## Setup Project with Conda
+
### Create & lock environment
```bash
mamba env create --yes -f requirements/environment.yml
conda-lock lock -f requirements/environment.yml -p linux-64 -p osx-64 -p win-64 --name p5
```
+
Commit the generated lock files and update them via:
```bash
mamba env update --yes -f requirements/environment.yml
conda-lock lock --update-lock-file
```