import click
import pickle
from scripts.utils import find_pmids


@click.command(
    help="""
This takes a directory as an input, searches for strings of the form PMID_{1-8 digits} among the file names
and writes those PMIDS to a .pkl file. 

PMID_DIRECTORY:            The directory where you want to search for PMIDs among the file names.
PKL_FILE_PATH:             The file path of the .pkl file which will contain those PMIDs as a set.
RECURSIVE DIR SEARCH:      If True then the search through PMID_directory looks through subdirectories.

Example:
assets/cases assets/pmids.pkl
"""
)
@click.argument("pmid_directory", type=click.Path(exists=True, dir_okay=True))
@click.argument("pkl_file_path", type=click.Path(exists=False))
# @click.argument("recursive_dir_search", type=click.BOOL, default=True)
def create_pmid_pkl(pmid_directory: str, pkl_file_path: str):
    print("hello")
    pmid_set = find_pmids(pmid_directory, True)

    with open(pkl_file_path, "wb") as file:
        pickle.dump(pmid_set, file)


if __name__ == "__main__":
    create_pmid_pkl()
