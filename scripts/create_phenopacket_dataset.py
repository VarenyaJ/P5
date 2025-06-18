import os
import re
from collections import defaultdict
from os import walk
from typing import DefaultDict

import click
import pandas as pd

regex = r"\d{7}"


def _get_pmid_by_file_dir(directory: str, recursive: bool) -> defaultdict[str, list]:
    pmid_by_file_dir = DefaultDict(list)
    for file_path, _, file_names in walk(directory):
        if len(file_names) == 0 and recursive is False:
            return pmid_by_file_dir

        for file_name in file_names:
            matches = re.findall(regex, file_name)

            if len(matches) != 1:
                click.secho(
                    f"Warning: Found more than one PMID ({matches}) in {file_path}. ",
                    fg="yellow",
                    bold=True,
                )
                continue

            pmid_by_file_dir[matches[0]].append(
                f"{os.path.abspath(file_path)}/{file_name}"
            )

        if recursive is False:
            return pmid_by_file_dir

    return pmid_by_file_dir


@click.command(
    help="""Filters phenopacket files based on matching PMIDs between input and ground truth directories.

    Parameters
    ----------
    input_data_dir : str
        Path to the directory containing input phenopacket files.
    ground_truth_files_dir : str
        Path to the directory containing ground truth phenopacket files.
    dataset_out_dir : str
        Path to the output CSV file where the filtered dataset will be saved.
    recursive_input_dir : bool, optional
        If True, recursively scan `input_data_dir` for files. Defaults to False.
    recursive_ground_truth_dir : bool, optional
        If True, recursively scan `ground_truth_files_dir` for files. Defaults to False.

    Returns
    -------
    None
        The function writes the filtered data to a CSV file specified by `dataset_out_dir`.
    """
)
@click.argument("input_data_dir", type=click.Path(exists=True))
@click.argument("ground_truth_files_dir", type=click.Path(exists=True))
@click.argument("dataset_out_dir", type=click.Path())
@click.option("--recursive_input_dir", type=click.BOOL, default=False)
@click.option("--recursive_ground_truth_dir", type=click.BOOL, default=False)
def create_phenopacket_dataset(
    input_data_dir: str,
    ground_truth_files_dir: str,
    dataset_out_dir: str,
    recursive_input_dir: bool,
    recursive_ground_truth_dir: bool,
):
    input_data = _get_pmid_by_file_dir(input_data_dir, recursive_input_dir)
    ground_truth_data = _get_pmid_by_file_dir(
        ground_truth_files_dir, recursive_ground_truth_dir
    )

    matching_pmids = set(input_data.keys()).intersection(set(ground_truth_data.keys()))

    data = [
        [pmid, input_data[pmid], ground_truth_data[pmid]] for pmid in matching_pmids
    ]

    df = pd.DataFrame(data, columns=["pmid", "input", "truth"])
    df = df.explode(column="truth")
    df = df.explode(column="input")
    df.to_csv(dataset_out_dir, index=False)
