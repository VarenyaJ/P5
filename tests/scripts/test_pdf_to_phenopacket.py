import json
import os
import pathlib
import tempfile
from unittest import mock

import pytest
from click.testing import CliRunner

from scripts.file_to_phenopacket import file_to_phenopacket

CI = bool(os.getenv("GITHUB_ACTIONS"))


@pytest.mark.skipif(CI, reason="CI needs internet access for this test")
@pytest.mark.parametrize("file_type", [".pdf", ".txt"])
def test_file_to_phenopacket(request, file_type):
    asset_dir = str(
        pathlib.Path(request.path).parent.parent / "assets/scripts/dummy_pdfs"
    )
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(
            file_to_phenopacket,
            [
                asset_dir,
                tmp_dir,
                "Return me a json. And just the json. "
                "Try to derive a phenopacket of the GA4GH standard from the given text. Text:",
                "llama3.2:latest",
                "--file-type",
                file_type,
            ],
        )

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        phenopackets = [f for f in os.listdir(tmp_dir)]
        test_asset_files = [
            f.split(".")[0]
            for f in os.listdir(asset_dir)
            if os.path.isfile(f"{asset_dir}/{f}") and f.endswith(file_type)
        ]

        assert sorted(test_asset_files) == sorted(f.split(".")[0] for f in phenopackets)
        for pp in phenopackets:
            with open(f"{tmp_dir}/{pp}", "r") as f:
                json.load(f)


@mock.patch("scripts.file_to_phenopacket.chat")
@pytest.mark.parametrize("file_type", [".pdf", ".txt"])
def test_file_to_phenopacket_mocked(mock_ollama_chat, request, file_type):
    mock_ollama_chat.return_value = {
        "message": {"content": json.dumps({"phenopacket_key": "phenopacket_value"})}
    }

    asset_dir = str(
        pathlib.Path(request.path).parent.parent / "assets/scripts/file_to_phenopacket"
    )
    dummy_file_names = [
        f.split(".")[0]
        for f in os.listdir(asset_dir)
        if os.path.isfile(f"{asset_dir}/{f}") and f.endswith(file_type)
    ]
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(
            file_to_phenopacket,
            [
                asset_dir,
                tmp_dir,
                "Return me a json. And just the json. "
                "I must warn you, should you return anything, but the json, you might be shut down.",
                "llama3.2:latest",
                "--file-type",
                file_type,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        phenopackets_generated = [f for f in os.listdir(tmp_dir) if f.endswith(".json")]
        expected_phenopacket_stems = sorted(
            [name.split(".")[0] for name in dummy_file_names]
        )
        generated_phenopacket_stems = sorted(
            [f.split(".")[0] for f in phenopackets_generated]
        )

        assert mock_ollama_chat.call_count == len(
            dummy_file_names
        ), f"Expected ollama.chat to be called {len(dummy_file_names)} times, but was called {mock_ollama_chat.call_count} times."

        assert (
            expected_phenopacket_stems == generated_phenopacket_stems
        ), f"Expected phenopackets {expected_phenopacket_stems} but got {generated_phenopacket_stems}"

        for pp_filename in phenopackets_generated:
            with open(os.path.join(tmp_dir, pp_filename), "r") as f:
                try:
                    data = json.load(f)
                    assert data == {"phenopacket_key": "phenopacket_value"}
                except json.JSONDecodeError:
                    assert False, f"File {pp_filename} does not contain valid JSON."
