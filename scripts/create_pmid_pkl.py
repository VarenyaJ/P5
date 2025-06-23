import click
import pickle

from utils import find_pmids


@click.command(
    help="""
This takes a directory as an input, searches for strings of the form PMID_{1-8 digits} among the file names
and writes those PMIDS to a .pkl file. 

PMID_DIRECTORY:            Directory whose file names will be searched for PMIDs
PKL_FILE_PATH:             The file path of the .pkl file which will contain those PMIDs as a set.
RECURSIVE DIR SEARCH:      If True then the search through PMID_directory looks through subdirectories.

Example:
assets/cases assets/pmids.pkl
"""
)
@click.argument("pmid_directory", type=click.Path(exists=True, dir_okay=True))
@click.argument(
    "pkl_file_path", type=click.Path(exists=False, file_okay=True, dir_okay=False)
)
@click.option("--recursive_dir_search", is_flag=True, default=False)
def create_pmid_pkl(
    pmid_directory: str, pkl_file_path: str, recursive_dir_search: bool
):

    pmid_set = find_pmids(pmid_directory, recursive_dir_search)
    click.secho(
        message=f"{len(pmid_set)} PMIDs found within {pmid_directory}", fg="green"
    )

    with open(pkl_file_path, "wb") as file:
        pickle.dump(pmid_set, file)


if __name__ == "__main__":
    create_pmid_pkl()
