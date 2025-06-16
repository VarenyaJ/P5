import os
import pathlib
import shutil
from os import listdir
from unittest import mock

from click.testing import CliRunner
from joblib.testing import skipif

from scripts.pull_git_files import pull_git_files

CI = bool(os.getenv("GITHUB_ACTIONS"))


@skipif(CI, reason="CI needs internet access for this test")
def test_pull_git_files(request):
    out_dir = pathlib.Path(request.path).parent.parent.parent / "data/tmp/test"
    runner = CliRunner()

    result = runner.invoke(
        pull_git_files,
        [
            str(out_dir),
            "https://github.com/P2GX/phenopacket2prompt",
            "docs/cases/",
        ],
    )

    assert (
        result.exit_code == 0
    ), f"CLI exited with code {result.exit_code}: {result.output}"

    assert len(listdir(out_dir / "cases")) > 0
    shutil.rmtree(out_dir)


@mock.patch("scripts.pull_git_files.Repo.clone_from")
def test_pull_git_files_mocked(mock_clone, tmp_path):
    runner = CliRunner()
    out_dir = tmp_path / "test_output"

    repo_url = "https://github.com/any/repo.git"
    files_to_copy = "docs/cases"

    def mock_clone_from_effect(url: str, to_path: str):
        cloned_content_path = pathlib.Path(to_path) / files_to_copy
        cloned_content_path.mkdir(parents=True)

        (cloned_content_path / "dummy_file.txt").write_text("hello world")

    mock_clone.side_effect = mock_clone_from_effect
    result = runner.invoke(
        pull_git_files,
        [
            str(out_dir),
            repo_url,
            files_to_copy,
        ],
    )

    assert (
        result.exit_code == 0
    ), f"CLI exited with code {result.exit_code}: {result.output}"

    mock_clone.assert_called_once()
    call_args, call_kwargs = mock_clone.call_args
    assert call_kwargs["url"] == repo_url

    assert "to_path" in call_kwargs

    final_output_path = out_dir / "cases"
    assert (
        final_output_path.exists()
    ), "The 'cases' directory was not created in the output."
    assert (final_output_path / "dummy_file.txt").exists()
    assert (final_output_path / "dummy_file.txt").read_text() == "hello world"
