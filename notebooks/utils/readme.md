# This directory provides small helper modules for working with GA4GH phenopackets in analysis notebooks.

---

## `phenopacket.py`

A minimal `Phenopacket` class to load, inspect, and query GA4GH Phenopacket JSON files generated elsewhere in this project.

### Features

- **Load from file**  
 ```python
 Phenopacket.load_from_file(path: str) -> Phenopacket
 Reads a JSON file from disk, validates it against the GA4GH schema via Protobuf,
 and returns a Phenopacket instance.
 ```
- **Count phenotypes**
 ```python
 pp.count_phenotypes  # int
 Returns the number of HPO-annotated features in the phenopacket.
 ```
- **List all phenotype labels**
 ```python
 pp.list_phenotypes() -> List[str]
 Returns a list of all human-readable HPO labels in the phenopacket.
 ```
- **Check for a specific phenotype**
 ```python
 pp.contains_phenotype(hpo_label: str) -> bool
 Returns True if any feature's type.label exactly matches hpo_label.
 ```
- **Export JSON**
 ```python
 pp.to_json() -> dict
 Returns a deep copy of the original JSON payload, so mutating the result won't
 affect the Phenopacket instance.
 ```

### Usage Example 

```python
from notebooks.utils.phenopacket import Phenopacket
```

**#1) Load a phenopacket JSON (e.g. created by scripts/file_to_phenopacket.py)**
```python
pp = Phenopacket.load_from_file("out_dir/PMID_1234567.json")
```

**#2) How many HPO terms did the model extract?**
```python
print(pp.count_phenotypes)
```

**#3) What are they?**
```python
print(pp.list_phenotypes())
```

**#4) Test for a particular phenotype by its human-readable label**
```python
if pp.contains_phenotype("Short stature"):
   print("Annotated with short stature")
else:
   print("No short stature annotation")
```

**#5) Get a copy of the raw JSON and modify it without affecting `pp`**
```python
data = pp.to_json()
data["phenotypicFeatures"].append({"type": {"id": "HP:9999999", "label": "Experimental"}})
print(pp.count_phenotypes)  # unchanged
```