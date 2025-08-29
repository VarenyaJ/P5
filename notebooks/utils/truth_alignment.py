"""
notebooks/utils/truth_alignment.py

Load ground-truth phenopackets, validate leniently against protobuf,
wrap them with the project's Phenopacket utility, and align them to the dataset.

Usage:
    from notebooks.utils.truth_alignment import load_and_align_truth

    aligned = load_and_align_truth(
        dataset_dataframe=dataframe_cases,
        maximum_rows=None,  # or an int for smoke testing
    )

    # aligned contains:
    # - list_of_pmids_aligned
    # - list_of_truth_packets_wrapped
    # - list_of_patient_ids_from_truth
    # - list_of_input_paths_aligned
    # - list_of_skipped_cases (with reasons)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from google.protobuf.json_format import ParseDict, ParseError
from phenopackets import Phenopacket as ProtoPhenopacket
from json.decoder import JSONDecodeError

# These are our project utilities (already on PYTHONPATH per the setup step)
from phenopacket import Phenopacket, InvalidPhenopacketError


@dataclass
class TruthAlignmentResult:
    list_of_pmids_aligned: List[str]
    list_of_truth_packets_wrapped: List[Phenopacket]
    list_of_patient_ids_from_truth: List[str]
    list_of_input_paths_aligned: List[str]
    list_of_skipped_cases: List[Dict[str, str]]


def _lenient_parse_truth_json(truth_json_path: str) -> Dict[str, Any]:
    """
    Read JSON from disk and leniently parse it into a protobuf object
    to catch gross schema issues while tolerating unknown fields.
    Returns the original dict if parsing succeeds.
    """
    with open(truth_json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    proto_obj = ProtoPhenopacket()
    # ignore_unknown_fields=True makes us tolerant to minor schema drift
    ParseDict(raw, proto_obj, ignore_unknown_fields=True)
    return raw


def load_and_align_truth(
    dataset_dataframe, maximum_rows: Optional[int] = None
) -> TruthAlignmentResult:
    """
    Iterate over the dataset rows, load each ground-truth phenopacket JSON,
    validate lightly (protobuf), then wrap with the project's Phenopacket class.

    Returns aligned lists in the same order; rows that fail are added to skipped_cases.
    """
    if maximum_rows is not None:
        dataset_dataframe = dataset_dataframe.head(int(maximum_rows))

    list_of_pmids_aligned: List[str] = []
    list_of_truth_packets_wrapped: List[Phenopacket] = []
    list_of_patient_ids_from_truth: List[str] = []
    list_of_input_paths_aligned: List[str] = []
    list_of_skipped_cases: List[Dict[str, str]] = []

    required_columns = {"pmid", "input", "truth"}
    missing_cols = required_columns - set(dataset_dataframe.columns)
    if missing_cols:
        raise KeyError(f"Dataset CSV missing required columns: {missing_cols}")

    for row in dataset_dataframe.itertuples(index=False):
        pmid_value: str = row.pmid
        input_path: str = row.input
        truth_json_path: str = row.truth

        # sanity: truth file must exist
        if not os.path.isfile(truth_json_path):
            list_of_skipped_cases.append(
                {
                    "pmid": pmid_value,
                    "truth": truth_json_path,
                    "reason": "truth file missing",
                }
            )
            continue

        # 1) Lenient protobuf check
        try:
            raw_truth_json = _lenient_parse_truth_json(truth_json_path)
        except (ParseError, JSONDecodeError) as e:
            list_of_skipped_cases.append(
                {
                    "pmid": pmid_value,
                    "truth": truth_json_path,
                    "reason": f"truth schema/parse error: {e}",
                }
            )
            continue

        # 2) Wrap with project utility (ensures phenotypicFeatures access)
        try:
            wrapped_truth = Phenopacket(raw_truth_json)
        except InvalidPhenopacketError as e:
            list_of_skipped_cases.append(
                {
                    "pmid": pmid_value,
                    "truth": truth_json_path,
                    "reason": f"invalid phenopacket: {e}",
                }
            )
            continue

        # 3) Best-effort patient id (for naming outputs later)
        try:
            patient_id = wrapped_truth.to_json().get("subject", {}).get("id")
        except Exception:
            patient_id = None
        patient_id = patient_id or pmid_value  # fallback

        # 4) Accumulate aligned outputs
        list_of_pmids_aligned.append(pmid_value)
        list_of_truth_packets_wrapped.append(wrapped_truth)
        list_of_patient_ids_from_truth.append(patient_id)
        list_of_input_paths_aligned.append(input_path)

    return TruthAlignmentResult(
        list_of_pmids_aligned=list_of_pmids_aligned,
        list_of_truth_packets_wrapped=list_of_truth_packets_wrapped,
        list_of_patient_ids_from_truth=list_of_patient_ids_from_truth,
        list_of_input_paths_aligned=list_of_input_paths_aligned,
        list_of_skipped_cases=list_of_skipped_cases,
    )
