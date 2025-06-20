import os
import tempfile
from unittest import mock

import pytest
from click.testing import CliRunner
from docling.document_converter import DocumentConverter

from scripts.PMID_downloader import pmid_downloader

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


@pytest.fixture()
def pmids():
    return {"PMID_8755636", "PMID_16636245"}


@pytest.fixture()
def pmids_no_pdf():
    return {"PMID_16636245", "PMID_19458539"}


@pytest.fixture()
def pmids_with_pdf():
    return {"PMID_8755636", "PMID_20089953"}


@pytest.mark.skipif(CI, reason="CI needs internet access for this test")
@mock.patch("scripts.PMID_downloader.find_pmids")
def test_pmid_downloader(mock_find_pmids, pmids):
    """
    This is an integration test, testing the selenium integration.
    1. The first PMID corresponds to a PMCID and so will generate a PDF.
    2. The second PMID does not correspond to a PMCID and so should not correspond to a PDF.
    """
    mock_find_pmids.return_value = pmids

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(
            pmid_downloader,
            [
                tmp_dir,  # This Dir does not affect the test, but an existing need to be passed
                tmp_dir,
            ],
        )

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        pdf_file_names = [f for f in os.listdir(tmp_dir)]
        pdf_file_names_no_file_type = [f.split(".")[0] for f in os.listdir(tmp_dir)]
        expected_pmids = ["PMID_8755636"]

        assert pdf_file_names_no_file_type == expected_pmids

        converter = DocumentConverter()
        for pdf in pdf_file_names:
            converter.convert(f"{tmp_dir}/{pdf}")

        # asserts that each pdf is at least 1kb
        for pdf in pdf_file_names:
            # expected PDF has file size ≈ 204,000 bytes
            assert os.path.getsize(f"{tmp_dir}/{pdf}") >= 200000


@mock.patch("scripts.PMID_downloader.Entrez")
@mock.patch("scripts.PMID_downloader.time.sleep")
@mock.patch("scripts.PMID_downloader.webdriver.Chrome")
@mock.patch("scripts.PMID_downloader.requests.Session.get")
@mock.patch("scripts.PMID_downloader.find_pmids")
def test_PMID_downloader_with_pmcid_mocked(
    mock_find_pmids,
    mock_session_request,
    mock_chrome,
    mock_sleep,
    mock_entrez,
    pdf_bytes,
    pmids_with_pdf,
):
    """
    This tests that everything works when we pass in PMIDs that correspond to PMCIDs.
    """
    mock_find_pmids.return_value = pmids_with_pdf
    mock_entrez.read.return_value = [{"LinkSetDb": [{"Link": [{"Id": "507429"}]}]}]

    mock_session_request.return_value.content = pdf_bytes

    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(
            pmid_downloader,
            [
                tmp_dir,  # This Dir does not affect the test, but an existing need to be passed
                tmp_dir,
            ],
        )

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        pdf_names = [f.split(".")[0] for f in os.listdir(tmp_dir)]

        assert sorted(pmids_with_pdf) == sorted(
            pdf_names
        ), f"There failed to be a correspondence between PMIDs and PDFs in the temporary directory."


@mock.patch("scripts.PMID_downloader.Entrez")
@mock.patch("scripts.PMID_downloader.find_pmids")
def test_PMID_downloader_no_pmcid_mocked(mock_entrez, mock_find_pmids, pmids_no_pdf):
    """
    This tests that everything works when we pass in PMIDs that do not correspond to PMCIDs.
    """
    mock_find_pmids = pmids_no_pdf
    mock_entrez.read.return_value = [{}]

    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(
            pmid_downloader,
            [
                tmp_dir,  # This Dir does not affect the test, but an existing need to be passed
                tmp_dir,
            ],
        )

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        assert (
            os.listdir(tmp_dir) == []
        ), "When running the test_PMID_downloader_no_pmcid_mocked test, the out directory unexpectedly contained a file."
