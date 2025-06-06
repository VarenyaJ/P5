import click
from ollama import chat, ChatResponse
import os
from docling.document_converter import DocumentConverter
import json


@click.command()
@click.argument("file_dir", type=click.Path(exists=True))
@click.argument("out_dir", type=click.Path(exists=True))
@click.argument("prompt", type=click.STRING)
@click.argument("model", type=click.STRING)
def pdf_to_phenopacket(file_dir: str, out_dir: str, prompt: str, model: str):
    """This script converts a PDF file to a Phenopacket file."""
    pdf_file_directories = [
        f"{file_dir}/{f}"
        for f in os.listdir(file_dir)
        if os.path.isfile(f"{file_dir}/{f}") and f.endswith(".pdf")
    ]
    converter = DocumentConverter()
    llm_ready_pdfs = {
        pdf_dir.split("/")[-1]: converter.convert(pdf_dir)
        for pdf_dir in pdf_file_directories
    }

    for pdf_file_name, pdf_file in llm_ready_pdfs.items():
        response: ChatResponse = chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt} {pdf_file.document.export_to_text()}",
                },
            ],
        )

        try:
            phenopacket_json = json.loads(response["message"]["content"])
            with open(f"{out_dir}/{pdf_file_name.split(".")[0]}.json", "w") as f:
                json.dump(phenopacket_json, f)
        except json.decoder.JSONDecodeError:
            click.secho(
                message=f"{model} did not convert {pdf_file_name} into valid json format",
                err=True,
                fg="red",
            )


if __name__ == "__main__":
    pdf_to_phenopacket()
