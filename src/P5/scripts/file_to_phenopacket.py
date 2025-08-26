"""
file_to_phenopacket.py

CLI to convert a directory of clinical files (PDF/TXT/etc.) into **one Phenopacket JSON per file**
using a local Ollama model.

Key design choices / maintenance notes:
- We request **structured JSON** from Ollama (`format="json"`) to reduce parsing errors.
- If the model still returns non-JSON, we emit a **minimal, valid Phenopacket scaffold** so each
  input produces an output file (helps tests/CI remain deterministic).
- The Phenopacket `metaData.created` is stamped in RFC3339(UTC, "Z") to satisfy protobuf parsing.
"""

import click
import json
import os

from datetime import datetime, timezone
from docling.document_converter import DocumentConverter
from json.decoder import JSONDecodeError
from ollama import chat, ChatResponse


def _now_rfc3339_z() -> str:
    """
    Return current UTC time in RFC3339 format with a trailing 'Z', e.g. '2025-08-25T12:34:56Z'.

    Why:
    - google.protobuf Timestamp JSON parsing is strict and expects this format.
    - Avoids the older utcfromtimestamp pattern that triggers deprecation warnings upstream.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _minimal_pp(patient_id: str) -> dict:
    """
    Construct a minimal, valid Phenopacket JSON.

    This is used as a **fallback** when the LLM does not return valid JSON. Producing *some* valid
    output per input file keeps downstream steps and tests predictable, and makes it obvious in
    artifacts which files need reprocessing.
    """
    return {
        "id": patient_id,
        "subject": {"id": patient_id},
        "phenotypicFeatures": [],
        "metaData": {
            "created": _now_rfc3339_z(),
            "createdBy": "P5.file_to_phenopacket",
            "phenopacketSchemaVersion": "2.0.2",
        },
    }


# File types we support for conversion. Non-text types are routed through docling.
file_types = [".pdf", ".pptx", ".docx", ".doc", ".html", ".txt"]


@click.command()
@click.argument("file_dir", type=click.Path(exists=True))
@click.argument("out_dir", type=click.Path(exists=False, dir_okay=True))
@click.argument("prompt", type=click.STRING)
@click.argument("model", type=click.STRING)
@click.option(
    "--file-type",
    type=click.Choice(file_types, case_sensitive=False),
    help=f"The type of file to process. Possible types are: {file_types}",
    default=".pdf",
)
def file_to_phenopacket(
    file_dir: str, out_dir: str, prompt: str, model: str, file_type: str
):
    """
    Convert all files of a given type in `file_dir` into Phenopacket JSONs in `out_dir`.

    Parameters
    ----------
    file_dir : str
        Directory containing input files.
    out_dir : str
        Destination directory (created by Click before we write files).
    prompt : str
        Prompt prefix prepended to file text for the LLM call.
    model : str
        Ollama model name (e.g., "llama3.2:latest").
    file_type : str
        Extension to filter inputs (e.g., ".pdf" or ".txt").

    Behavior
    --------
    - Uses docling to convert non-.txt inputs to text.
    - Requests JSON from Ollama with `format="json"` and low temperature for determinism.
    - On JSON parse failure, writes a minimal valid Phenopacket as a fallback (and warns).
    """
    if not file_type.startswith("."):
        # Accept "pdf" as " .pdf " for convenience; tests pass in ".pdf" already.
        file_type = f".{file_type}"

    # Discover files we will process.
    file_dirs = [
        f"{file_dir}/{f}"
        for f in os.listdir(file_dir)
        if os.path.isfile(f"{file_dir}/{f}") and f.endswith(file_type)
    ]

    filename_to_content: dict[str, str] = dict()

    # Convert input files to plain text for the LLM.
    if file_type.lower() in [".pdf", ".pptx", ".docx", ".doc", ".html"]:
        # Docling can raise if a document is malformed; test assets are simple and safe.
        converter = DocumentConverter()
        filename_to_content = {
            file_dir.split("/")[-1]: converter.convert(
                file_dir
            ).document.export_to_text()
            for file_dir in file_dirs
        }
    elif file_type.lower() == ".txt":
        # Text fast-path. Many of our assets prefix "[text]"—we strip it to be robust.
        filename_to_content = {
            file_dir.split("/")[-1]: open(file_dir).read().split("[text]")[-1]
            for file_dir in file_dirs
        }

    # One LLM request per file; one JSON file per input.
    for file_name, text in filename_to_content.items():
        # Ask Ollama for **pure JSON**. `format="json"` makes newer models far less chatty.
        response: ChatResponse = chat(
            model=model,
            messages=[{"role": "user", "content": f"{prompt} {text} [EOS]"}],
            stream=False,
            format="json",
            options={"temperature": 0},  # deterministic output helps tests/CI
        )

        stem = file_name.split(".")[0]
        out_path = f"{out_dir}/{stem}.json"

        try:
            # Newer ollama versions return a dict-like ChatResponse; we index directly here.
            phenopacket_json = json.loads(response["message"]["content"])
        except JSONDecodeError:
            # If the model ignored format hints or emitted trailing prose, keep the pipeline going.
            click.secho(
                message=f"{model} did not return valid JSON for {file_name}; writing minimal phenopacket.",
                err=True,
                fg="yellow",
            )
            phenopacket_json = _minimal_pp(patient_id=stem)

        # Ensure the emitted file is valid JSON; readers/tests can rely on it.
        with open(out_path, "w") as f:
            json.dump(phenopacket_json, f)


if __name__ == "__main__":
    file_to_phenopacket()
