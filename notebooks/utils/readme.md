# notebooks/utils

This directory provides small helper modules for working with GA4GH phenopackets in analysis notebooks.

---

## `phenopacket.py`

A minimal `Phenopacket` class to load, inspect, and query phenopacket JSON files generated elsewhere in this project.

### Features

- **Load from file**  
 `Phenopacket.load(path: str) -> Phenopacket`  
 Reads a JSON file from disk and returns a `Phenopacket` instance.

- **Count phenotypes**  
 `pp.count_phenotypes -> int`  
 Returns the number of HPO-annotated features in the phenopacket.

- **Check for a specific phenotype**  
 `pp.contains_phenotype(hpo_label: str) -> bool`  
 Returns `True` if the phenopacket includes a phenotypic feature whose `type.label` matches `hpo_label`.

### Usage Example

```python
from notebooks.utils.phenopacket import Phenopacket

# 1) Load a phenopacket JSON (e.g. created by scripts/file_to_phenopacket.py):
pp = Phenopacket.load("out_dir/PMID_1234567.json")

# 2) How many HPO terms did the model extract?
print(pp.count_phenotypes)  

# 3) Test for a particular phenotype by its human-readable label:
if pp.contains_phenotype("Short stature"):
   print("Annotated with short stature")
else:
   print("No short stature annotation")