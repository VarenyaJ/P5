import time
from pathlib import Path
from typing import Optional

import click
import requests
from Bio import Entrez
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm

from scripts.utils import find_pmids


def _get_pmcid(pmid: str) -> Optional[str]:
    """This function uses the PubMed API called Entrez to get a PMCID from a PMID.
    Once we have a PMCID we can use that to get the URL of a PDF.
    """
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
    this takes a PMCID of a PubMed article
    guesses the URL of the PDF
    uses Selenium to avoid anti-web-scraping JavaScript challenges
    and then downloads the PDF using requests
    we need to use the cookies of the Selenium browser and pause for 5 seconds to trick the webpage
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
                message=f"A PDF for PMID_{pmid} was successfully downloaded. PMCID = {pmcid}.",
                fg="green",
            )

    except Exception as e:
        click.secho(
            message=f"An error occurred when downloading PMID_{pmid} = PMC_{pmcid}: {e}",
            err=True,
            fg="red",
        )


@click.command(
    help="""
Takes a directory to find PMIDs and downloads the corresponding PDFs from PubMed (whenever they are accessible via PubMed Central).

PMID_FILE_PATH:     Directory where PMID files are located.
PDF_OUTPUT_DIR:     Ouput directory where PMID PDFs will be written.

Example: 
data/pmid_list.txt      data/pmid_pdfs, 
"""
)
@click.argument("pmid_file_path", type=click.Path(exists=True))
@click.argument("pdf_out_dir", type=click.Path(exists=False, dir_okay=True))
def pmid_downloader(pmid_file_path: str, pdf_out_dir: str):

    pdf_out_dir_path = Path(pdf_out_dir)
    if not pdf_out_dir_path.exists():
        pdf_out_dir_path.mkdir(exist_ok=True, parents=True)

    pmids = find_pmids(pmid_file_path)

    with tqdm(total=len(pmids)) as progress_bar:
        for pmid in pmids:
            progress_bar.set_description(f"Processing {pmid}")
            pmcid = _get_pmcid(pmid)
            if pmcid is None:
                click.secho(message=f"No PMCID found for {pmid}.", fg="yellow")
                progress_bar.update(1)
                continue
            download_pdf(pmcid, pmid, pdf_out_dir)
            progress_bar.update(1)
        progress_bar.set_description(f"Processing of {str(len(pmids))} PMIDs complete.")


if __name__ == "__main__":
    pmid_downloader()
