import click
from . import __version__


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(version=__version__, prog_name="P5")
def main():
    """P5: Prompt-driven Parsing of Prenatal PDFs to Phenopackets."""
    # Subcommands are registered via entry points, but importing here ensures discovery if run via `python -m P5`.
    # Lazy import so dependencies for other CLIs aren't required just to show help/version.
    try:
        from .cli import create_pmid_pkl as _  # noqa: F401
        from .cli import pull_git_files as _  # noqa: F401
    except Exception:
        # Don't hard-fail on optional tools; they’re exposed by console_scripts anyway.
        pass


if __name__ == "__main__":
    main()
