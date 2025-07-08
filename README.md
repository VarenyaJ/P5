# P5
Prompt-driven Parsing of Prenatal PDFs to Phenopackets

* adapted from https://github.com/VarenyaJ/P5/tree/exp/prioritize-conda

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
+
## Setup Project
```bash
cd $HOME
git clone https://github.com/VarenyaJ/P5.git
cd $HOME/P5/
git checkout exp/prioritize-conda

# 1. Clear caches
conda clean --all -y
pip cache purge

# 2. Remove old env
conda deactivate
conda env remove -n p5 -y

# 3. Create new env
conda env create -f requirements/environment.yml -n p5 || mamba env create -f requirements/environment.yml -n p5

# 4. Validate smoke test
conda activate p5
python - <<EOF
import docling, selenium
print("OK:", type(docling), selenium.__version__)
EOF

pytest --maxfail=1 -q
```
+
# TODO:

### 5. Install lock tool & generate lock
```
conda install -n p5 -c conda-forge conda-lock -y || mamba install -n p5 -c conda-forge conda-lock -y
conda-lock lock -f requirements/environment.yml \
 -p linux-64 -p osx-64 -p osx-arm64
```
+
### Create lock
```bash
conda env create --yes -f requirements/environment.yml || mamba env create --yes -f requirements/environment.yml
conda-lock lock -f requirements/environment.yml -p linux-64 -p osx-64 -p win-64 --name p5
```
+
Commit the generated lock files and update them via:
```bash
conda env update --yes -f requirements/environment.yml || mamba env update --yes -f requirements/environment.yml
conda-lock lock --update-lock-file
```
