import os
from unittest import mock

from click.testing import CliRunner
from docling.document_converter import DocumentConverter
from joblib.testing import skipif

from scripts.PMID_downloader import PMID_downloader
import pathlib
import tempfile

CI = bool(os.getenv("GITHUB_ACTIONS"))


@skipif(CI, reason="CI needs internet access for this test")
def test_PMID_downloader(request):

    dummy_pmid_file_path = str(
        pathlib.Path(request.path).parent.parent / "assets/scripts/dummyPMIDs.txt"
    )
    with open(dummy_pmid_file_path, "r") as file:
        dummy_pmids: list[str] = file.readlines()

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdirname:
        result = runner.invoke(
            PMID_downloader, [dummy_pmid_file_path, tmpdirname, "email@expert.com"]
        )

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        PDFs = [f for f in os.listdir(tmpdirname)]
        PDF_names = [f.split(".")[0] for f in os.listdir(tmpdirname)]
        dummy_PMID_names = [line.split("_")[1].rstrip() for line in dummy_pmids]
        assert sorted(dummy_PMID_names) == sorted(PDF_names)
        converter = DocumentConverter()
        for pdf in PDFs:
            converter.convert(f"{tmpdirname}/{pdf}")


@mock.patch("Bio.Entrez.read")
@mock.patch("Bio.Entrez.elink")
@mock.patch("scripts.PMID_downloader.time.sleep")
@mock.patch("scripts.PMID_downloader.webdriver.Chrome")
@mock.patch("scripts.PMID_downloader.requests.Session.get")
# @mock.patch("scripts.PMID_downloader.Options")
def test_PMID_downloader_mocked(
    mock_session_request,
    mock_chrome,
    mock_sleep,
    mock_entrez_elink,
    mock_entrez_read,
    request,
):

    mock_handle = mock.MagicMock()  # this is a fake file-like object
    mock_entrez_elink.return_value = mock_handle  # this ensures that Entrez.elink is not actually called and that handle is replaced with mock_handle
    mock_records = [
        {"LinkSetDb": [{"Link": [{"Id": "507429"}]}]}
    ]  # this is what we are replacing records with
    mock_entrez_read.return_value = mock_records  # this ensures that Entrez.read is not actually called and that records is replaced with mock_records. the structure of mock_records means that pmc_id will be "507429".

    mock_session_request.return_value.content = b"a9fa98dhv"

    runner = CliRunner()

    dummy_pmid_file_path = str(
        pathlib.Path(request.path).parent.parent / "assets/scripts/dummyPMIDs.txt"
    )
    with open(dummy_pmid_file_path, "r") as file:
        dummy_pmids: list[str] = file.readlines()

    with tempfile.TemporaryDirectory() as tmpdirname:
        result = runner.invoke(
            PMID_downloader, [dummy_pmid_file_path, tmpdirname, "email@expert.com"]
        )

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        PDFs = [f for f in os.listdir(tmpdirname)]
        PDF_names = [f.split(".")[0] for f in os.listdir(tmpdirname)]
        dummy_PMID_names = [line.split("_")[1].rstrip() for line in dummy_pmids]

        assert sorted(dummy_PMID_names) == sorted(
            PDF_names
        ), f"There failed to be a correspondence between PMIDs and PDFs in the temporary directory."
