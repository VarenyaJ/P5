import pathlib
import re
from os import walk
from typing import Union, Optional

import click

import pickle


def random_string() -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(5))
pmid_regex = re.compile(r"PMID_\d{1,8}")


def find_pmids(
    directory: Union[str, pathlib.Path], recursive: Optional[bool] = False
) -> set[str]:
    """Finds PubMed IDs (PMIDs) in filenames within a given directory.

    Parameters
    ----------
    directory : str or pathlib.Path
        The path to the directory to search for PMIDs.
    recursive : bool, optional
        If True, the search will include subdirectories. If False (default),
        only the top-level directory will be searched.

    Returns
    -------
    set of str
        A set of unique PMIDs found in the filenames, representing
        the PMIDs.

    Warnings
    --------
    UserWarning
        If a filename contains more than one PMID, a warning is
        printed.
    """
    pmids = set()

    for _, _, file_names in walk(directory):
        if len(file_names) == 0:
            if recursive is False:
                return pmids
            continue

        for filename in file_names:
            matches = re.findall(pmid_regex, filename)

            if len(matches) != 1:
                click.secho(
                    f"Warning: Found more than one PMID ({matches}) in {filename}. ",
                    fg="yellow",
                    bold=True,
                )
                continue

            pmids.add(matches[0])
        if recursive is False:
            return pmids

    return pmids


def set_to_pkl(input_set: set, pkl_file_path: str):
    """This function takes a set (e.g. created by the function find_pmids)
    and loads them into a .pkl file"""

    with open(pkl_file_path, "wb") as file:
        pickle.dump(input_set, file)


def pkl_to_set(pkl_file_path: str) -> set:
    """This function takes a .pkl file loaded with a set
    and returns a set object"""

    with open(pkl_file_path, "rb") as file:
        output_set = pickle.load(file)

    return output_set
