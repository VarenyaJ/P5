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

from notebooks.utils.hpo_extraction import (
    extract_hpo_terms,
    build_minimal_phenopacket_from_hpo_list,
)
from phenopacket import Phenopacket as UtilPhenopacket


@dataclass
class SingleCaseOutcome:
    pmid: str
    patient_id: str
    input_path: str
    raw_output_path: Optional[str] = None
    predicted_json_path: Optional[str] = None
    predicted_packet_util: Optional[UtilPhenopacket] = None
    error_message: Optional[str] = None


@dataclass
class BatchInferenceResult:
    successful_outcomes: List[SingleCaseOutcome] = field(default_factory=list)
    failed_outcomes: List[SingleCaseOutcome] = field(default_factory=list)

    def total_successes(self) -> int:
        return len(self.successful_outcomes)

    def total_failures(self) -> int:
        return len(self.failed_outcomes)


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


def run_hpo_batch_inference(
    list_of_pmids_aligned: List[str],
    list_of_input_paths_aligned: List[str],
    list_of_patient_ids_aligned: List[str],
    directory_for_raw_llm_outputs: str,
    directory_for_predicted_jsons: str,
    ollama_model_name: str = "llama3.2:latest",
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
    os.makedirs(directory_for_raw_llm_outputs, exist_ok=True)
    os.makedirs(directory_for_predicted_jsons, exist_ok=True)

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

    for case_index, (pmid, input_path, patient_id) in enumerate(
        zip(
            list_of_pmids_aligned,
            list_of_input_paths_aligned,
            list_of_patient_ids_aligned,
        ),
        start=1,
    ):
        if debug_logging:
            print(
                f"[batch] ({case_index}/{total_cases}) PMID={pmid} | patient_id={patient_id}"
            )

        outcome = SingleCaseOutcome(
            pmid=pmid, patient_id=patient_id, input_path=input_path
        )

        try:
            # 1) Load/convert clinical text
            clinical_text_for_case = _load_clinical_text(input_path)
            if debug_logging:
                print(f"[batch] text length={len(clinical_text_for_case)} chars")

            # 2) Extract HPO terms via LLM
            predicted_terms_for_case, raw_model_text = extract_hpo_terms(
                clinical_text=clinical_text_for_case,
                model=ollama_model_name,
                return_raw_model_text=True,
                debug_logging=debug_logging,
            )

            # 3) Persist raw model text (optional)
            if write_raw_model_text:
                raw_filename = f"{pmid}__raw.txt"
                raw_output_path = os.path.join(
                    directory_for_raw_llm_outputs, raw_filename
                )
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write(raw_model_text)
                outcome.raw_output_path = raw_output_path
                if debug_logging:
                    print(f"[batch] wrote raw model text → {raw_output_path}")

            # 4) Build minimal predicted Phenopacket + validate via utility class
            predicted_pp_json = build_minimal_phenopacket_from_hpo_list(
                patient_id=patient_id, hpo_list=predicted_terms_for_case
            )
            predicted_pkt_util = UtilPhenopacket(predicted_pp_json)
            outcome.predicted_packet_util = predicted_pkt_util

            # 5) Persist predicted JSON (optional)
            if write_predicted_json:
                out_filename = f"{pmid}__{patient_id}.json"
                predicted_json_path = os.path.join(
                    directory_for_predicted_jsons, out_filename
                )
                with open(predicted_json_path, "w", encoding="utf-8") as f:
                    json.dump(predicted_pkt_util.to_json(), f, indent=2)
                outcome.predicted_json_path = predicted_json_path
                if debug_logging:
                    print(f"[batch] wrote predicted JSON → {predicted_json_path}")

            batch_result.successful_outcomes.append(outcome)

        except Exception as err:  # capture and continue
            outcome.error_message = str(err)
            batch_result.failed_outcomes.append(outcome)
            print(f"[WARN] Failed prediction for PMID {pmid}: {err}")

        # 6) Rate limiting (optional)
        if sleep_seconds_between_cases > 0:
            time.sleep(sleep_seconds_between_cases)

    if debug_logging:
        print(
            f"[batch] Completed: successes={batch_result.total_successes()} "
            f"failures={batch_result.total_failures()}"
        )

    return batch_result
