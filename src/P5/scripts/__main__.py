#!/usr/bin/env python3
import click, logging

from P5.scripts.pull_git_files import pull_git_files
from P5.scripts.create_pmid_pkl import create_pmid_pkl
from P5.scripts.pmid_downloader import pmid_downloader
from P5.scripts.create_phenopacket_dataset import create_phenopacket_dataset

@click.group(invoke_without_command=True)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose (DEBUG) logging"
)
@click.pass_context
def cli(ctx, verbose):
    """
    P5 scripts command-line interface.
    If no subcommand is given, it will run the full pipeline:
        1) pull_git_files
        2) create_pmid_pkl
        3) pmid_downloader
        4) create_phenopacket_dataset
    """
    # set up context and logging
    ctx.ensure_object(dict)
    ctx.obj["VERBOSE"] = verbose
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.debug("Verbose mode is ON")

    # if no subcommand, execute the four pipeline steps
    if ctx.invoked_subcommand is None:
        logger.info("No subcommand given; running full pipeline in order…")

        # 1) Pull phenopackets
        pull_git_files.callback(
            "scripts/data/tmp/phenopacket_store",
            "https://github.com/monarch-initiative/phenopacket-store",
            "notebooks"
        )

        # 2) Create PMIDs .pkl
        create_pmid_pkl.callback(
            "assets/cases",
            "assets/pmids.pkl",
            True  # --recursive_dir_search
        )

        # 3) Download PDFs (first 10)
        pmid_downloader.callback(
            "scripts/data/pmids.pkl",
            "scripts/data/pmid_pdfs",
            10
        )

        # 4) Build comparison CSV
        create_phenopacket_dataset.callback(
            "scripts/data/tmp/phenopacket_store/pmid_pdfs",
            "scripts/data/tmp/phenopacket_store/notebooks",
            "scripts/data/tmp/PMID_PDF_Phenopacket_list_in_phenopacket_store.csv",
            False,  # --recursive_input_dir
            True    # --recursive_ground_truth_dir
        )

@cli.command("pull_git_files")
@click.pass_context
def _pull(ctx, *args, **kwargs):
    """Alias for pull_git_files"""
    pull_git_files.callback(*args, **kwargs)

@cli.command("create_pmid_pkl")
@click.pass_context
def _pk(ctx, *args, **kwargs):
    """Alias for create_pmid_pkl"""
    create_pmid_pkl.callback(*args, **kwargs)

@cli.command("pmid_downloader")
@click.pass_context
def _dl(ctx, *args, **kwargs):
    """Alias for pmid_downloader"""
    pmid_downloader.callback(*args, **kwargs)

@cli.command("create_phenopacket_dataset")
@click.pass_context
def _ds(ctx, *args, **kwargs):
    """Alias for create_phenopacket_dataset"""
    create_phenopacket_dataset.callback(*args, **kwargs)

if __name__ == "__main__":
    cli(obj={})