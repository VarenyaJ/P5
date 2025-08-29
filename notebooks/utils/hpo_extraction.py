"""
notebooks/utils/hpo_extraction.py

LLM-based HPO extraction with robust JSON parsing and practical fallbacks.
Also includes a helper to wrap HPO terms into a minimal Phenopacket JSON.

Requires: `ollama` Python package and a local model (default: llama3.2:latest).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

from ollama import chat


# ----------------------- Prompt + JSON schema -----------------------

HPO_JSON_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "hpo_id":       {"type": ["string", "null"]},
            "hpo_label":    {"type": ["string", "null"]},
            "excerpt":      {"type": ["string", "null"]},
            "onset_id":     {"type": ["string", "null"]},
            "severity_id":  {"type": ["string", "null"]},
            "frequency_id": {"type": ["string", "null"]},
        },
        "required": ["hpo_id"],
    },
}

HPO_PROMPT: str = (
    "You are a clinical NLP engine specialized in biomedical ontologies.\n"
    "Extract ONLY Human Phenotype Ontology (HPO) terms that describe the patient(s) in the text.\n\n"
    "Output: a single JSON array. Each element MUST be an object with exactly these keys:\n"
    "{\n"
    '  "hpo_id": "HP:XXXXXXX",\n'
    '  "hpo_label": "Seizure",\n'
    '  "excerpt": "exact text from PDF",\n'
    '  "onset_id": "HP:XXXXXXX" or null,\n'
    '  "severity_id": "HP:XXXXXXX" or null,\n'
    '  "frequency_id": "HP:XXXXXXX" or null\n'
    "}\n\n"
    "No prose, no markdown, no extra keys. If none exist, return []."
)


# ----------------------- Small parsing helpers -----------------------

def _first_list_in(obj: Any) -> Optional[List[Any]]:
    """Return the first list nested anywhere in `obj` (list or dict), else None."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for value in obj.values():
            found = _first_list_in(value)
            if found is not None:
                return found
    return None


def _slice_first_json_array(raw_text: str) -> str:
    """Extract the first top-level JSON array substring from `raw_text`."""
    start = raw_text.find("[")
    if start == -1:
        raise RuntimeError("No '[' found in text; cannot slice JSON array.")
    depth = 0
    for i, ch in enumerate(raw_text[start:], start=start):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return raw_text[start : i + 1]
    raise RuntimeError("Unbalanced brackets; could not slice JSON array.")


# ----------------------- Phenopacket builder -----------------------

def build_minimal_phenopacket_from_hpo_list(
    patient_id: str,
    hpo_list: List[Dict[str, Any]],
    created_by: str = "P5-demo-notebook",
    schema_version: str = "2.0.2",
) -> Dict[str, Any]:
    """
    Convert extracted HPO terms into a minimal Phenopacket JSON
    with phenotypicFeatures only (and basic qualifiers if present).
    """
    def _mk_type(term_id: Optional[str], label: Optional[str]) -> Optional[Dict[str, Any]]:
        if not term_id:
            return None
        return {"id": term_id, "label": label or term_id}

    phenotypic_features: List[Dict[str, Any]] = []
    for term in hpo_list:
        t = _mk_type(term.get("hpo_id"), term.get("hpo_label"))
        if t is None:
            continue
        feature: Dict[str, Any] = {"type": t}
        if term.get("onset_id"):
            feature["onset"] = {"term": {"id": term["onset_id"]}}
        if term.get("severity_id"):
            feature["severity"] = {"term": {"id": term["severity_id"]}}
        if term.get("frequency_id"):
            feature["frequency"] = {"term": {"id": term["frequency_id"]}}
        phenotypic_features.append(feature)

    return {
        "id": patient_id,
        "subject": {"id": patient_id},
        "phenotypicFeatures": phenotypic_features,
        "metaData": {
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "createdBy": created_by,
            "phenopacketSchemaVersion": schema_version,
        },
    }


# ----------------------- Main extraction function -----------------------

