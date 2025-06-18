from typing import Optional

import requests
from Bio import Entrez
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import click

from pathlib import Path

from tqdm import tqdm


def _load_PMIDs(pmid_file_path: str) -> list[str]:
    """This function takes the path of a .txt file with lines of the form PMID_1234567
    and returns a list of the form [1234567,...]"""

    with open(pmid_file_path, "r") as file:
        pmid_list = [line.split("_")[1].rstrip() for line in file]
    return pmid_list


def _get_pmcid(pmid: str) -> Optional[str]:
    """This function uses the PubMed API called Entrez to get a PMCID from a PMID.
    Once we have a PMCID we can use that to get the URL of a PDF.
    """

    Entrez.email = "fake.email@email.de"

    with Entrez.elink(
        dbfrom="pubmed", db="pmc", id=pmid, linkname="pubmed_pmc"
    ) as handle:
        records = Entrez.read(handle)

    linksets = records[0].get("LinkSetDb", [])
    if linksets == []:
        return None
    pmcid = linksets[0]["Link"][0]["Id"]
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

        # set up the Selenium browser. The --headless argument means the Chrome browser does not pop up.
        # TODO ChatGPT says that to make headless work on windows, \
        #  some other arguments might need to be added. \
        #  I did not add them, because currently we would have no way of testing it.
        options = Options()
        options.add_argument("--headless")

        with webdriver.Chrome(options=options) as driver:
            # load the page and pause for 5 seconds
            driver.get(pdf_url)
            time.sleep(2)  # give time for JS challenge to complete

            # Get the actual PDF URL if redirected
            final_pdf_url = driver.current_url
            # Extract cookies set by the JS
            cookies = driver.get_cookies()

        # Now use requests with those cookies to get the real PDF
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie["name"], cookie["value"])

        # TODO make this less Mac-specific
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
Takes a .txt file containing lines of the form PMID_1234567 
and outputs a directory containing the corresponding PDFs of the journal articles 
(whenever they are accessible via PubMed Central).

PMID_FILE_PATH:     where the .txt file is located
PDF_OUTPUT_DIR:     where you want the directory containing the PDFs to be located

Example: 
data/pmid_list.txt      data/pmid_pdfs, 
"""
)
@click.argument("pmid_file_path", type=click.Path(exists=True))
@click.argument("pdf_out_dir", type=click.Path(exists=False, dir_okay=True))
def PMID_downloader(pmid_file_path: str, pdf_out_dir: str):

    pdf_out_dir_path = Path(pdf_out_dir)
    if not pdf_out_dir_path.exists():
        pdf_out_dir_path.mkdir(exist_ok=True, parents=True)

    pmids = _load_PMIDs(pmid_file_path)
    no_of_pmids = len(pmids)

    with tqdm(total=no_of_pmids) as progress_bar:
        for pmid in pmids:
            progress_bar.set_description(f"Processing PMID_{pmid}")
            pmcid = _get_pmcid(pmid)
            if pmcid is None:
                click.secho(message=f"No PMCID found for PMID_{pmid}.", fg="yellow")
                progress_bar.update(1)
                continue
            download_pdf(pmcid, pmid, pdf_out_dir)
            progress_bar.update(1)
        progress_bar.set_description(
            f"Processing of {str(no_of_pmids)} PMIDs complete."
        )


if __name__ == "__main__":
    PMID_downloader()
