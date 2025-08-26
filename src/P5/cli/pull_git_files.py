"""
Clone or pull a Git repo into a destination directory.

Examples:
  pull-git-files --repo https://github.com/obophenotype/human-phenotype-ontology.git --dest data/hpo
"""

import click
from pathlib import Path
from git import Repo, InvalidGitRepositoryError


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "--repo", "repo_url", required=True, help="Git repository URL (https or ssh)"
)
@click.option(
    "--dest", "dest_dir", required=True, type=click.Path(), help="Destination directory"
)
@click.option("--branch", default=None, help="Optional branch or tag to checkout")
def main(repo_url: str, dest_dir: str, branch: str | None):
    dest = Path(dest_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    if (dest / ".git").exists():
        # existing repo → pull
        try:
            repo = Repo(dest)
        except InvalidGitRepositoryError:
            raise click.ClickException(
                f"Destination exists but is not a git repo: {dest}"
            )
        click.echo(f"Updating existing repo in {dest} …")
        repo.remotes.origin.fetch()
        if branch:
            repo.git.checkout(branch)
            repo.remotes.origin.pull(branch)
        else:
            # pull current branch
            repo.remotes.origin.pull()
    else:
        # fresh clone
        click.echo(f"Cloning {repo_url} into {dest} …")
        repo = Repo.clone_from(repo_url, dest)
        if branch:
            repo.git.checkout(branch)

    # show short commit id for reproducibility
    head = repo.head.commit.hexsha[:12]
    click.echo(f"Repo ready at {dest} (HEAD {head})")
