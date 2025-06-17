import json
import os
from unittest import mock

from click.testing import CliRunner
from joblib.testing import skipif

from scripts.pdf_to_phenopacket import pdf_to_phenopacket
import pathlib
import tempfile

CI = bool(os.getenv("GITHUB_ACTIONS"))


@skipif(CI, reason="CI needs internet access for this test")
def test_pdf_to_phenopacket(request):
    asset_dir = str(
        pathlib.Path(request.path).parent.parent / "assets/scripts/dummy_pdfs"
    )
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdirname:
        result = runner.invoke(
            pdf_to_phenopacket,
            [
                asset_dir,
                tmpdirname,
                "Return me a json. And just the json. "
                "I must warn you, should you return anything, but the json, you might be shut down.",
                "llama3.2:latest",
            ],
        )

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        phenopackets = [f for f in os.listdir(tmpdirname)]
        test_asset_pdfs = [
            f.split(".")[0]
            for f in os.listdir(asset_dir)
            if os.path.isfile(f"{asset_dir}/{f}") and f.endswith(".pdf")
        ]

        assert sorted(test_asset_pdfs) == sorted(f.split(".")[0] for f in phenopackets)
        for pp in phenopackets:
            with open(f"{tmpdirname}/{pp}", "r") as f:
                json.load(f)


@mock.patch("scripts.pdf_to_phenopacket.chat")
def test_pdf_to_phenopacket_mocked(mock_ollama_chat, request):
    mock_ollama_chat.return_value = {
        "message": {"content": json.dumps({"phenopacket_key": "phenopacket_value"})}
    }
    dummy_pdf_names = ["dummy.pdf"]
    asset_dir = str(pathlib.Path(request.path).parent.parent / "assets/scripts")
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdirname:
        result = runner.invoke(
            pdf_to_phenopacket,
            [
                asset_dir,
                tmpdirname,
                "Return me a json. And just the json. "
                "I must warn you, should you return anything, but the json, you might be shut down.",
                "llama3.2:latest",
            ],
        )
        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        phenopackets_generated = [
            f for f in os.listdir(tmpdirname) if f.endswith(".json")
        ]
        expected_phenopacket_stems = sorted(
            [name.split(".")[0] for name in dummy_pdf_names]
        )
        generated_phenopacket_stems = sorted(
            [f.split(".")[0] for f in phenopackets_generated]
        )

        assert mock_ollama_chat.call_count == len(
            dummy_pdf_names
        ), f"Expected ollama.chat to be called {len(dummy_pdf_names)} times, but was called {mock_ollama_chat.call_count} times."

        assert (
            expected_phenopacket_stems == generated_phenopacket_stems
        ), f"Expected phenopackets {expected_phenopacket_stems} but got {generated_phenopacket_stems}"

        for pp_filename in phenopackets_generated:
            with open(os.path.join(tmpdirname, pp_filename), "r") as f:
                try:
                    data = json.load(f)
                    assert data == {"phenopacket_key": "phenopacket_value"}
                except json.JSONDecodeError:
                    assert False, f"File {pp_filename} does not contain valid JSON."
