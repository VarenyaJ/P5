"""
Test suite for `P5.scripts.pmid_downloader`.

Covers three main scenarios:

1. **Integration test (network required, skipped in CI)**  
   - Runs the CLI against real PubMed Central.  
   - Verifies that a PMID with a valid PMCID yields a PDF, while a PMID without a PMCID yields nothing.  
   - Ensures the PDF parses with `docling` and is of a reasonable size.

2. **Mocked positive case**  
   - Entrez is mocked to always return a PMCID.  
   - Selenium and requests are mocked, with requests returning a minimal valid PDF (`pdf_bytes`).  
   - Verifies that one JSON file per PMID is produced with correct names.

3. **Mocked negative case**  
   - Entrez is mocked to return no PMCID links.  
   - Verifies the downloader exits cleanly but produces no output files.

Fixtures:
- `pdf_bytes`: minimal valid PDF for mocking.  
- `test_pmids_with_pdf`: PMIDs that should yield PDFs under mocks.  
- `test_pmids_no_pdf`: PMIDs that should yield no PDFs under mocks.

These tests together ensure both the real downloader path and its mocked fallback
logic behave correctly, handling both success and failure cases robustly.
"""

import os
import tempfile
from unittest import mock

import pytest
from click.testing import CliRunner
from docling.document_converter import DocumentConverter

from P5.scripts.pmid_downloader import pmid_downloader

import pickle

# Flag to skip tests that require live internet access when running in CI
CI = bool(os.getenv("GITHUB_ACTIONS"))


@pytest.fixture()
def pdf_bytes() -> bytes:
    """
    Returns a minimal but valid PDF binary sequence.

    Used in the mocked `requests.Session.get` path so that the downloader
    writes a syntactically correct PDF file. `docling` is not invoked in this
    case — the test only validates that a PDF-like file is written.
    """
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
def test_pmids_with_pdf() -> set:
    """
    Fixture: PMIDs that are expected to resolve to valid PMCIDs in the mocked test.

    Both values in this set will produce PDFs when the downloader runs under mocks.
    """
    return {"PMID_8755636", "PMID_20089953"}


@pytest.fixture()
def test_pmids_no_pdf() -> set:
    """
    Fixture: PMIDs that are expected NOT to resolve to PMCIDs in the mocked test.

    Both values in this set will yield no output PDFs when the downloader runs.
    """
    return {"PMID_16636245", "PMID_19458539"}


@pytest.mark.skipif(CI, reason="CI needs internet access for this test")
def test_pmid_downloader(test_pmids, request):
    """
    Integration test (requires network access).

    - Creates a temporary .pkl file containing two PMIDs.
    - One PMID (8755636) corresponds to a PMCID and should yield a PDF.
    - The other PMID should NOT yield a PDF.
    - Verifies:
        • CLI exits with code 0
        • Exactly one PDF was written
        • The PDF is parseable by docling
        • PDF size is above a sanity threshold (~200 KB)
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        pmids_pkl_file_path = tmp_dir + "/dummy_pmids.pkl"

        # Write the fixture PMIDs to a temporary pickle file
        with open(pmids_pkl_file_path, "wb") as file:
            pickle.dump(test_pmids, file)

        output_dir = tmp_dir + "/output_pdfs"

        runner = CliRunner()
        result = runner.invoke(pmid_downloader, [pmids_pkl_file_path, output_dir, "0"])

        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"

        pdf_file_names = {f for f in os.listdir(output_dir)}
        pdf_file_names_no_file_type = {f.split(".")[0] for f in os.listdir(output_dir)}
        expected_pmid_names = {"PMID_8755636"}

        assert pdf_file_names_no_file_type == expected_pmid_names

        # Verify the file parses as a PDF
        converter = DocumentConverter()
        for pdf in pdf_file_names:
            converter.convert(f"{output_dir}/{pdf}")

        # Size sanity check (real PubMed PDFs are typically ~200 KB+)
        min_valid_pdf_bytes = 200000
        for pdf in pdf_file_names:
            assert os.path.getsize(f"{output_dir}/{pdf}") >= min_valid_pdf_bytes


@mock.patch("P5.scripts.pmid_downloader.Entrez")
@mock.patch("P5.scripts.pmid_downloader.time.sleep")
@mock.patch("P5.scripts.pmid_downloader.webdriver.Chrome")
@mock.patch("P5.scripts.pmid_downloader.requests.Session.get")
def test_pmid_downloader_with_pmcid_mocked(
    mock_session_request,
    mock_chrome,
    mock_sleep,
    mock_entrez,
    pdf_bytes,
    test_pmids_with_pdf,
    request,
):
    """
    Unit test with mocks for a positive case.

    - Entrez is mocked to return a PMCID for every PMID.
    - requests is mocked to return `pdf_bytes` as content.
    - Selenium is mocked so no real browser is started.
    - Verifies:
        • CLI exits with code 0
        • Output PDFs are created for each input PMID
    """
    mock_entrez.read.return_value = [{"LinkSetDb": [{"Link": [{"Id": "507429"}]}]}]
    mock_session_request.return_value.content = pdf_bytes

    expected_pmids = test_pmids_with_pdf

    with tempfile.TemporaryDirectory() as tmp_dir:
        pmids_pkl_file_path = tmp_dir + "/dummy_pmids.pkl"

        with open(pmids_pkl_file_path, "wb") as file:
            pickle.dump(test_pmids_with_pdf, file)

        output_dir = tmp_dir + "/output_pdfs"

        runner = CliRunner()
        result = runner.invoke(pmid_downloader, [pmids_pkl_file_path, output_dir, "0"])

        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"

        pdf_file_names_no_file_type = {f.split(".")[0] for f in os.listdir(output_dir)}
        assert (
            expected_pmids == pdf_file_names_no_file_type
        ), "There failed to be a correspondence between PMIDs and PDFs in the temporary directory."


@mock.patch("P5.scripts.pmid_downloader.Entrez")
def test_pmid_downloader_no_pmcid_mocked(mock_entrez, test_pmids_no_pdf, request):
    """
    Unit test with mocks for a negative case.

    - Entrez is mocked to return no PMCID links for the input PMIDs.
    - Verifies:
        • CLI exits with code 0
        • No PDFs are written to the output directory
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

        with open(pmids_pkl_file_path, "wb") as file:
            pickle.dump(test_pmids_no_pdf, file)

        output_dir = tmp_dir + "/output_pdfs"

        runner = CliRunner()
        result = runner.invoke(pmid_downloader, [pmids_pkl_file_path, output_dir, "0"])

        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"

        assert os.listdir(output_dir) == [], (
            "When running test_pmid_downloader_no_pmcid_mocked, "
            "the output directory unexpectedly contained a file."
        )