def extract_hpo_terms(
    clinical_text: str,
    prompt: str = HPO_PROMPT,
    model: str = "llama3.2:latest",
    max_retries_json_mode: int = 2,
    return_raw_model_text: bool = False,
    debug_logging: bool = False,
) -> List[Dict[str, Any]] | Tuple[List[Dict[str, Any]], str]:
    """
    Ask the local LLM (Ollama) for ONLY an array of HPO term dicts and return it.

    Strategy:
      1) Try structured output with `format=HPO_JSON_SCHEMA`.
      2) Fallback to `format="json"` with a few cleanup attempts.
      3) Final fallback: regex pull of HP:IDs from model text or source text.

    Returns:
        List of HPO term dicts (or tuple with raw model text if `return_raw_model_text=True`).
    """
    last_raw_text_from_model = ""

    def _ask(schema_or_mode):
        # Try with format hint
        try:
            response = chat(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": clinical_text},
                ],
                stream=False,
                format=schema_or_mode,           # dict (schema) or "json"
                options={"temperature": 0, "seed": -1, "num_ctx": 8192},
            )
            out = (response.get("message") or {}).get("content", "")
            if out:
                return out.strip()
        except Exception:
            pass

        # Fallback: no format hint at all
        response = chat(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": clinical_text},
            ],
            stream=False,
            # format omitted on purpose
            options={"temperature": 0, "seed": -1, "num_ctx": 8192},
        )
        return (response.get("message") or {}).get("content", "").strip()

    # 1) Schema mode
    try:
        last_raw_text_from_model = _ask(HPO_JSON_SCHEMA)
        obj = json.loads(last_raw_text_from_model)
        maybe_list = _first_list_in(obj)
        if isinstance(maybe_list, list):
            return (maybe_list, last_raw_text_from_model) if return_raw_model_text else maybe_list
    except Exception as e:
        if debug_logging:
            print("Schema mode failed:", repr(e))

    # 2) JSON-mode with retries + cleanup
    for attempt in range(max_retries_json_mode + 1):
        last_raw_text_from_model = _ask("json")
        if debug_logging:
            print(f"[json attempt {attempt}] preview: {last_raw_text_from_model[:160]!r}")

        # a) direct JSON
        try:
            obj = json.loads(last_raw_text_from_model)
            maybe_list = _first_list_in(obj)
            if isinstance(maybe_list, list):
                return (maybe_list, last_raw_text_from_model) if return_raw_model_text else maybe_list
            if isinstance(obj, dict) and "hpo_id" in obj:
                as_list = [obj]
                return (as_list, last_raw_text_from_model) if return_raw_model_text else as_list
        except json.JSONDecodeError:
            pass

        # b) strip code fences
        cleaned = re.sub(r"^```(?:json)?|```$", "", last_raw_text_from_model, flags=re.MULTILINE).strip()
        if cleaned != last_raw_text_from_model:
            try:
                obj = json.loads(cleaned)
                maybe_list = _first_list_in(obj)
                if isinstance(maybe_list, list):
                    return (maybe_list, last_raw_text_from_model) if return_raw_model_text else maybe_list
                if isinstance(obj, dict) and "hpo_id" in obj:
                    as_list = [obj]
                    return (as_list, last_raw_text_from_model) if return_raw_model_text else as_list
            except json.JSONDecodeError:
                pass

        # c) bracket slicing
        try:
            array_text = _slice_first_json_array(last_raw_text_from_model)
            obj = json.loads(array_text)
            if isinstance(obj, list):
                return (obj, last_raw_text_from_model) if return_raw_model_text else obj
        except Exception:
            pass

    # 3) Regex fallback — safer than returning [] silently
    hp_ids = sorted(set(re.findall(r"HP:\d{7}", last_raw_text_from_model)) |
                    set(re.findall(r"HP:\d{7}", clinical_text)))
    fallback = [
        {
            "hpo_id": hp,
            "hpo_label": None,
            "excerpt": None,
            "onset_id": None,
            "severity_id": None,
            "frequency_id": None,
        }
        for hp in hp_ids
    ]
    if debug_logging:
        print("JSON extraction failed; falling back to regex IDs:", hp_ids[:10], "..." if len(hp_ids) > 10 else "")
    return (fallback, last_raw_text_from_model) if return_raw_model_text else fallback
