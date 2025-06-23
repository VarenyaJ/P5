import os
import pytest

CI = bool(os.getenv("GITHUB_ACTIONS"))

@pytest.fixture()
def test_pmids() -> set:
    return {"PMID_8755636", "PMID_16636245"}