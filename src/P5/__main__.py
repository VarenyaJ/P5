# src/P5/__main__.py
import click
from . import __version__
from .cli.pdf_parse import main as pdf_parse_cmd  # import at top (fixes E402)


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
    if show_help or ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


# Register subcommands
main.add_command(pdf_parse_cmd, name="pdf-parse")

if __name__ == "__main__":
    main()
