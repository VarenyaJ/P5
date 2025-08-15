import json
from pathlib import Path
from datetime import datetime
import click

# accepted input formats for the initial stub
VALID_SUFFIXES = {".pdf", ".docx", ".pptx", ".html", ".htm", ".txt"}

def _collect_files(path: Path, pattern: str | None) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in VALID_SUFFIXES else []
    # directory
    if pattern:
        # explicit glob under the root
        return [p for p in path.glob(pattern) if p.is_file() and p.suffix.lower() in VALID_SUFFIXES]
    # default: recurse all valid files
    return [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in VALID_SUFFIXES]

@click.command(name="pdf-parse", context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "-i", "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True),
    help="PDF (or directory) to parse",
)
@click.option(
    "-o", "--out",
    "out_dir",
    required=True,
    type=click.Path(),
    help="Output directory for run artifacts",
)
@click.option(
    "--pattern",
    default="**/*",
    show_default=True,
    help="Glob (relative to input dir) when INPUT is a directory",
)
@click.option(
    "--extract-text/--no-extract-text",
    default=False,
    show_default=True,
    help="If set, write naive text dumps for .txt only (PDF requires docling, added later).",
)
@click.option("--dry-run", is_flag=True, help="List files and exit")
def main(input_path: str, out_dir: str, pattern: str, extract_text: bool, dry_run: bool):
    """
    Stub for the P5 pipeline: enumerate files, create a manifest, and (optionally) dump text
    for .txt inputs. PDF/doc/docx parsing will be wired to docling in a follow-up.
    """
    inp = Path(input_path).expanduser().resolve()
    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    run_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = out / f"run_{run_stamp}"
    text_dir = run_dir / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    manifest = run_dir / "manifest.jsonl"

    files = _collect_files(inp, pattern if inp.is_dir() else None)

    if not files:
        click.echo("No input files matched.")
        return

    click.echo(f"Found {len(files)} file(s).")
    if dry_run:
        for p in files[:20]:
            click.echo(f"- {p}")
        if len(files) > 20:
            click.echo(f"... and {len(files) - 20} more")
        return

    # create manifest & optional text dumps
    with open(manifest, "w", encoding="utf-8") as mf:
        for p in files:
            rec = {
                "path": str(p),
                "name": p.name,
                "suffix": p.suffix.lower(),
                "size_bytes": p.stat().st_size,
            }
            mf.write(json.dumps(rec) + "\n")

            if extract_text and p.suffix.lower() == ".txt":
                # only passthrough for .txt right now
                target = text_dir / (p.stem + ".txt")
                try:
                    target.write_text(p.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    # fallback: binary read/write
                    target.write_bytes(p.read_bytes())

    click.echo(f"Wrote manifest to {manifest}")
    if extract_text:
        click.echo(f"Text dumps (for .txt only) under {text_dir}")
    click.echo("PDF/office parsing will be enabled via docling in the next step.")
