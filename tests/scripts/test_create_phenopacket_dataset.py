import pathlib
import tempfile

import pandas as pd
import pytest
from click.testing import CliRunner

from scripts.create_phenopacket_dataset import create_phenopacket_dataset


@pytest.mark.parametrize(
    "recursive_input_dir, recursive_ground_truth_dir, expected_pmids, expected_n_pmids",
    [
        (True, True, ["PMID_7803799", "PMID_8800795"], 4),
        (True, False, list(), 0),
        (False, True, ["PMID_7803799", "PMID_8800795"], 4),
        (False, False, list(), 0),
    ],
)
def test_filter_phenopackets(
    recursive_input_dir, recursive_ground_truth_dir, expected_pmids, expected_n_pmids
):
    """
    Directory is construced as follows:
    tmp_dir
    ├── ground_truth
    │ ├── AAGAB
    │ │ └── phenopackets
    │ │     ├── PMID_7803799_0.json
    │ │     └── PMID_7803799_1.json
    │ ├── ACTB
    │ │ └── phenopackets
    │ │     ├── PMID_8800795_0.json
    │ │     └── PMID_8800795_1.json
    │ ├── ERF
    │ │ └── phenopackets
    │ │     ├── PMID_0000000_0.json
    │ │     └── PMID_0000000_1.json
    │ ├── FBLX4
    │ │ └── phenopackets
    │ │     ├── PMID_1111111_0.json
    │ │     └── PMID_1111111_1.json
    │ └── POT1
    │     └── phenopackets
    │         ├── NO_PUBMED_ID_0.json
    │         └── NO_PUBMED_ID_1.json
    ├── inputs
    │ ├── PMID_7803799.pdf
    │ └── PMID_8800795.pdf
    └── out_dir
    """
    random_file_dirs = ["AAGAB", "ACTB", "ERF", "FBLX4", "POT1"]
    pmids = ["PMID_7803799", "PMID_8800795"]
    not_matching_pmids = ["PMID_0000000", "PMID_1111111", "NO_PUBMED_ID"]

    with tempfile.TemporaryDirectory() as tmp_dir:
        inputs_dir = pathlib.Path(f"{tmp_dir}/inputs")
        inputs_dir.mkdir(parents=True, exist_ok=True)

        ground_truth_dir = pathlib.Path(f"{tmp_dir}/ground_truth")
        ground_truth_dir.mkdir(parents=True, exist_ok=True)

        out_dir = pathlib.Path(f"{tmp_dir}/out_dir")
        out_dir.mkdir(parents=True, exist_ok=True)

        for pmid in pmids:
            with open(f"{inputs_dir}/{pmid}.pdf", "w") as f:
                f.write("Test PMID")

        for i, pmid in enumerate(pmids + not_matching_pmids):
            save_dir = pathlib.Path(
                f"{ground_truth_dir}/{random_file_dirs[i]}/phenopackets"
            )
            save_dir.mkdir(parents=True, exist_ok=True)
            for file_number in range(2):
                with open(f"{save_dir}/{pmid}_{file_number}.json", "w") as f:
                    f.write("Test PMID")

        runner = CliRunner()
        result = runner.invoke(
            create_phenopacket_dataset,
            [
                str(inputs_dir),
                str(ground_truth_dir),
                str(out_dir / "phenopacket_df.csv"),
                "--recursive_input_dir",
                recursive_input_dir,
                "--recursive_ground_truth_dir",
                recursive_ground_truth_dir,
            ],
        )

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        phenopacket_df = pd.read_csv(out_dir / "phenopacket_df.csv")

        assert len(phenopacket_df) == expected_n_pmids
        assert sorted(phenopacket_df["pmid"].unique().tolist()) == sorted(
            expected_pmids
        )
