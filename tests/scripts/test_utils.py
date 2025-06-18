import pathlib
import random
import string
import tempfile

import pytest

from scripts.utils import find_pmids


@pytest.fixture()
def pmids():
    return {"7803799", "8800795"}


@pytest.mark.parametrize(
    "recursive, expected_pmids", [(True, ["7803799", "8800795"]), (False, [])]
)
def test_find_pmids(recursive: bool, expected_pmids: list[str], pmids: set[str]):
    packet_dirs = [
        "".join(random.choice(string.ascii_letters) for _ in range(5)) for _ in pmids
    ]
    with tempfile.TemporaryDirectory() as tmp_dir:
        for i, pmid in enumerate(pmids):
            save_dir = pathlib.Path(f"{tmp_dir}/{packet_dirs[i]}/phenopackets")
            save_dir.mkdir(parents=True, exist_ok=True)
            for n_sub_dirs in range(2):
                with open(f"{save_dir}/{pmid}_{n_sub_dirs}.json", "w") as f:
                    f.write("Test PMID")

        found_pmids = find_pmids(tmp_dir, recursive=recursive)

        assert set(expected_pmids) == found_pmids


def test_find_pmids_recursive(pmids: set[str]):
    with tempfile.TemporaryDirectory() as tmp_dir:
        for i, pmid in enumerate(pmids):
            save_dir = pathlib.Path(f"{tmp_dir}/{pmid}.json")
            with open(save_dir, "w") as f:
                f.write("Test PMID")

        found_pmids = find_pmids(tmp_dir, recursive=True)

        assert pmids == found_pmids
