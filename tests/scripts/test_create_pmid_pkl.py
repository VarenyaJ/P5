import os
import pathlib
import tempfile
from unittest import mock

import pytest

from click.testing import CliRunner
from docling.document_converter import DocumentConverter

from scripts.utils import pkl_loader
from scripts.create_pmid_pkl import create_pmid_pkl


@mock.patch("scripts.create_pmid_pkl.find_pmids")
def test_create_pmid_pkl(mock_find_pmids, test_pmids):

    mock_find_pmids.return_value = test_pmids

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_pkl_path = tmp_dir + "/pickle.pkl"
        result = runner.invoke(create_pmid_pkl, [tmp_dir, output_pkl_path])

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        output_set = pkl_loader(output_pkl_path)

        assert output_set == test_pmids
