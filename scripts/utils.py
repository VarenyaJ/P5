import pathlib
import random
import re
import string
from os import walk
from typing import Union, Optional

import click


def random_string() -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(5))


def find_pmids(
    directory: Union[str, pathlib.Path], recursive: Optional[bool] = False
) -> set[str]:
    """Finds PubMed IDs (PMIDs) in filenames within a given directory.

    This function searches for 7-digit numbers in the filenames present in the
    specified directory. If `recursive` is True, it will traverse subdirectories
    as well. It expects each filename to contain at most one 7-digit number
    (assumed to be a PMID). A warning is issued if multiple 7-digit numbers are
    found in a single filename.

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
        A set of unique 7-digit strings found in the filenames, representing
        the PMIDs.

    Warnings
    --------
    UserWarning
        If a filename contains more than one 7-digit number, a warning is
        printed.
    """
    pmids = set()

    for _, _, file_names in walk(directory):
        if len(file_names) == 0:
            if recursive is False:
                return pmids
            continue

        for filename in file_names:
            matches = re.findall(r"PMID_\d{1,8}", filename)

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
