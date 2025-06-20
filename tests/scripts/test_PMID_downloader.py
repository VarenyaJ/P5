import os
import pathlib
import tempfile
from unittest import mock

import pytest
from click.testing import CliRunner
from docling.document_converter import DocumentConverter

from scripts.PMID_downloader import pmid_downloader

from scripts.utils import pkl_to_set

import pickle

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
def pmids_set():
    return {"PMID_8755636", "PMID_16636245"}


@pytest.fixture()
def pmids_no_pdf_set():
    return {"PMID_16636245", "PMID_19458539"}


@pytest.fixture()
def pmids_with_pdf_set():
    return {"PMID_8755636", "PMID_20089953"}


@pytest.mark.skipif(CI, reason="CI needs internet access for this test")
def test_pmid_downloader(pmids_set, request):
    """
    This tests that everything works when we pass in a .pkl file containing two PMIDS.
    One of the PMIDs (which is PMID_8755636) corresponds to a PMCID and so will generate a PDF.
    The other PMID does not correspond to a PMCID and so should not correspond to a PDF.
    """

    with tempfile.TemporaryDirectory() as tmp_dir:

        pmids_pkl_file_path = tmp_dir + "/dummy_pmids.pkl"

        # create the .pkl file from the fixture pmids_set above
        with open(pmids_pkl_file_path, "wb") as file:
            pickle.dump(pmids_set, file)

        output_dir = tmp_dir + "/output_pdfs"

        runner = CliRunner()
        result = runner.invoke(pmid_downloader, [pmids_pkl_file_path, output_dir])

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        pdf_file_names = {f for f in os.listdir(output_dir)}
        pdf_file_names_no_file_type = {f.split(".")[0] for f in os.listdir(output_dir)}
        expected_pmid_names = {"PMID_8755636"}

        assert pdf_file_names_no_file_type == expected_pmid_names
        converter = DocumentConverter()
        for pdf in pdf_file_names:
            converter.convert(f"{output_dir}/{pdf}")

        # asserts that each pdf is at least 1kb
        for pdf in pdf_file_names:
            # expected PDF has file size ≈ 204,000 bytes
            assert os.path.getsize(f"{output_dir}/{pdf}") >= 200000


@mock.patch("scripts.PMID_downloader.Entrez")
@mock.patch("scripts.PMID_downloader.time.sleep")
@mock.patch("scripts.PMID_downloader.webdriver.Chrome")
@mock.patch("scripts.PMID_downloader.requests.Session.get")
def test_PMID_downloader_with_pmcid_mocked(
    mock_session_request,
    mock_chrome,
    mock_sleep,
    mock_entrez,
    pdf_bytes,
    pmids_with_pdf_set,
    request,
):
    """
    This tests that everything works when we pass in a .pkl containing two PMIDs that correspond to PMCIDs.
    Entrez, Selenium and requests are mocked.
    """
    mock_entrez.read.return_value = [{"LinkSetDb": [{"Link": [{"Id": "507429"}]}]}]

    mock_session_request.return_value.content = pdf_bytes

    expected_pmids = pmids_with_pdf_set

    with tempfile.TemporaryDirectory() as tmp_dir:

        pmids_pkl_file_path = tmp_dir + "/dummy_pmids.pkl"

        # create the .pkl file from the fixture pmids_with_pdf_set above
        with open(pmids_pkl_file_path, "wb") as file:
            pickle.dump(pmids_with_pdf_set, file)

        output_dir = tmp_dir + "/output_pdfs"

        runner = CliRunner()
        result = runner.invoke(pmid_downloader, [pmids_pkl_file_path, output_dir])

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        pdf_file_names_no_file_type = {f.split(".")[0] for f in os.listdir(output_dir)}

        assert (
            expected_pmids == pdf_file_names_no_file_type
        ), f"There failed to be a correspondence between PMIDs and PDFs in the temporary directory."


@mock.patch("scripts.PMID_downloader.Entrez")
def test_PMID_downloader_no_pmcid_mocked(mock_entrez, pmids_no_pdf_set, request):
    """
    This tests that everything works when we pass in a .pkl containing two PMIDs that do NOT correspond to PMCIDs.
    In particular when we pass in the PMIDS contained in the file "assets/scripts/dummy_pmids_no_pmcid.pkl".
    Entrez is mocked.
    """

    mock_entrez.read.return_value = [
        {
            "LinkSetDb": [],
            "LinkSetDbHistory": [],
            "ERROR": [],
            "DbFrom": "pubmed",
            "IdList": ["16636245"],
        }
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:

        pmids_pkl_file_path = tmp_dir + "/dummy_pmids.pkl"

        # create the .pkl file from the fixture pmids_no_pdf_set above
        with open(pmids_pkl_file_path, "wb") as file:
            pickle.dump(pmids_no_pdf_set, file)

        output_dir = tmp_dir + "/output_pdfs"

        runner = CliRunner()
        result = runner.invoke(pmid_downloader, [pmids_pkl_file_path, output_dir])

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        assert (
            os.listdir(output_dir) == []
        ), "When running the test_PMID_downloader_no_pmcid_mocked test, the out directory unexpectedly contained a file."
