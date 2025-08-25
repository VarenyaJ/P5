import json
import os

import click
from docling.document_converter import DocumentConverter
from ollama import chat, ChatResponse

# top
from datetime import datetime, timezone
from json.decoder import JSONDecodeError

def _now_rfc3339_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _minimal_pp(patient_id: str) -> dict:
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
def file_to_phenopacket(file_dir: str, out_dir: str, prompt: str, model: str, file_type: str):
    """This script converts a several file to a Phenopacket via LLM."""
    if not file_type.startswith("."):
        file_type = f".{file_type}"

    file_dirs = [
        f"{file_dir}/{f}"
        for f in os.listdir(file_dir)
        if os.path.isfile(f"{file_dir}/{f}") and f.endswith(file_type)
    ]

    filename_to_content: dict[str, str] = dict()
    if file_type.lower() in [".pdf", ".pptx", ".docx", ".doc", ".html"]:
        converter = DocumentConverter()
        filename_to_content = {
            file_dir.split("/")[-1]: converter.convert(file_dir).document.export_to_text()
            for file_dir in file_dirs
        }
    elif file_type.lower() == ".txt":
        filename_to_content = {
            file_dir.split("/")[-1]: open(file_dir).read().split("[text]")[-1]
            for file_dir in file_dirs
        }
        
    for file_name, text in filename_to_content.items():
        # Ask Ollama for pure JSON
        response: ChatResponse = chat(
            model=model,
            messages=[{"role": "user", "content": f"{prompt} {text} [EOS]"}],
            stream=False,
            format="json",
            options={"temperature": 0},
        )

        stem = file_name.split(".")[0]
        out_path = f"{out_dir}/{stem}.json"

        try:
            phenopacket_json = json.loads(response["message"]["content"])
        except JSONDecodeError:
            # Fall back to a minimal, valid phenopacket so a file is always produced
            click.secho(
                message=f"{model} did not return valid JSON for {file_name}; writing minimal phenopacket.",
                err=True, fg="yellow",
            )
            phenopacket_json = _minimal_pp(patient_id=stem)

        with open(out_path, "w") as f:
            json.dump(phenopacket_json, f)


if __name__ == "__main__":
    file_to_phenopacket()
