import pathlib
import tempfile

import pandas as pd
from click.testing import CliRunner

from scripts.filter_phenopackets import create_phenopacket_dataset


def test_filter_phenopackets():
    random_file_dirs = ["AAGAB", "ACTB", "ERF", "FBLX4", "POT1"]
    expected_pmids = [7803799, 8800795]
    additional_pmids = ["0000000", "1111111", "NO_PUBMED_ID"]

    with tempfile.TemporaryDirectory() as tmp_dir:
        inputs_dir = pathlib.Path(f"{tmp_dir}/inputs")
        inputs_dir.mkdir(parents=True, exist_ok=True)

        ground_truth_dir = pathlib.Path(f"{tmp_dir}/ground_truth")
        ground_truth_dir.mkdir(parents=True, exist_ok=True)

        out_dir = pathlib.Path(f"{tmp_dir}/out_dir")
        out_dir.mkdir(parents=True, exist_ok=True)

        for pmid in expected_pmids:
            with open(f"{inputs_dir}/{pmid}.pdf", "w") as f:
                f.write("Test PMID")

        for i, pmid in enumerate(expected_pmids + additional_pmids):
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
                "--recursive_ground_truth_dir",
                True,
            ],
        )

        assert (
            result.exit_code == 0
        ), f"CLI exited with code {result.exit_code}: {result.output}"

        phenopacket_df = pd.read_csv(out_dir / "phenopacket_df.csv")

        assert len(phenopacket_df) == 4
        assert sorted(phenopacket_df["pmid"].unique().tolist()) == sorted(
            expected_pmids
        )
