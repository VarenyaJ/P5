import click
from . import __version__

# Make help rock-solid:
# - add_help_option=False so we control -h/--help ourselves
# - invoke_without_command=True so `p5` (no args) shows help
@click.group(invoke_without_command=True, add_help_option=False)
@click.version_option(version=__version__, prog_name="P5")
@click.option(
    "-h",
    "--help",
    "show_help",
    is_flag=True,
    is_eager=True,
    help="Show this message and exit.",
)
@click.pass_context
def main(ctx: click.Context, show_help: bool):
    """P5: Prompt-driven Parsing of Prenatal PDFs to Phenopackets."""
    # Lazy import: don't force optional deps just to show help/version
    try:
        from .cli import create_pmid_pkl as _  # noqa: F401
        from .cli import pull_git_files as _   # noqa: F401
    except Exception:
        # Optional tools—ignore import failures here
        pass

    # Print help if requested or if no subcommand was invoked
    if show_help or ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


if __name__ == "__main__":
    main()
