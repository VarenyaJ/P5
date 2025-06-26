import json
import tempfile

import pytest

from notebooks.utils.phenopacket import Phenopacket, InvalidPhenopacketError


@pytest.fixture
def sample_json() -> dict:
    """
    Provide a minimal but valid Phenopacket JSON dict for testing.

    The dict contains exactly three entries under "phenotypicFeatures",
    each with a "type" sub-dict including "id" and "label".

    Returns
    -------
    dict
        A minimal Phenopacket JSON structure.
    """
    return {
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000001", "label": "Phenotype One"}},
            {"type": {"id": "HP:0000002", "label": "Phenotype Two"}},
            {"type": {"id": "HP:0000003", "label": "Phenotype Three"}},
        ]
    }


def test_load_from_file(sample_json):
    """
    Ensure `load_from_file` can read and validate a Phenopacket JSON file.

    This test writes `sample_json` to a temporary file, loads it via
    `Phenopacket.load_from_file`, and checks that the resulting instance
    contains the expected number of phenotypic features.

    Parameters
    ----------
    sample_json : dict
        The fixture providing a valid Phenopacket dictionary.

    Asserts
    -------
    assert pp.count_phenotypes == 3
    """
    # Write the sample JSON to disk
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as f:
        json.dump(sample_json, f)
        tmp_path = f.name

    # Load and validate
    pp = Phenopacket.load_from_file(tmp_path)
    assert pp.count_phenotypes == 3


@pytest.mark.parametrize(
    "bad_input",
    [
        [],  # not a dict
        "just a string",  # wrong top-level type
        123,  # wrong top-level type
        {"phenotypicFeatures": "foo"},  # features must be a list
    ],
)
def test_invalid_structure_raises(bad_input):
    """
    Verify that invalid inputs raise InvalidPhenopacketError.

    Each `bad_input` exercises a different validation failure path:
      - non-dict top level,
      - `phenotypicFeatures` not a list.

    Parameters
    ----------
    bad_input : Any
        A malformed JSON payload to pass to the constructor.

    Asserts
    -------
    Raises InvalidPhenopacketError for each malformed input.
    """
    with pytest.raises(InvalidPhenopacketError):
        Phenopacket(bad_input)
    #


#
