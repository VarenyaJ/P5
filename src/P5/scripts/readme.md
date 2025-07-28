# P5/scripts - README

## Overview

The `scripts/` directory provides Click-based CLI tools to build and assemble PubMed → Phenopacket datasets. Each script is a subcommand under a single entry point (`scripts/__main__.py`).

The scripts implement a data-processing pipeline that:
- **Clones or updates a remote Phenopacket repository**
- **Scans filenames for PMIDs and serializes them to a .pkl**
- **Downloads article PDFs from PubMed Central**
- **Builds a CSV mapping PMIDs to PDF paths to ground-truth Phenopacket JSONs**
- **(Future) Converts PDFs into LLM-generated Phenopacket JSON**

## Entry Point (`__main__.py`)

Defines a `@click.group()` called `cli`. Global flag `-v/--verbose` sets `logging.DEBUG`. Dynamically imports and registers:
- `pull_git_files`
- `create_pmid_pkl`
- `pmid_downloader`
- `create_phenopacket_dataset`
- `file_to_phenopacket`

Dispatches to the chosen subcommand.

## Scripts & Usage

### 1) pull_git_files

Clone or update a Git repo and extract a subdirectory:

```bash
python -m scripts pull_git_files \
OUT_DIR REPO_URL SUBDIR_PATH \
[--branch BRANCH] [--depth N] [--force]
```

To pull all the phenopackets from "phenopacket-store" run:

```shell
python -m pull_git_files "scripts/data/tmp/phenopacket_store" "https://github.com/monarch-initiative/phenopacket-store" "notebooks"
```

### 2) create_pmid_pkl
Scan filenames for `PMID_<digits>` patterns and dump to pickle:

```bash
python -m scripts create_pmid_pkl \
INPUT_DIR OUTPUT_PKL \
[--recursive]
```

To look at every filename in the directory *scripts/data/tmp/phenopacket_store/notebooks* for occurences of a filename containing a string of the form
"PMID_{1-8 digits}" and the add that PMID to the .pkl file *scripts/data/tmp/phenopacket_store/pmids.pkl*, run:

```shell
python -m create_pmid_pkl "scripts/data/tmp/phenopacket_store/notebooks" "scripts/data/tmp/phenopacket_store/pmids.pkl" "--recursive_dir_search"
```

### 3) pmid_downloader
Fetch PDFs from PubMed Central for PMIDs in a pickle:

```bash
python -m scripts pmid_downloader \
PKL_FILE PDF_OUTPUT_DIR MAX_DOWNLOADS
```

For every PMID in the .pkl file, to download the PDFs to the directory *scripts/data/tmp/phenopacket_store/pmid_pdfs* (i.e. whenever there is a valid PMCID), run:
 
```shell
python -m PMID_downloader "scripts/data/tmp/phenopacket_store/pmids.pkl" "scripts/data/tmp/phenopacket_store/pmid_pdfs" "0"
```

### create_phenopacket_dataset
Match PDFs to "ground truth" JSON and emit a CSV:

```bash
python -m scripts create_phenopacket_dataset \
PDF_DIR JSON_GT_DIR OUTPUT_CSV \
[--recursive-pdf] [--recursive-json]
```

To create a CSV file with columns *PMID, PMID PDF file path, and phenopacket file path*.

```shell
python -m scripts.create_phenopacket_dataset "scripts/data/tmp/phenopacket_store/pmid_pdfs" "scripts/data/tmp/phenopacket_store/notebooks" "scripts/data/tmp/PMID_PDF_Phenopacket_list_in_phenopacket_store.csv" --recursive_ground_truth_dir True
```

### <span style="color:orange">BELOW NOT CURRENTLY PART OF THE PIPELINE</span>

#### Create LLM output files <span style="color:orange">(DOES NOT EXIST YET... OUTPUT FILES = E.G. HPO TERMS OR PHENOPACKETS)</span>

Run: 
```shell
python -m scripts.llm_output "scripts/data/tmp/phenopacket_store/pmid_pdfs" "scripts/data/tmp/phenopacket_store/llm_output_dir"
```

Uses the script file_to_phenopacket to take every PDF in the folder and pmid_pdfs and outputs some sort of LLM generated response to files named PMID_1234567.something

#### File to Phenopacket Script
Make sure ollama is installed on your machine and your env. Start the server.
Then download the model of your choice via:
```shell
conda activate p5
python
>>> import ollama
>>> ollama.pull('<model_name>')
>>> exit()
```

If you successfully installed the model switch into the scripts directory and:
```shell 
python -m scripts.file_to_phenopacket "scripts/data/tmp/phenopacket_store/pmid_pdfs" "scripts/data/tmp/phenopacket_store/llm_jsons" "<prompt>" "<model_name>" --file-type .pdf
```

For example, you could run:
```shell 
python -m scripts.file_to_phenopacket "scripts/data/tmp/phenopacket_store/pmid_pdfs" "scripts/data/tmp/phenopacket_store/llm_jsons" "Please take this PubMed article, and for JUST ONE of the patients described in it, can you create me a valid Phenopacket in JSON format. Please make sure it is a valid JSON." "llama3.2:latest" --file-type .pdf
```
