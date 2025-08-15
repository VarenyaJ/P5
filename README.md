# P5 - README
Prompt-driven Parsing of Prenatal PDFs to Phenopackets

**A local, end-to-end CLI pipeline for converting unstructured prenatal ultrasound reports (PDF and other formats) into GA4GH-compliant Phenopacket JSONs enriched with Human Phenotype Ontology (HPO) terms, citations, and reasoning. P5 combines PDF text extraction, prompt-driven large language model (LLM) parsing, and retrieval-augmented generation (RAG) to ensure high-fidelity phenotype annotation — all without relying on external cloud services.**

## Project Design & Goals

This project develops a local, secure, reproducible pipeline to transform unstructured prenatal ultrasound reports and raw ultrasound measurement data into structured, GA4GH-compliant Phenopacket JSONs enriched with:

* HPO terms for precise, ontology-driven phenotype descriptions
* Citations to relevant medical literature
* Reasoning traces to make annotations explainable and auditable

## Core Components

1. PDF text extraction — layout-aware parsing of vendor-generated PDFs (Observer, GE ViewPoint) and other document types to recover tabular measurements and free-text narratives.
2. Prompt-based LLM parsing — locally hosted large language models extract candidate phenotypes from clinical text.
3. Retrieval-Augmented Generation (RAG) — queries the Human Phenotype Ontology to verify, disambiguate, and enrich annotations.
4. Phenopacket assembly — outputs GA4GH v2-compliant JSON including subject metadata, phenotypic features, biosamples, and provenance.
5. Validation & evaluation — compares "experimental" phenopackets against curated ground-truth datasets to measure precision, recall, and F1-score.

## Why It Matters

* Automates phenotype curation tasks traditionally handled by genetic counselors and OBGYN/Pediatric specialists.
* Standardizes prenatal phenotype reporting for cases already paired with WES/WGS data.
* Enables the creation of federated genotype–phenotype repositories without relying on cloud-based NLP services, preserving patient privacy.

## Features

* Extract PMIDs from filenames to prepare for batch retrieval.
* Download PDFs from PubMed Central using Selenium.
* Parse & Normalize multi-format documents (PDF, DOCX, PPTX, HTML, TXT).
* LLM Conversion using local models for prompt-driven parsing.
* Dataset Assembly to align predicted and ground-truth phenopackets.
* Evaluate precision, recall, and F1 for phenotype extraction.

## Prerequisites

* Python ≥ 3.13
* Conda or Mamba (recommended)
* Chrome/Chromium for Selenium-based PDF downloads
* Local Ollama installation with chosen LLMs


## Install Conda
```bash
mkdir -p $HOME/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-<YOUR_SYSTEM>.sh -O $HOME/miniconda3/miniconda.sh
bash $HOME/miniconda3/miniconda.sh -b -u -p $HOME/miniconda3
#rm $HOME/miniconda3/miniconda.sh
source $HOME/.bashrc
source $HOME/miniconda3/bin/activate
conda init --all
conda --version
conda info
```


## Setup Conda (and optionally install Mamba)
```bash
# 1. Activate Conda for Shell
source $HOME/.bashrc && source $HOME/miniconda3/bin/activate && source $HOME/.bashrc && conda init --all && conda --version && conda info && conda list envs && which conda && conda --version

# 2. Setup Conda-Forge
conda update -n base -c defaults conda && conda install -n base -c conda-forge mamba conda-lock && conda list --show-channel-urls

# 3. Initialize conda
eval "$(conda shell.bash hook)" || echo 'no conda :('

# 4. OPTIONAL: Initialize mamba
eval "$(mamba shell hook --shell bash)" || echo 'no mamba :('
```

## Setup Project
```bash
cd $HOME
git clone https://github.com/VarenyaJ/P5.git
cd $HOME/P5/
git checkout main

# 1. Clear caches
conda clean --all -y
pip cache purge

# 2. Remove old env
conda deactivate
conda env remove -n p5 -y

# 3. Create new env
conda env create -f requirements/environment.yml -n p5 -y || mamba env create -f requirements/environment.yml -n p5

# 4. Validate smoke test
conda activate p5
python - <<EOF
import docling, selenium
print("OK:", type(docling), selenium.__version__)
EOF

# 4.5 Install and Verify Package
pip install -e .
python -c "import P5; print(P5.__version__)"
pull-git-files --help
create-pmid-pkl --help

pytest --maxfail=1 -q
```

# TODO:

### 5. Install lock tool & generate lock
```
conda install -n p5 -c conda-forge conda-lock -y || mamba install -n p5 -c conda-forge conda-lock -y
conda-lock lock -f requirements/environment.yml \
 -p linux-64 -p osx-64 -p osx-arm64
```

### Create lock
```bash
conda env create --yes -f requirements/environment.yml || mamba env create --yes -f requirements/environment.yml
conda-lock lock -f requirements/environment.yml -p linux-64 -p osx-64 -p win-64 --name p5
```

### Commit the generated lock files and update them via:
```bash
conda env update --yes -f requirements/environment.yml || mamba env update --yes -f requirements/environment.yml
conda-lock lock --update-lock-file
```

# Miniconda and Mamba Notes:
- Miniforge Repository: https://github.com/conda-forge/miniforge
- Mamba Repository: https://github.com/mamba-org/mamba
- Miniconda Installers from Anaconda:
  - https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
    - fe74721e1d17211a2d14acd9c6889948897dabaddcef7802196bb29c136d59e7
  - https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
    - 4152f260040d452bfe00c67ac6b429aec7ff3b98f62bab8abe4c468e98e51891
  - https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
    - 2ec6f7981770b3396a9ab426e07ac8ef5b12b4393aa2e4bcc984376fe3aa327e
  - https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    - 612af113b49db0368e2be41ac4d51b7088eebd5f31daeeb89f23fff8f920db58