import os
import time
from pathlib import Path
from typing import Optional

import click
import requests
from Bio import Entrez
from requests.exceptions import InvalidSchema
from selenium import webdriver
from selenium.common import InvalidSessionIdException
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm

from P5.scripts.utils import pkl_loader


def _get_pmcid(pmid: str) -> Optional[str]:
    """This function uses the PubMed API called Entrez to get a PMCID from a PMID."""
    Entrez.email = "fake.email@email.de"

    with Entrez.elink(
        dbfrom="pubmed", db="pmc", id=pmid.split("_")[-1], linkname="pubmed_pmc"
    ) as handle:
        records = Entrez.read(handle)

    link_sets_db = records[0]["LinkSetDb"]
    if link_sets_db == []:
        return None
    pmcid = link_sets_db[0]["Link"][0]["Id"]
    return pmcid


def download_pdf(pmcid: str, pmid: str, pdf_out_dir: str):
    """
    This function
    1. takes a PMCID of a PubMed article
    2. guesses the URL of the associated PDF
    3. uses a Selenium browser to pause for a few seconds in order to bypass Javascript anti-web-scraping challenges
    4. the cookies of the browser are then used to download the PDF using requests
    """

    try:
        # via guesswork, this is probably the URL of the PDF
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"

        # set up the Selenium browser. The --headless=new argument means the Chrome browser does not pop up.
        # TODO: Additional arguments needed to implement headless and test for other OS's
        options = Options()
        options.add_argument("--headless=new")

        with webdriver.Chrome(options=options) as driver:
            driver.get(pdf_url)
            time.sleep(4)  # give time for JS challenge to complete

            # Get the actual PDF URL if redirected
            final_pdf_url = driver.current_url
            # Extract cookies set by the JS
            cookies = driver.get_cookies()

        # Now use requests with those cookies to get the real PDF
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie["name"], cookie["value"])

        # TODO test on other OS's using different user agents
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            ),
            "Accept": "application/pdf",
            "Referer": "https://pmc.ncbi.nlm.nih.gov/",
        }

        response = session.get(final_pdf_url, headers=headers)
        with open(f"{pdf_out_dir}/{pmid}.pdf", "wb") as f:
            f.write(response.content)
            click.secho(
                message=f"A PDF for {pmid} was successfully downloaded. PMCID={pmcid}.",
                fg="green",
            )

    except (InvalidSessionIdException, FileNotFoundError, IOError, InvalidSchema) as e:
        click.secho(
            message=f"An error occurred when downloading {pmid} = PMC_{pmcid}: {e}",
            err=True,
            fg="red",
        )


@click.command(
    help="""
INPUT: a .pkl file whose entries are strings of the form "PMID_1234567" 
OUTPUT: a directory containing the corresponding PDFs of the journal articles (whenever they are accessible via PubMed Central).

PKL_FILE_PATH:     the file path for the .pkl file
PDF_OUTPUT_DIR:    directory to dump the PDFs
DL_CUT_OFF:     the maximum amount of PDFs that we would like to download. If set to 0, the entire collection of PDFs will be downloaded

Usage:
    python -m P5.scripts.pmid_downloader <PKL_FILE_PATH> <PDF_OUT_DIR> <DL_CUT_OFF>

Example:
    python -m P5.scripts.pmid_downloader data/pmids.pkl data/pmid_pdfs 10
"""
)
@click.argument("pkl_file_path", type=click.Path(exists=True))
@click.argument("pdf_out_dir", type=click.Path(exists=False, dir_okay=True))
@click.argument("dl_cut_off", type=int)
def pmid_downloader(pkl_file_path: str, pdf_out_dir: str, dl_cut_off: int):
    pdf_out_dir_path = Path(pdf_out_dir)
    if not pdf_out_dir_path.exists():
        pdf_out_dir_path.mkdir(exist_ok=True, parents=True)

    all_pmids: set = pkl_loader(pkl_file_path)

    if dl_cut_off == 0:
        dl_cut_off = len(all_pmids)

    if dl_cut_off > len(all_pmids):
        click.secho(
            message=f"Requested download cut-off size of {dl_cut_off} greater than number of PMIDs in {pkl_file_path}. Attempting to download all {len(all_pmids)} PMIDs.",
            fg="yellow",
        )
        dl_cut_off = len(all_pmids)

    pmid_batch: set = set(
        list(all_pmids)[:dl_cut_off]
    )  # entries of the form "PMID_1234567"

    with tqdm(total=len(pmid_batch)) as progress_bar:
        for pmid in pmid_batch:
            progress_bar.set_description(f"Processing {pmid}")
            pmcid: str = _get_pmcid(pmid)  # of the form "1234567"
            if pmcid is None:
                click.secho(message=f"No PMCID found for {pmid}.", fg="yellow")
                progress_bar.update(1)
                continue
            download_pdf(pmcid, pmid, pdf_out_dir)
            progress_bar.update(1)

        pdf_count = len(os.listdir(pdf_out_dir))
        progress_bar.set_description(
            f"Processing of {str(len(pmid_batch))} PMIDs complete. {pdf_count} PDFs successfully downloaded."
        )


if __name__ == "__main__":
    pmid_downloader()
