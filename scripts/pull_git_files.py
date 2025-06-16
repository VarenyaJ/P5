import tempfile
from pathlib import Path

from git import Repo
import click
import shutil


@click.command(
    help="""
Clones a Git repository and copies a specific file or directory from it.

This command will:

1. Clone the git REPO into a temporary directory.
2. Move the specified FILES_TO_COPY_DIR from the cloned repo. 
3. Place the moved contents into the OUT_DIR. 
4. Clean up the temporary cloned repository. 

OUT_DIR:            The destination directory for the copied files.
REPO:               The URL of the git repository to clone.
FILES_TO_COPY_DIR:  The relative path to the directory or file
                    within the repository to copy.

Example:
  python pull_git_files.py ./local_assets https://github.com/Call-for-Code/Project-Sample src/assets
"""
)
@click.argument("out_dir", type=click.Path(exists=True))
@click.argument("repo", type=click.STRING)
@click.argument("files_to_copy_dir", type=click.Path())
def pull_git_files(out_dir: str, repo: str, files_to_copy_dir: str):
    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        out_dir.mkdir(exist_ok=True, parents=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        Repo.clone_from(
            url=repo,
            to_path=tmp_dir,
        )
        shutil.move(f"{tmp_dir}/{files_to_copy_dir}", out_dir)


if __name__ == "__main__":
    pull_git_files()
