#!/usr/bin/env python3
"""
phenopacket_store_dataset_setup.py
Utility to bootstrap the phenopacket-store dataset for the demo pipeline (clone → index → download PDFs → build CSV).

Stages:
  1) Fresh-clone phenopacket-store's "notebooks" folder into:
       <src_folder>/P5/scripts/data/tmp/phenopacket_store/notebooks
  2) Create a pickle of PMIDs discovered in those notebooks (recursive).
  3) Download PDFs for those PMIDs into:
       <src_folder>/P5/scripts/data/tmp/phenopacket_store/pmid_pdfs
  4) Build the CSV mapping PDFs -> ground-truth phenopacket JSONs (if missing).

Designed to be imported from the demo notebook AFTER running
`notebooks/utils/demonstration_directory_creation.py`, which sets up:
  - project_root
  - src_folder
  - experimental_data_root
  - pdf_input_directory
  - ground_truth_notebooks_directory
  - dataset_csv_path
  - llm_output_directory
  - validated_jsons_directory
  - evaluation_report_output_path

We can also run this as a standalone script via CLI.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess, logging

logger = logging.getLogger(__name__)


def setup_phenopacket_store_dataset(
    src_folder: str,
    pdf_input_directory: str,
    ground_truth_notebooks_directory: str,
    dataset_csv_path: str,
    max_pdfs_to_download: int = 0,
) -> str:
    """
    Run the four setup stages and return the absolute path to the generated pmids.pkl.

    Parameters
    ----------
    src_folder : str
        Absolute path to our repo's "src" directory (already on PYTHONPATH).
    pdf_input_directory : str
        Destination directory for downloaded PDFs.
    ground_truth_notebooks_directory : str
        Destination directory for cloned phenopacket-store notebooks.
    dataset_csv_path : str
        Output CSV path mapping PMIDs to (PDF, ground-truth phenopacket JSON).
    max_pdfs_to_download : int, default 0
        How many PDFs to download (0 = no limit).

    Returns
    -------
    str
        Absolute path to pmids.pkl (the list of PMIDs discovered).
    """

    # -------------------------------------------------------------------------
    # Compute canonical locations used by the helper scripts
    # -------------------------------------------------------------------------
    phenopacket_store_root_dir = os.path.join(
        src_folder, "P5", "scripts", "data", "tmp", "phenopacket_store"
    )
    pmids_pickle_path = os.path.join(
        src_folder, "P5", "scripts", "data", "tmp", "pmids.pkl"
    )

    # Ensure parent folders exist
    os.makedirs(phenopacket_store_root_dir, exist_ok=True)
    os.makedirs(os.path.dirname(pmids_pickle_path), exist_ok=True)
    os.makedirs(pdf_input_directory, exist_ok=True)
    os.makedirs(os.path.dirname(dataset_csv_path), exist_ok=True)

    # -------------------------------------------------------------------------
    # Stage 0: Clean the ground-truth notebooks dir to ensure a fresh clone
    # (empirically avoids cases where git can't overwrite an existing directory)
    # -------------------------------------------------------------------------
    logger.info("[Stage 0] Preparing ground-truth notebooks directory for a fresh clone...")
    target_notebooks_dir = os.path.join(phenopacket_store_root_dir, "notebooks")
    if os.path.exists(target_notebooks_dir):
        logger.info("  - Removing existing directory: %s", target_notebooks_dir)
        shutil.rmtree(target_notebooks_dir)

    # -------------------------------------------------------------------------
    # Stage 1: Clone phenopacket-store notebooks
    # -------------------------------------------------------------------------
    logger.info("[Stage 1] Cloning 'phenopacket-store' notebooks...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "P5.scripts.pull_git_files",
            phenopacket_store_root_dir,
            "https://github.com/monarch-initiative/phenopacket-store.git",
            "notebooks",
        ],
        check=True,
    )
    logger.info(f"[Stage 1] Complete. Produced: {ground_truth_notebooks_directory}")

    # -------------------------------------------------------------------------
    # Stage 2: Discover PMIDs in the cloned notebooks and persist to pmids.pkl
    # -------------------------------------------------------------------------
    logger.info("[Stage 2] Scanning notebooks for PMIDs and creating pmids.pkl...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "P5.scripts.create_pmid_pkl",
            os.path.join(phenopacket_store_root_dir, "notebooks"),
            pmids_pickle_path,
            "--recursive_dir_search",
        ],
        check=True,
    )
    logger.info("  - Stage 2 Complete.")

    # -------------------------------------------------------------------------
    # Stage 3: Download PDFs for those PMIDs into pdf_input_directory
    # -------------------------------------------------------------------------
    logger.info("[Stage 3] Downloading PDFs for discovered PMIDs...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "P5.scripts.pmid_downloader",
            pmids_pickle_path,
            pdf_input_directory,
            str(max_pdfs_to_download),
        ],
        check=True,
    )
    logger.info("  - Stage 3 Complete.")

    # -------------------------------------------------------------------------
    # Stage 4: Build the CSV mapping PDFs -> ground-truth phenopacket JSONs
    # (only if it does not already exist)
    # -------------------------------------------------------------------------
    logger.info("[Stage 4] Building dataset CSV (if missing)...")
    if not os.path.isfile(dataset_csv_path):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "P5.scripts.create_phenopacket_dataset",
                pdf_input_directory,
                ground_truth_notebooks_directory,
                dataset_csv_path,
                "--recursive_ground_truth_dir",
                "True",
            ],
            check=True,
        )
        logger.info("  - Created dataset CSV at: %s", dataset_csv_path)
        logger.info("  - Stage 4 Complete.")
    else:
        logger.info("  - Skipping: dataset CSV already exists at: %s", dataset_csv_path)


    # -------------------------------------------------------------------------
    # Final sanity prints
    # -------------------------------------------------------------------------
    if os.path.isdir(pdf_input_directory):
        logger.info("Summary of created/verified paths:")
        logger.info("  - PDF inputs folder:             %s", pdf_input_directory)
        logger.info("  - Ground truth folder:           %s", ground_truth_notebooks_directory)
        logger.info("  - Dataset CSV path:              %s", dataset_csv_path)
    else:
        logger.error("PDF input directory not found:    %s", pdf_input_directory)


    return pmids_pickle_path


# -----------------------------------------------------------------------------
# Optional CLI usage
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Bootstrap phenopacket-store dataset for the demo pipeline."
    )
    parser.add_argument(
        "--src-folder", required=True, help="Absolute path to the repo's 'src' folder."
    )
    parser.add_argument(
        "--pdf-input-dir", required=True, help="Directory to store downloaded PDFs."
    )
    parser.add_argument(
        "--ground-truth-notebooks-dir",
        required=True,
        help="Directory where phenopacket-store notebooks are cloned.",
    )
    parser.add_argument(
        "--dataset-csv-path",
        required=True,
        help="Output CSV mapping PMIDs to (PDF, ground-truth JSON).",
    )
    parser.add_argument(
        "--max-pdfs", type=int, default=0, help="Max PDFs to download (0 = unlimited)."
    )

    args = parser.parse_args()

    returned_pmids_pkl = setup_phenopacket_store_dataset(
        src_folder=args.src_folder,
        pdf_input_directory=args.pdf_input_dir,
        ground_truth_notebooks_directory=args.ground_truth_notebooks_dir,
        dataset_csv_path=args.dataset_csv_path,
        max_pdfs_to_download=args.max_pdfs,
    )
    logger.info("PMIDs pickle created at: %s", returned_pmids_pkl)
