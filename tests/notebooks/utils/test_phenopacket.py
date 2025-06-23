# P5/tests/notebooks/test_phenopacket.py

import json
import os
import tempfile

import pytest

from notebooks.utils.phenopacket import Phenopacket


@pytest.fixture
def sample_json_dict():
    """
    Build a minimal phenopacket dict with three phenotypes.
    """
    return {
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000001", "label": "Phenotype One"}},
            {"type": {"id": "HP:0000002", "label": "Phenotype Two"}},
            {"type": {"id": "HP:0000003", "label": "Phenotype Three"}},
        ]
    }


def test_init_and_count(sample_json_dict):
    """
    The Phenopacket should store the JSON and count phenotypes correctly.
    """
    pp = Phenopacket(sample_json_dict)
    assert pp.count_phenotypes == 3


def test_contains_phenotype_positive(sample_json_dict):
    """
    contains_phenotype should return True when the label is present.
    """
    pp = Phenopacket(sample_json_dict)
    assert pp.contains_phenotype("Phenotype Two") is True


def test_contains_phenotype_negative(sample_json_dict):
    """
    contains_phenotype should return False when the label is absent.
    """
    pp = Phenopacket(sample_json_dict)
    assert pp.contains_phenotype("Nonexistent Phenotype") is False


def test_load_and_file_not_found(sample_json_dict):
    """
    Phenopacket.load should raise FileNotFoundError for invalid paths,
    and should load correctly when the file exists.
    """
    # 1) non-existent path
    with pytest.raises(FileNotFoundError):
        Phenopacket.load("does_not_exist.json")

    # 2) write a temp file and load it
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "pp.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sample_json_dict, f)
        pp = Phenopacket.load(filepath)
        # loaded object should behave identically
        assert pp.count_phenotypes == 3
        assert pp.contains_phenotype("Phenotype Three")
