"""
pmid_downloader.py

CLI to fetch PDFs from PubMed Central (PMC) given a pickle (.pkl) of PMIDs ("PMID_1234567").

Workflow:
1) Map PMID → PMCID using NCBI Entrez ELink (`pubmed` → `pmc`).
2) Guess the PMC PDF URL and load it with Selenium (headless) to satisfy possible JS/cookie gating.
3) Reuse Selenium cookies with `requests` to download the PDF to disk.

Resilience & maintenance:
- `_get_pmcid` retries on transient NCBI 5xx errors with backoff+jitter and returns `None` on failure
  (we *skip* that PMID instead of failing the run).
- We set `Entrez.email` (and optionally `Entrez.api_key`) from env so users can configure it
  without editing code (NCBI request etiquette).
- Selenium/Requests exceptions are caught and logged with `click.secho`; the loop continues.
"""

import click
import os
import requests
import time
from Bio import Entrez
from pathlib import Path
import random
from requests.exceptions import InvalidSchema
from selenium import webdriver
from selenium.common import InvalidSessionIdException
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm
from typing import Optional
from urllib.error import HTTPError, URLError

from P5.scripts.utils import pkl_loader

# before calling Entrez.* anywhere
Entrez.email = os.environ.get("NCBI_EMAIL", "fake.email@email.de")
# optionally:
# Entrez.api_key = os.environ.get("NCBI_API_KEY")


def _get_pmcid(pmid: str) -> Optional[str]:
    """
    Resolve a PMID string like 'PMID_1234567' to a PMCID (digits as a string), or None if not found.
    Retries a few times on HTTP 5xx from NCBI with exponential backoff + jitter.
    Returns None on persistent or non-retryable errors so callers can skip gracefully.
    """
    pmid_num = pmid.split("_")[-1]
    retries = 4
    for i in range(retries):
        try:
            with Entrez.elink(dbfrom="pubmed", db="pmc", id=pmid_num, linkname="pubmed_pmc") as handle:
                records = Entrez.read(handle)
            link_sets_db = records[0].get("LinkSetDb", [])
            if not link_sets_db:
                return None
            return link_sets_db[0]["Link"][0]["Id"]
        except HTTPError as e:
            # # Retry only on 5xx; 4xx usually indicates a permanent issue.; otherwise give up.
            if 500 <= getattr(e, "code", 0) < 600:
                # exponential backoff with jitter
                delay = (1.5 ** i) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            return None
        except (URLError, Exception):
            # Network hiccup or unexpected parse—treat as non-fatal for this PMID.
            return None
    return None


def download_pdf(pmcid: str, pmid: str, pdf_out_dir: str):
    """
    Download the PMC PDF for a given PMCID to `pdf_out_dir` as '<PMID>.pdf'.

    Steps
    -----
    1. Build an expected PMC PDF URL: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/
    2. Use headless Chrome to pass any JS challenges and collect cookies.
    3. Use `requests.Session` with those cookies + desktop UA headers to fetch the PDF bytes.

    - Selenium is used only to acquire cookies; the actual download is done by `requests`.
    - Exceptions are caught and logged; callers should continue iterating.
    """
    try:
        # Likely PDF location on PMC. Selenium may be redirected to the canonical file URL.
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"

        # Set up a headless browser. The `--headless=new` arg keeps UI from popping up.
        # TODO: Additional arguments needed to implement headless and test for other OS's
        options = Options()
        options.add_argument("--headless=new")

        with webdriver.Chrome(options=options) as driver:
            driver.get(pdf_url)
            time.sleep(4)  # allow time for any JS/cookie challenge to resolve

            # If we were redirected to the real PDF URL, grab it here.
            final_pdf_url = driver.current_url
            # Extract cookies set by the site; we’ll replay them with requests.
            cookies = driver.get_cookies()

        # Replay Selenium cookies with requests to download the PDF.
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie["name"], cookie["value"])

        # TODO test on other OS's using different user agents
        # Basic desktop UA & referer to look like an interactive browser.
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
                message=f"A PDF for {pmid} was successfully downloaded. PMCID={pmcid}.", fg="green"
            )

    except (InvalidSessionIdException, FileNotFoundError, IOError, InvalidSchema) as e:
        # Keep going—log and move on so a single bad article doesn't sink the whole batch.
        click.secho(
            message=f"An error occurred when downloading {pmid} = PMC_{pmcid}: {e}",
            err=True,
            fg="red",
        )


@click.command(
    help="""
INPUT: a .pkl file whose entries are strings of the form "PMID_1234567" 
OUTPUT: a directory containing the corresponding PDFs of the journal articles (whenever they are accessible via PubMed Central).

PKL_FILE_PATH:      the file path for the .pkl file
PDF_OUTPUT_DIR:     directory to dump the PDFs
DL_CUT_OFF:         the maximum number of PDFs to download (0 = all)

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

    pmid_batch: set = set(list(all_pmids)[:dl_cut_off])  # entries of the form "PMID_1234567"

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
