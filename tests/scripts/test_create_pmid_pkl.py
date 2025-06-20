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

from scripts.create_pmid_pkl import create_pmid_pkl


@pytest.fixture()
def pmids_set():
    return {"PMID_8755636", "PMID_16636245"}


@mock.patch("scripts.utils.find_pmids")
def test_create_pmid_pkl(mock_find_pmids, pmids_set):
    """
    We mock find_pmids since there is already a test for it.
    """
    mock_find_pmids.return_value = pmids_set

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(create_pmid_pkl, [tmp_dir, tmp_dir + "tmp_pkl.pkl"])

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"
