"""
test_evaluation.py

Unit tests for PhenotypeEvaluator and its integration with Phenopacket.
Verifies TP/FP/FN counts, macro metrics, and classification report output.
"""

import json
import pytest
from pathlib import Path

from notebooks.utils.evaluation import PhenotypeEvaluator
from notebooks.utils.phenopacket import Phenopacket


@pytest.fixture
def phenopacket_path(tmp_path):
   """
   Write a minimal phenopacket JSON file with two HPO labels
   and return its file path.
   """
   data = {
       "phenotypicFeatures": [
           {"type": {"id": "HP:0000001", "label": "Phen1"}},
           {"type": {"id": "HP:0000002", "label": "Phen2"}},
       ]
   }
   path = tmp_path / "test.json"
   path.write_text(json.dumps(data), encoding="utf-8")
   return str(path)


def test_perfect_prediction_metadata(phenopacket_path):
   """
   When predictions exactly match ground truth,
   TP should be 2, FP and FN should be 0.
   """
   evaluator = PhenotypeEvaluator()
   ground_truth = Phenopacket.load_from_file(phenopacket_path)

   evaluator.check_phenotypes(["Phen1", "Phen2"], ground_truth)
   report = evaluator.report("alice", "exp1", "modelA")

   assert report.metadata["TP"] == 2
   assert report.metadata["FP"] == 0
   assert report.metadata["FN"] == 0


def test_perfect_prediction_metrics(phenopacket_path):
   """
   When predictions exactly match ground truth,
   precision, recall, and f1_score should all be 1.0.
   """
   evaluator = PhenotypeEvaluator()
   ground_truth = Phenopacket.load_from_file(phenopacket_path)

   evaluator.check_phenotypes(["Phen1", "Phen2"], ground_truth)
   metrics = evaluator.report("alice", "exp1", "modelA").metrics

   assert metrics["precision"] == pytest.approx(1.0)
   assert metrics["recall"]    == pytest.approx(1.0)
   assert metrics["f1_score"]  == pytest.approx(1.0)


def test_perfect_prediction_classification_report(phenopacket_path):
   """
   The classification_report output should include 'present' and 'absent' labels.
   """
   evaluator = PhenotypeEvaluator()
   ground_truth = Phenopacket.load_from_file(phenopacket_path)

   evaluator.check_phenotypes(["Phen1", "Phen2"], ground_truth)
   report_text = evaluator.report("alice", "exp1", "modelA").classification_report

   assert "present" in report_text
   assert "absent" in report_text


def test_false_positive_and_miss(phenopacket_path):
   """
   One true positive and one false positive yields TP=1, FP=1, FN=1,
   and macro metrics of 0.5.
   """
   evaluator = PhenotypeEvaluator()
   ground_truth = Phenopacket.load_from_file(phenopacket_path)

   evaluator.check_phenotypes(["Phen1", "Fake"], ground_truth)
   report = evaluator.report("bob", "exp2", "modelB")
   metrics = report.metrics

   assert report.metadata["TP"] == 1
   assert report.metadata["FP"] == 1
   assert report.metadata["FN"] == 1

   assert metrics["precision"] == pytest.approx(0.5, rel=1e-6)
   assert metrics["recall"]    == pytest.approx(0.5, rel=1e-6)
   assert metrics["f1_score"]  == pytest.approx(0.5, rel=1e-6)


def test_multiple_batches(phenopacket_path, tmp_path):
   """
   After two batches (one true-positive/miss, one true-positive/false-positive),
   total TP=2, FP=1, FN=1 and macro metrics of 2/3.
   """
   evaluator = PhenotypeEvaluator()

   # First batch: one correct, one missed
   ground_truth1 = Phenopacket.load_from_file(phenopacket_path)
   evaluator.check_phenotypes(["Phen1"], ground_truth1)

   # Second batch: one correct, one false positive
   data2 = {"phenotypicFeatures": [{"type": {"id": "HP:0000001", "label": "Phen1"}}]}
   p2 = tmp_path / "test2.json"
   p2.write_text(json.dumps(data2), encoding="utf-8")
   ground_truth2 = Phenopacket.load_from_file(str(p2))
   evaluator.check_phenotypes(["Phen1", "Extra"], ground_truth2)

   report = evaluator.report("carol", "exp3", "modelC")
   metadata = report.metadata
   metrics = report.metrics

   assert metadata["TP"] == 2
   assert metadata["FP"] == 1
   assert metadata["FN"] == 1

   assert metrics["precision"] == pytest.approx(2/3, rel=1e-6)
   assert metrics["recall"]    == pytest.approx(2/3, rel=1e-6)
   assert metrics["f1_score"]  == pytest.approx(2/3, rel=1e-6)