import requests
from Bio import Entrez
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import click

#This is for using the PubMed API. Don't upload your actual email to GitHub :)
Entrez.email = "your-email-here.de"

def pmid_list_maker(txt_file_path: str) -> list[str]:
    """This function takes the path of a .txt file with lines of the form PMID_1234567
    and returns a list of the form [1234567,...]"""

    pmid_list = []
    with open(txt_file_path, 'r') as file:
        for line in file:
            pmid_list.append(line[5:].rstrip())
    return pmid_list


def get_pmc_id(pmid: str) -> str
    """this function uses the PMID API to get a PMC ID from a PMID
    once we have a PMC ID we can use that to get the URL of a PDF
    """

    # Fetch links for the PubMed ID to find PMC ID
    handle = Entrez.elink(dbfrom="pubmed", db="pmc", id=pmid, linkname="pubmed_pmc")
    records = Entrez.read(handle)
    handle.close()

    linksets = records[0].get("LinkSetDb", [])
    if not linksets:
        return None
    pmc_id = linksets[0]["Link"][0]["Id"]
    return pmc_id

def download_pdf(pdf_url: str, pmid: str):
    """
    this takes the URL of the PDF on PMC
    uses Selenium to avoid anti-web-scraping JavaScript challenges
    and then downloads the PDF using requests
    we need to use the cookies of the Selenium browser and pause for 5 seconds to trick the webpage
    """

    try:
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

        response = response = session.get(final_pdf_url, headers=headers)
        with open(f"PMID_pdf_folder/{pmid}.pdf", 'wb') as f:
            f.write(response.content)
            print("PDF downloaded successfully.")
    except:
        print(f"An error occurred downloading PMID_{pmid}")

@click.command()
@click.argument(pmid_file_dir, type=click.Path(exists=True))
def PMID_downloader(pmid_file_dir: str):
    pmids = pmid_list_maker(pmid_file_dir)
    for pmid in pmids:
        print(f"Processing PMID {pmid}...")
        pmc_id = get_pmc_id(pmid)
        if not pmc_id:
            print(f"No PMC article found for PMID {pmid}")
            continue
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
        download_pdf(pdf_url, pmid)

if __name__ == "__main__":
    PMID_downloader()