"""
Scan a directory, extract PMIDs from filenames, and write an index .pkl

Examples:
  create-pmid-pkl --root ./pdfs --out pmids.pkl
  create-pmid-pkl --root ./papers --pattern "*/*.pdf" --out pmids.pkl
"""

import click
import pickle
import re
from pathlib import Path
from typing import Iterable

PMID_RE = re.compile(r"(?<!\d)(?:PMID[_\-\s:]*)?(\d{7,8})(?!\d)", re.IGNORECASE)


def iter_files(root: Path, pattern: str) -> Iterable[Path]:
    if pattern:
        yield from root.glob(pattern)
    else:
        # default: everything under root
        yield from root.rglob("*")


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "--root",
    "root_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directory to scan",
)
@click.option(
    "--pattern",
    default="**/*.pdf",
    help="Glob (relative to root) for files to scan (default: **/*.pdf)",
)
@click.option(
    "--out",
    "out_file",
    required=True,
    type=click.Path(),
    help="Path to write the pickle index (e.g., pmids.pkl)",
)
@click.option("--dry-run", is_flag=True, help="Print matches but do not write pickle")
def main(root_dir: str, pattern: str, out_file: str, dry_run: bool):
    root = Path(root_dir).expanduser().resolve()
    matches: dict[str, list[str]] = {}

    for path in iter_files(root, pattern):
        if not path.is_file():
            continue
        m = PMID_RE.search(path.name)
        if not m:
            continue
        pmid = m.group(1)
        matches.setdefault(pmid, []).append(str(path))

    click.echo(f"Found {len(matches)} unique PMIDs")
    # show a small sample
    shown = 0
    for pmid, files in list(matches.items())[:10]:
        click.echo(f"  PMID {pmid}: {files[0]}")
        shown += 1
    if shown and len(matches) > shown:
        click.echo(f"  … and {len(matches) - shown} more")

    if dry_run:
        return

    out_path = Path(out_file).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(matches, f, protocol=pickle.HIGHEST_PROTOCOL)
    click.echo(f"Wrote pickle index to {out_path}")
