import requests
from Bio import Entrez
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import click

def load_PMIDs(txt_file_path: str) -> list[str]:
    """This function takes the path of a .txt file with lines of the form PMID_1234567
    and returns a list of the form [1234567,...]"""

    with open(txt_file_path, 'r') as file:
        pmid_list = [line.split(_)[1] for line in file]
    return pmid_list

def get_pmc_id(pmid: str, email_address: str) -> str
    """This function uses the PubMed API to get a PMC ID from a PMID.
    Once we have a PMC ID we can use that to get the URL of a PDF.
    """

    #This is for using the PubMed API
    Entrez.email = email_address

    # Fetch links for the PubMed ID to find PMC ID
    handle = Entrez.elink(dbfrom="pubmed", db="pmc", id=pmid, linkname="pubmed_pmc")
    records = Entrez.read(handle)
    handle.close()

    linksets = records[0].get("LinkSetDb", [])
    if not linksets:
        return None
    pmc_id = linksets[0]["Link"][0]["Id"]
    return pmc_id

def download_pdf(pmc_id: str,pmid: str,pdf_output_dir: str):
    """
    this takes a PMC_id of a PubMed article
    guesses the URL of the PDF
    uses Selenium to avoid anti-web-scraping JavaScript challenges
    and then downloads the PDF using requests
    we need to use the cookies of the Selenium browser and pause for 5 seconds to trick the webpage
    """

    try:
        #via guesswork, this is probably the URL of the PDF
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"

        # set up the Selenium browser
        options = Options()
        options.headless = True
        driver = webdriver.Chrome(options=options)

        # load the page and pause for 5 seconds
        driver.get(pdf_url)
        time.sleep(5)  # give time for JS challenge to complete

        # Get the actual PDF URL if redirected
        final_pdf_url = driver.current_url
        # Extract cookies set by the JS
        cookies = driver.get_cookies()
        driver.quit()

        # Now use requests with those cookies to get the real PDF
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])

        # Add headers to mimic a real browser
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            ),
            "Accept": "application/pdf",
            "Referer": "https://pmc.ncbi.nlm.nih.gov/"
        }

        response = session.get(final_pdf_url, headers=headers)
        with open(f"{pdf_output_dir}/{pmid}.pdf", 'wb') as f:
            f.write(response.content)
            print("PDF downloaded successfully.")
    except Exception as e:
        print(f"An error occurred when downloading PMID_{pmid} = PMC_{pmc_id}: {e}")

@click.command()
@click.argument("pmid_file_dir", type=click.Path(exists=True))
#presumably exists=True needs to be changed for the argument below?
@click.argument("pdf_output_dir", type=click.Path(exists=True))
@click.argument("email address [for PubMed API]", type=click.STRING)
def PMID_downloader(pmid_file_dir: str, pdf_output_dir: str, email_address: str):
    pmids = load_PMIDs(pmid_file_dir)
    for pmid in pmids:
        print(f"Processing PMID {pmid}...")
        pmc_id = get_pmc_id(pmid,email_address)
        if not pmc_id:
            print(f"No PMC article found for PMID {pmid}")
            continue
        download_pdf(pmc_id, pmid, pdf_output_dir)

if __name__ == "__main__":
    PMID_downloader()