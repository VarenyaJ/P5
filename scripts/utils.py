import pathlib
import random
import re
import string
from os import walk
from typing import Union

import click


def random_string() -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(5))


def find_pmids(
    directory: Union[str, pathlib.Path], recursive: bool = False
) -> list[str]:
    pmids = []

    for _, _, file_names in walk(directory):
        if len(file_names) == 0:
            if recursive is False:
                return []
            continue

        for filename in file_names:
            matches = re.findall(r"\d{7}", filename)

            if len(matches) != 1:
                click.secho(
                    f"Warning: Found more than one PMID ({matches}) in {filename}. ",
                    fg="yellow",
                    bold=True,
                )
                continue

            pmids.append(matches[0])
    if recursive is False:
        return pmids

    return pmids
