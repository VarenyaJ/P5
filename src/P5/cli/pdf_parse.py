# src/P5/cli/pdf_parse.py
import json
from pathlib import Path
from datetime import datetime
import click

VALID_SUFFIXES = {".pdf", ".docx", ".pptx", ".html", ".htm", ".txt"}

# Detect docling without blind except
try:
    from docling.document_converter import DocumentConverter  # type: ignore

    DOC_AVAILABLE = True
except ImportError:
    DOC_AVAILABLE = False


def _collect_files(path: Path, pattern: str | None) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in VALID_SUFFIXES else []
    if pattern:
        return [
            p
            for p in path.glob(pattern)
            if p.is_file() and p.suffix.lower() in VALID_SUFFIXES
        ]
    return [
        p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in VALID_SUFFIXES
    ]


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _extract_with_docling(in_path: Path) -> tuple[str, str]:
    """
    Return (text, format_hint). Tries multiple docling APIs to be robust across versions.
    format_hint is 'md' or 'txt'.
    """
    converter = DocumentConverter()
    res = converter.convert(str(in_path))
    obj = getattr(res, "document", res)

    for attr, fmt in (
        ("export_to_markdown", "md"),
        ("to_markdown", "md"),
        ("export_to_text", "txt"),
        ("to_text", "txt"),
    ):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn(), fmt
            except (RuntimeError, AttributeError, TypeError, ValueError):
                continue
    return str(obj), "txt"


def _process_one(
    p: Path, use_docling: bool, text_dir: Path, err_dir: Path
) -> tuple[dict, bool, bool]:
    """
    Process a single file. Returns (manifest_record, wrote_text, failed).
    """
    rec = {
        "path": str(p),
        "name": p.name,
        "suffix": p.suffix.lower(),
        "size_bytes": p.stat().st_size,
        "engine": "docling" if use_docling else "none",
        "text_path": None,
        "error_path": None,
    }

    try:
        text = ""
        fmt = "txt"
        if use_docling and p.suffix.lower() in VALID_SUFFIXES:
            text, fmt = _extract_with_docling(p)
        elif p.suffix.lower() == ".txt":
            text = p.read_text(encoding="utf-8", errors="ignore")
            fmt = "txt"

        if text:
            target = text_dir / (p.with_suffix("." + fmt).name)
            target.write_text(text, encoding="utf-8", errors="ignore")
            rec["text_path"] = str(target)
            return rec, True, False

        return rec, False, False

    except (OSError, UnicodeError, RuntimeError, ValueError) as e:
        err_file = err_dir / (p.stem + ".err.txt")
        err_file.write_text(f"{type(e).__name__}: {e}\n", encoding="utf-8")
        rec["error_path"] = str(err_file)
        return rec, False, True


@click.command(
    name="pdf-parse", context_settings=dict(help_option_names=["-h", "--help"])
)
@click.option(
    "-i",
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True),
    help="PDF (or directory) to parse",
)
@click.option(
    "-o",
    "--out",
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
    "--engine",
    type=click.Choice(["auto", "docling"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Extraction engine. 'auto' uses docling when available.",
)
@click.option("--dry-run", is_flag=True, help="List files and exit")
def main(input_path: str, out_dir: str, pattern: str, engine: str, dry_run: bool):
    """
    Enumerate valid documents, extract text with docling (if available), and
    write a manifest with per-file metadata. Text outputs land under 'text/'.
    """
    inp = Path(input_path).expanduser().resolve()
    out = Path(out_dir).expanduser().resolve()
    _ensure_dir(out)

    run_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = out / f"run_{run_stamp}"
    text_dir = run_dir / "text"
    err_dir = run_dir / "errors"
    _ensure_dir(text_dir)
    _ensure_dir(err_dir)

    manifest = run_dir / "manifest.jsonl"

    files = _collect_files(inp, pattern if inp.is_dir() else None)
    if not files:
        click.echo("No input files matched.")
        return

    use_docling = (engine.lower() == "docling") or (
        engine.lower() == "auto" and DOC_AVAILABLE
    )
    if engine.lower() == "docling" and not DOC_AVAILABLE:
        raise click.ClickException(
            "docling is not installed. Install it or use --engine auto."
        )

    click.echo(
        f"Found {len(files)} file(s). Using engine: {'docling' if use_docling else 'none'}"
    )
    if dry_run:
        for p in files[:20]:
            click.echo(f"- {p}")
        if len(files) > 20:
            click.echo(f"... and {len(files) - 20} more")
        return

    written = 0
    failed = 0

    with open(manifest, "w", encoding="utf-8") as mf:
        for p in files:
            rec, wrote, fail = _process_one(p, use_docling, text_dir, err_dir)
            mf.write(json.dumps(rec) + "\n")
            written += int(wrote)
            failed += int(fail)

    click.echo(f"Wrote manifest to {manifest}")
    click.echo(f"Extracted text files: {written}")
    if failed:
        click.echo(f"Failures: {failed} (see {err_dir})")
    if not DOC_AVAILABLE and use_docling:
        # shouldn't happen (guarded), but keep the note for clarity
        click.echo(
            "Note: docling not detected; only passthrough for .txt was performed."
        )
