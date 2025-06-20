import os
import pathlib
import tempfile
from unittest import mock

import pytest

from click.testing import CliRunner
from docling.document_converter import DocumentConverter

from scripts.utils import pkl_to_set
from scripts.create_pmid_pkl import create_pmid_pkl


@pytest.fixture()
def pmids_set():
    return {"PMID_8755636", "PMID_16636245"}


@mock.patch("scripts.create_pmid_pkl.find_pmids")
def test_create_pmid_pkl(mock_find_pmids, pmids_set):
    """
    We mock find_pmids since there is already a test for it.
    """
    mock_find_pmids.return_value = pmids_set

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_pkl_path = tmp_dir + "/pickle.pkl"
        result = runner.invoke(create_pmid_pkl, [tmp_dir, output_pkl_path])

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        output_set = pkl_to_set(output_pkl_path)

        assert output_set == pmids_set
