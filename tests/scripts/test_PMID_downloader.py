import os
from unittest import mock

import pytest
from click.testing import CliRunner
from docling.document_converter import DocumentConverter

from scripts.PMID_downloader import pmid_downloader
import pathlib
import tempfile

CI = bool(os.getenv("GITHUB_ACTIONS"))


@pytest.fixture()
def pdf_bytes():
    return (
        b"%PDF-1.2\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 250 50] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 51 >>\nstream\n"
        b"BT /F1 20 Tf 72 20 Td (TEST) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n"
        b"0 6\n"
        b"0000000000 65535 f \n"
        b"0000000010 00000 n \n"
        b"0000000060 00000 n \n"
        b"0000000113 00000 n \n"
        b"0000000230 00000 n \n"
        b"0000000317 00000 n \n"
        b"trailer\n<< /Root 1 0 R /Size 6 >>\nstartxref\n401\n%%EOF"
    )

#FIX THIS CODE!
@pytest.mark.skipif(CI, reason="CI needs internet access for this test")
def test_pmid_downloader(request):
    """
    This tests that everything works when we pass in a file containing two PMIDS.
    The first PMID corresponds to a PMCID and so will generate a PDF.
    The second PMID does not correspond to a PMCID and so should not correspond to a PDF.
    They are contained in the file "assets/scripts/dummy_pmids.txt".
    """
    dummy_pmid_dir = str(
        pathlib.Path(request.path).parent.parent / "assets/scripts/dummy_pmid_dir"
    )
    with open(dummy_pmids_file_path, "r") as file:
        dummy_pmids: list[str] = file.readlines()

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdirname:
        result = runner.invoke(pmid_downloader, [dummy_pmid_dir, tmpdirname])

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        pdf_file_names = [f for f in os.listdir(tmpdirname)]
        pdf_file_names_no_file_type = [f.split(".")[0] for f in os.listdir(tmpdirname)]
        expected_pmid_name = "8755636"

        assert pdf_file_names_no_file_type == expected_pmid_name

        converter = DocumentConverter()
        for pdf in pdf_file_names:
            converter.convert(f"{tmpdirname}/{pdf}")

        # asserts that each pdf is at least 1kb
        for pdf in pdf_file_names:
            # expected PDF has file size ≈ 204,000 bytes
            assert os.path.getsize(f"{tmpdirname}/{pdf}") >= 200000


@mock.patch("Bio.Entrez.read")
@mock.patch("Bio.Entrez.elink")
@mock.patch("scripts.PMID_downloader.time.sleep")
@mock.patch("scripts.PMID_downloader.webdriver.Chrome")
@mock.patch("scripts.PMID_downloader.requests.Session.get")
def test_PMID_downloader_with_pmcid_mocked(
    mock_session_request,
    mock_chrome,
    mock_sleep,
    mock_entrez_elink,
    mock_entrez_read,
    pdf_bytes,
    request,
):
    """
    This tests that everything works when we pass in PMIDs that correspond to PMCIDs.
    In particular when we pass in the PMIDS contained in the file "assets/scripts/dummy_pmids_with_pmcid.txt".
    Entrez, Selenium and requests  are mocked.
    """

    mock_entrez_elink.return_value = mock.MagicMock()
    mock_entrez_read.return_value = [{"LinkSetDb": [{"Link": [{"Id": "507429"}]}]}]

    # This is the raw bytes of a tiny PDF which just contains the word TEST
    mock_session_request.return_value.content = pdf_bytes

    runner = CliRunner()

    dummy_pmids_file_path = str(
        pathlib.Path(request.path).parent.parent
        / "assets/scripts/dummy_pmids_with_pmcid.txt"
    )
    with open(dummy_pmids_file_path, "r") as file:
        dummy_pmids: list[str] = file.readlines()

    with tempfile.TemporaryDirectory() as tmpdirname:
        result = runner.invoke(pmid_downloader, [dummy_pmids_file_path, tmpdirname])

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        PDF_names = [f.split(".")[0] for f in os.listdir(tmpdirname)]
        expected_PMID_names = [line.split("_")[1].rstrip() for line in dummy_pmids]

        assert sorted(expected_PMID_names) == sorted(
            PDF_names
        ), f"There failed to be a correspondence between PMIDs and PDFs in the temporary directory."


@mock.patch("Bio.Entrez.read")
@mock.patch("Bio.Entrez.elink")
def test_PMID_downloader_no_pmcid_mocked(mock_entrez_elink, mock_entrez_read, request):
    """
    This tests that everything works when we pass in PMIDs that do not correspond to PMCIDs.
    In particular when we pass in the PMIDS contained in the file "assets/scripts/dummy_pmids_no_pmcid.txt".
    Entrez is mocked.
    """

    mock_entrez_elink.return_value = mock.MagicMock()
    mock_entrez_read.return_value = [{}]

    runner = CliRunner()

    dummy_pmids_file_path = str(
        pathlib.Path(request.path).parent.parent
        / "assets/scripts/dummy_pmids_no_pmcid.txt"
    )

    with tempfile.TemporaryDirectory() as tmpdirname:
        result = runner.invoke(pmid_downloader, [dummy_pmids_file_path, tmpdirname])

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        assert (
            os.listdir(tmpdirname) == []
        ), "When running the test_PMID_downloader_no_pmcid_mocked test, the out directory unexpectedly contained a file."
