#!/usr/bin/env python3
import sys
import click
import logging

from P5.scripts.pull_git_files import pull_git_files
from P5.scripts.create_pmid_pkl import create_pmid_pkl
from P5.scripts.pmid_downloader import pmid_downloader
from P5.scripts.create_phenopacket_dataset import create_phenopacket_dataset

@click.group(invoke_without_command=True)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose (DEBUG) logging",
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
        level=level, format="%(asctime)s %(levelname)s %(name)s — %(message)s"
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
            "notebooks",
        )

        # 2) Create PMIDs .pkl
        create_pmid_pkl.callback(
            "assets/cases", "assets/pmids.pkl", True  # --recursive_dir_search
        )

        # 3) Download PDFs (first 10)
        pmid_downloader.callback("scripts/data/pmids.pkl", "scripts/data/pmid_pdfs", 10)

        # 4) Build comparison CSV
        create_phenopacket_dataset.callback(
            "scripts/data/tmp/phenopacket_store/pmid_pdfs",
            "scripts/data/tmp/phenopacket_store/notebooks",
            "scripts/data/tmp/PMID_PDF_Phenopacket_list_in_phenopacket_store.csv",
            False,  # --recursive_input_dir
            True,  # --recursive_ground_truth_dir
        )

@cli.command("pull-git-files", help="Pull phenopacket‑store files")
@click.argument("output_dir")
@click.argument("repo_url")
@click.argument("notebooks_dir")
@click.pass_context
def pull_files_cmd(ctx, output_dir, repo_url, notebooks_dir):
    pull_git_files.callback(output_dir, repo_url, notebooks_dir)

@cli.command("create-pmid-pkl", help="Generate the PMIDs .pkl file")
@click.argument("cases_dir")
@click.argument("output_pkl")
@click.option(
    "--recursive/--no-recursive",
    default=True,
    help="Search directories recursively",
)
@click.pass_context
def pmid_pkl_cmd(ctx, cases_dir, output_pkl, recursive):
    create_pmid_pkl.callback(cases_dir, output_pkl, recursive)

@cli.command("pmid-downloader", help="Download PDFs by PMID")
@click.argument("input_pkl")
@click.argument("output_dir")
@click.argument("max_pdfs", type=int)
@click.pass_context
def downloader_cmd(ctx, input_pkl, output_dir, max_pdfs):
    pmid_downloader.callback(input_pkl, output_dir, max_pdfs)

@cli.command("create-phenopacket-dataset", help="Build the comparison CSV")
@click.argument("pmid_pdfs_dir")
@click.argument("notebooks_dir")
@click.argument("output_csv")
@click.option(
    "--recursive-input/--no-recursive-input",
    default=False,
    help="Recurse into input directory",
)
@click.option(
    "--recursive-ground-truth/--no-recursive-ground-truth",
    default=True,
    help="Recurse into ground‑truth directory",
)
@click.pass_context
def dataset_cmd(
    ctx,
    pmid_pdfs_dir,
    notebooks_dir,
    output_csv,
    recursive_input,
    recursive_ground_truth,
):
    create_phenopacket_dataset.callback(
        pmid_pdfs_dir,
        notebooks_dir,
        output_csv,
        recursive_input,
        recursive_ground_truth,
    )

if __name__ == "__main__":
    cli()(p5)