# P5/notebooks/utils - README

# Phenopacket Validation, Evaluation & Reporting

A comprehensive suite of utility modules for validating GA4GH Phenopackets, evaluating HPO term predictions, and generating detailed reports. This project provides a complete workflow for phenotypic data analysis and evaluation.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Utility Modules](#utils)
- [Running the Test Suite](#testing)
- [Putting It All Together](#workflow)
  - [Example Usage of Modules](#usage)
    * [phenopacket.py](#phenopacketpy)
    * [report.py](#reportpy)
    * [evaluation.py](#evaluationpy)

## Overview

This document provides a suite of utility modules for validating GA4GH Phenopackets, evaluating HPO term predictions against ground truth data, and generating comprehensive reports. The core components are:

- **`phenopacket.py`**: Validates and parses Phenopacket JSON data, providing a convenient interface for accessing phenotypic information.
- **`report.py`**: Computes precision, recall, F1 score, and generates classification reports based on evaluation results.
- **`evaluation.py`**: Accumulates true positive, false positive, and false negative counts when comparing predicted HPO labels to ground truth Phenopackets.

---

## Features

- GA4GH Phenopacket validation
- HPO term prediction evaluation
- Comprehensive reporting with metrics
- Modular design for easy integration
- Error handling and validation
- JSON serialization support

## Installation

```bash
# Create virtual environment (recommended)
# This is an example of using venv. Please refer to the main README for the Conda setup
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install ...
```

## Utility Modules

### 1. phenopacket.py

This module provides tools for working with GA4GH Phenopackets in JSON format. It validates the structure of the input data and offers methods for accessing phenotypic information.

Key Classes:
- `Phenopacket`: Represents a Phenopacket, encapsulating the parsed JSON data.
- `InvalidPhenopacketError`: Exception raised when the input JSON does not conform to the Phenopacket schema.

Key Methods:
- `load_from_file(filepath)`: Loads a Phenopacket from a JSON file.
- `contains_phenotype(term)`: Checks if the Phenopacket contains a specific HPO term.
- `list_phenotypes()`: Returns a list of all phenotype labels in the Phenopacket.
- `to_json()`: Returns a deep copy of the original JSON data, preventing external modifications.

Example Usage:
```python
from notebooks.utils.phenopacket import Phenopacket, InvalidPhenopacketError
try:
    pp = Phenopacket.load_from_file("path/to/your/phenopacket.json")
    print(f"Phenopacket contains HP:0000001: {pp.contains_phenotype('HP:0000001')}")
    print(f"Number of phenotypes: {pp.count_phenotypes}")
except InvalidPhenopacketError as e:
    print(f"Error loading Phenopacket: {e}")
```

### 2. report.py

This module computes evaluation metrics and generates reports based on the results of a comparison between predicted and true labels.

Key Classes:
- `Report`: Represents an evaluation report, storing metrics and metadata.

Key Methods:
- `get_metrics()`: Calculates precision, recall, F1 score, and other relevant metrics.
- `save(filepath)`: Saves the report to a JSON file.
- `load(filepath)`: Loads a report from a JSON file.

Example Usage:
```python
from notebooks.utils.report import Report
# Create a report (example data)
report_data = {"true_positives": 10, "false_positives": 2, "false_negatives": 3}
report = Report(**report_data)
# Print the summary
print(f"Report Summary: {report.get_summary()}")
# Save the report to a file
report.save("path/to/your/report.json")
# Load the report from a file
loaded_report = Report.load("path/to/your/report.json")
print(f"Loaded Report Summary: {loaded_report.get_summary()}")
```

### 3. evaluation.py

This module ties together predicted HPO labels and ground truth Phenopackets to accumulate true positive, false positive, and false negative counts.

Key Classes:
- `PhenotypeEvaluator`: Accumulates evaluation counts across multiple samples.

Key Methods:
- `check_phenotypes(experimentally_extracted_phenotypes, ground_truth_phenotypes)`: Updates internal counts based on a comparison of predicted and true phenotypes.
- `report(creator, experiment, model, **metadata_extra)`: Constructs and returns a Report summarizing all counts.

Example Usage:
```python
from notebooks.utils.evaluation import PhenotypeEvaluator, Report
from notebooks.utils.phenopacket import Phenopacket
# Load ground truth and predicted phenopackets
ground_truth_pp = Phenopacket.load_from_file("path/to/ground_truth.json")
predicted_pp = Phenopacket.load_from_file("path/to/predictions.json")
# Create an evaluator
evaluator = PhenotypeEvaluator()
# Iterate over samples and accumulate metrics (example)
evaluator.check_phenotypes(predicted_pp.list_phenotypes(), ground_truth_pp.list_phenotypes())
# Dump a final report
final_report = evaluator.report(creator="Your Name", experiment="HPO Prediction", model="LLM")
print(f"Final Report Summary: {final_report.get_summary()}")
```

## Running the Test Suite

To run the tests for this project, navigate to the notebooks/utils directory and execute:
```bash
pytest .
```

## Putting It All Together

Here's a typical workflow demonstrating how to combine these modules:

1. Validate Phenopackets: Load both ground truth and predicted phenopackets using phenopacket.py and handle potential InvalidPhenopacketError exceptions.
2. Predict HPO Terms: (This step is assumed to be done elsewhere, generating the predicted_pp).
3. Evaluate and Accumulate Results: Create a PhenotypeEvaluator instance, iterate over samples (or use the entire phenopackets), and call check_phenotypes() to accumulate TP/FP/FN counts.
4. Generate and Save a Final Report: Call report() on the evaluator to create a Report instance, and then save it to a JSON file using save().```

### Usage

Here's a complete example showing how to use all modules together:

```python
from notebooks.utils.evaluation import PhenotypeEvaluator
from notebooks.utils.phenopacket import Phenopacket
from notebooks.utils.report import Report

# Load ground truth and predicted phenopackets
ground_truth_pp = Phenopacket.load_from_file("path/to/ground_truth.json")
predicted_pp = Phenopacket.load_from_file("path/to/predictions.json")

# Create evaluator
evaluator = PhenotypeEvaluator()

# Evaluate predictions
evaluator.check_phenotypes(predicted_pp.list_phenotypes(), ground_truth_pp)

# Generate report
final_report = evaluator.report(
    creator="Your Name",
    experiment="HPO Prediction",
    model="LLM",
    notes="Batch evaluation"
)

# Save report
final_report.save("evaluation_results.json")
```