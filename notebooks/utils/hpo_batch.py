"""
notebooks/utils/hpo_batch.py

Batch LLM HPO extraction:
- iterates aligned (pmid, input_path, patient_id) triples
- calls the single-case extractor
- saves raw model output and a minimal predicted Phenopacket JSON
- returns wrapped Phenopacket utils for downstream evaluation

Dependencies:
  - notebooks.utils.hpo_extraction
  - the `phenopacket.Phenopacket` utility
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional
import logging

from notebooks.utils.hpo_extraction import (
    extract_hpo_terms,
    build_minimal_phenopacket_from_hpo_list,
)
from phenopacket import Phenopacket as UtilPhenopacket

logger = logging.getLogger(__name__)


# -----------------------------
# Data structures
# -----------------------------
@dataclass
class BatchOutcome:
    pmid: str
    patient_id: str
    raw_output_path: Optional[str] = None
    predicted_json_path: Optional[str] = None
    predicted_packet_util: Optional[UtilPhenopacket] = None
    error_message: Optional[str] = None


@dataclass
class BatchInferenceResult:
    successful_outcomes: List[BatchOutcome] = field(default_factory=list)
    failed_outcomes: List[BatchOutcome] = field(default_factory=list)

    def total_successes(self) -> int:
        return len(self.successful_outcomes)

    def total_failures(self) -> int:
        return len(self.failed_outcomes)


@dataclass
class BatchDirectories:
    raw_dir: str
    json_dir: str


# -----------------------------
# Helpers
# -----------------------------
def _persist_raw_text(directory: str, pmid: str, raw_text: str) -> str:
    os.makedirs(directory, exist_ok=True)
    out_path = os.path.join(directory, f"{pmid}__raw.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(raw_text)
    return out_path


def _persist_json(directory: str, pmid: str, patient_id: str, packet_json: dict) -> str:
    os.makedirs(directory, exist_ok=True)
    out_path = os.path.join(directory, f"{pmid}__{patient_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(packet_json, f, indent=2)
    return out_path


def _load_clinical_text(file_path: str) -> str:
    """
    Lightweight loader for clinical text:
    - .txt files are read directly (and optional leading '[text]' is stripped)
    - other extensions are treated as PDF and converted to text via docling
    """
    if file_path.lower().endswith(".txt"):
        with open(file_path, encoding="utf-8") as f:
            text = f.read()
        return text.split("[text]")[-1]
    else:
        from docling.document_converter import DocumentConverter, ConversionError
        from pypdfium2._helpers.misc import PdfiumError

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")
        try:
            converter = DocumentConverter()
            doc = converter.convert(file_path)
            return doc.document.export_to_text()
        except (ConversionError, PdfiumError) as e:
            raise RuntimeError(
                f"Could not convert PDF to text ({os.path.basename(file_path)}): {e}"
            )


# -----------------------------
# Core processing
# -----------------------------
def _process_single_case(
    list_of_pmids_aligned: List[str],
    list_of_input_paths_aligned: List[str],
    list_of_patient_ids_aligned: List[str],
    case_index: int,
    total_cases: int,
    directories: BatchDirectories,
    model_name: str,
    write_raw: bool,
    write_json: bool,
    debug_logging: bool,
) -> BatchOutcome:
    """Process one case; split out to reduce complexity in the main driver."""
    pmid = list_of_pmids_aligned[case_index - 1]
    input_path = list_of_input_paths_aligned[case_index - 1]
    patient_id = list_of_patient_ids_aligned[case_index - 1]

    if debug_logging:
        logger.debug(
            "[batch] (%d/%d) PMID=%s | patient_id=%s",
            case_index,
            total_cases,
            pmid,
            patient_id,
        )

    clinical_text_for_case = _load_clinical_text(input_path)
    if debug_logging:
        logger.debug("[batch] text length=%d chars", len(clinical_text_for_case))

    items, raw_model_text = extract_hpo_terms(
        clinical_text=clinical_text_for_case,
        model=model_name,
        return_raw_model_text=True,
        debug_logging=debug_logging,
    )

    outcome = BatchOutcome(pmid=pmid, patient_id=patient_id)

    if write_raw:
        raw_output_path = _persist_raw_text(directories.raw_dir, pmid, raw_model_text)
        outcome.raw_output_path = raw_output_path
        if debug_logging:
            logger.debug("[batch] wrote raw model text → %s", raw_output_path)

    predicted_packet_json = build_minimal_phenopacket_from_hpo_list(
        patient_id=patient_id, hpo_list=items
    )
    predicted_packet_util = UtilPhenopacket(predicted_packet_json)
    outcome.predicted_packet_util = predicted_packet_util

    if write_json:
        predicted_json_path = _persist_json(
            directories.json_dir, pmid, patient_id, predicted_packet_json
        )
        outcome.predicted_json_path = predicted_json_path
        if debug_logging:
            logger.debug("[batch] wrote predicted JSON → %s", predicted_json_path)

    return outcome


def run_hpo_batch_inference(  # reduced complexity by delegating to _process_single_case
    list_of_pmids_aligned: List[str],
    list_of_input_paths_aligned: List[str],
    list_of_patient_ids_aligned: List[str],
    directory_for_raw_llm_outputs: str,
    directory_for_predicted_jsons: str,
    ollama_model_name: str,
    sleep_seconds_between_cases: float = 0.0,
    write_raw_model_text: bool = True,
    write_predicted_json: bool = True,
    debug_logging: bool = False,
) -> BatchInferenceResult:
    """
    Execute HPO extraction across all aligned cases and persist artifacts.
    Returns:
        BatchInferenceResult with per-case success/failure records.
    """
    dirs = BatchDirectories(
        raw_dir=directory_for_raw_llm_outputs, json_dir=directory_for_predicted_jsons
    )
    os.makedirs(dirs.raw_dir, exist_ok=True)
    os.makedirs(dirs.json_dir, exist_ok=True)

    batch_result = BatchInferenceResult()

    total_cases = len(list_of_pmids_aligned)
    if not (
        len(list_of_input_paths_aligned)
        == total_cases
        == len(list_of_patient_ids_aligned)
    ):
        raise ValueError(
            "Aligned inputs differ in length — ensure pmids, input paths, and patient ids are aligned 1:1."
        )

    for case_index in range(1, total_cases + 1):
        try:
            outcome = _process_single_case(
                list_of_pmids_aligned,
                list_of_input_paths_aligned,
                list_of_patient_ids_aligned,
                case_index,
                total_cases,
                dirs,
                ollama_model_name,
                write_raw_model_text,
                write_predicted_json,
                debug_logging,
            )
            batch_result.successful_outcomes.append(outcome)

        except (RuntimeError, OSError, ValueError) as err:  # capture and continue
            pmid = list_of_pmids_aligned[case_index - 1]
            patient_id = list_of_patient_ids_aligned[case_index - 1]
            outcome = BatchOutcome(pmid=pmid, patient_id=patient_id)
            outcome.error_message = str(err)
            batch_result.failed_outcomes.append(outcome)
            logger.warning("[batch] Failed prediction for PMID %s: %s", pmid, err)

        if sleep_seconds_between_cases > 0:
            time.sleep(sleep_seconds_between_cases)

    if debug_logging:
        logger.debug(
            "[batch] Completed: successes=%d failures=%d",
            batch_result.total_successes(),
            batch_result.total_failures(),
        )

    return batch_result
