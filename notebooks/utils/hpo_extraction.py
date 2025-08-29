# notebooks/utils/hpo_extraction.py
"""
HPO extraction utilities (strict, no normalizer)

Design goals
------------
- The model MUST infer the exact HPO id (HP:#######) and the official primary label itself.
- Deterministic generation: temperature=0, top_p=1 (where supported).
- Output must be a top-level JSON array between sentinels <<<JSON and JSON>>>.
- We validate client-side and fail closed:
  - hpo_id must match r'^HP:\\d{7}$'
  - hpo_label must be non-empty string
  - evidence MUST be an exact snippet from the provided text (case-insensitive substring)
- We drop the evidence field before returning (it is only used to force text-grounding).
- If the first pass is invalid, we do exactly ONE retry that RESENDS the full instructions
  plus the clinical text (not just a format correction).
- Includes a fallback JSON array "scavenger" that locates any top-level array in the output
  if the model ignores the <<<JSON ... JSON>>> sentinels.
- No ontology lookup, mapping, or normalization is performed.

Public API
----------
- extract_hpo_terms(clinical_text, model="llama3.2:latest", return_raw_model_text=False, ...)
    -> (list[dict], raw_model_text or None)
- build_minimal_phenopacket_from_hpo_list(patient_id, hpo_list) -> dict
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

__all__ = ["extract_hpo_terms", "build_minimal_phenopacket_from_hpo_list"]

# -----------------------------
# Constants & simple utilities
# -----------------------------

_JSON_START = "<<<JSON"
_JSON_END = "JSON>>>"

_HPO_ID_RE = re.compile(r"^HP:\d{7}$")
# Small heuristic blocklist to catch "default-to-seizure" drift when the text
# doesn't mention seizures at all (only applied if no 'seiz' substring exists).
_COMMON_FAKE_DEFAULTS = {"Seizure", "seizure"}


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -----------------------------
# Prompt construction
# -----------------------------

_SYSTEM_PREAMBLE = """You extract Human Phenotype Ontology (HPO) terms from scientific text.

Rules that are mandatory:
1) You must output ONLY a top-level JSON array between the markers:
   <<<JSON
   [ ... array here ... ]
   JSON>>>
2) Each array item MUST be an object with exactly these keys:
   - "hpo_id": string, like "HP:0001250" (MUST match ^HP:\\d{7}$)
   - "hpo_label": string, the primary HPO label for that id
   - "evidence": string, an exact snippet copied from the given text that justifies the term
3) If you are uncertain or cannot find a supporting quote in the text, DO NOT include the item.
4) DO NOT summarize, DO NOT include any other keys, DO NOT include explanations outside the JSON.
5) The JSON must be valid and parseable.
"""

# NOTE: clinical_text is fenced in a code block to improve adherence.
# The example uses doubled braces so .format() doesn't consume them.
_USER_INSTRUCTIONS = """Extract up to {max_items} distinct HPO phenotypes from the provided text.

- Only include items you can justify with an exact evidence snippet from the text.
- If the text mentions a phenotype family (e.g., "seizures") but you cannot determine the exact HPO ID and primary label, omit it.
- No normalization or lookup will be performed after your output, so the id and label must already be correct.
- Return nothing else besides the bracketed JSON block.

Text:
```
{clinical_text}
```
Return strictly:
<<<JSON
[{{"hpo_id":"HP:0001250","hpo_label":"Seizure","evidence":"..."}}]
JSON>>>
(Use the correct id/label for THIS text; the above line is just a format example.)
"""


# On retry, we resend the full task + the SAME text with a tightened "output-only" rule.
def _format_retry_prompt(original_clinical_text: str, max_items: int) -> str:
    tightened = (
        "Your previous output did not follow format or could not be validated.\n"
        "Return ONLY a valid top-level JSON array of objects with keys "
        '"hpo_id", "hpo_label", "evidence" — wrapped between <<<JSON and JSON>>>.\n'
        "Do not add any commentary.\n"
    )
    return (
        tightened
        + "\n\n"
        + _USER_INSTRUCTIONS.format(
            max_items=max_items, clinical_text=original_clinical_text
        )
    )


# -----------------------------
# Ollama call helpers
# -----------------------------


def _call_ollama_http(model: str, prompt: str, timeout_s: int = 180) -> str:
    """
    Try the Ollama HTTP API first (http://localhost:11434).
    Streams are concatenated into a single string.
    We do NOT force JSON with 'format': 'json' because we need custom sentinels.
    """
    import http.client
    import json as _json

    conn = http.client.HTTPConnection("localhost", 11434, timeout=timeout_s)
    body = _json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "options": {
                "temperature": 0,
                "top_p": 1,
                "repeat_penalty": 1.0,
                # Ignored by some models; included to reduce truncation:
                "num_ctx": 8192,
            },
            # "format": "json",   # enforce JSON if model supports it (safe no-op if not)
            "stream": True,
        }
    )
    headers = {"Content-Type": "application/json"}
    conn.request("POST", "/api/generate", body=body, headers=headers)
    resp = conn.getresponse()
    if resp.status != 200:
        raise RuntimeError(f"Ollama HTTP error {resp.status}: {resp.read()!r}")

    raw_chunks: List[str] = []
    while True:
        line = resp.readline()
        if not line:
            break
        try:
            piece = _json.loads(line.decode("utf-8"))
            raw_chunks.append(piece.get("response", ""))
            if piece.get("done"):
                break
        except Exception:
            continue
    return "".join(raw_chunks)


def _call_ollama_cli(model: str, prompt: str, timeout_s: int = 180) -> str:
    """
    Fallback to the `ollama run` CLI if HTTP isn't available.
    We feed via stdin for maximum compatibility.
    """
    cmd = ["ollama", "run", model]
    try:
        proc = subprocess.run(
            cmd,
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
        )
    except FileNotFoundError:
        raise RuntimeError("Ollama not found. Install Ollama or start the daemon.")
    if proc.returncode != 0:
        raise RuntimeError(
            f"Ollama CLI error {proc.returncode}: {proc.stderr.decode('utf-8', 'ignore')}"
        )
    return proc.stdout.decode("utf-8", "ignore")


def _ask_model(
    model: str, prompt: str, timeout_s: int = 180, debug: bool = False
) -> str:
    """
    Try HTTP first, then CLI. Returns raw text from the model.
    """
    try:
        out = _call_ollama_http(model, prompt, timeout_s=timeout_s)
        if debug:
            print("[extract] used Ollama HTTP")
        return out
    except Exception as e_http:
        if debug:
            print(f"[extract] HTTP failed: {e_http}. Falling back to CLI...")
        out = _call_ollama_cli(model, prompt, timeout_s=timeout_s)
        if debug:
            print("[extract] used Ollama CLI")
        return out


# -----------------------------
# Parsing & validation
# -----------------------------


def _slice_between_sentinels(
    text: str, start_tok: str = _JSON_START, end_tok: str = _JSON_END
) -> Optional[str]:
    """
    Extract substring between the first <<<JSON and the next JSON>>>.
    Returns None if not found.
    """
    i = text.find(start_tok)
    if i < 0:
        return None
    j = text.find(end_tok, i + len(start_tok))
    if j < 0:
        return None
    return text[i + len(start_tok) : j].strip()


def _ensure_list(obj: Any) -> Optional[List[Any]]:
    return obj if isinstance(obj, list) else None


def _validate_and_filter_items(
    items: Iterable[Dict[str, Any]],
    source_text: str,
    max_items: int,
    apply_seizure_blocker: bool = True,
) -> List[Dict[str, str]]:
    """
    Validate items and return a list of dicts with only {hpo_id, hpo_label}.
    - Strict regex for hpo_id
    - Non-empty hpo_label
    - evidence must be a substring (case-insensitive) of the source text
    - Optional "seizure" guard if the word "seiz" never appears in the text
    """
    out: List[Dict[str, str]] = []
    text_lower = source_text.lower()

    allow_seizure = (not apply_seizure_blocker) or ("seiz" in text_lower)

    for it in items:
        if not isinstance(it, dict):
            continue
        hpo_id = it.get("hpo_id")
        hpo_label = it.get("hpo_label")
        evidence = it.get("evidence")
        if not (isinstance(hpo_id, str) and _HPO_ID_RE.match(hpo_id)):
            continue
        if not (isinstance(hpo_label, str) and hpo_label.strip()):
            continue
        if not (isinstance(evidence, str) and evidence.strip()):
            continue
        # evidence must be present in the text (case-insensitive)
        if evidence.lower() not in text_lower:
            continue
        # Optional guard against spurious "Seizure"
        if not allow_seizure and hpo_label in _COMMON_FAKE_DEFAULTS:
            continue
        out.append({"hpo_id": hpo_id, "hpo_label": hpo_label})

        if len(out) >= max_items:
            break
    return out


def _format_prompt(clinical_text: str, max_items: int) -> str:
    return f"{_SYSTEM_PREAMBLE}\n\n{_USER_INSTRUCTIONS.format(max_items=max_items, clinical_text=clinical_text)}"


# Fallback: find any JSON array block in the text
_JSON_ARRAY_FINDER = re.compile(r"\[\s*\{.*?\}\s*\]", flags=re.DOTALL)


def _find_any_json_array_block(text: str) -> Optional[str]:
    """
    Fallback: find any JSON array block in the text and return the raw substring.
    We still fully validate items afterwards.
    """
    m = _JSON_ARRAY_FINDER.search(text or "")
    return m.group(0) if m else None


def _dict_looks_like_item(obj: Any) -> bool:
    return (
        isinstance(obj, dict)
        and "hpo_id" in obj
        and "hpo_label" in obj
        and "evidence" in obj
    )


# -----------------------------
# Public functions
# -----------------------------


def extract_hpo_terms(
    clinical_text: str,
    model: str = "llama3.2:latest",
    *,
    max_pheno_items: int = 50,
    timeout_s: int = 180,
    return_raw_model_text: bool = False,
    debug_logging: bool = False,
) -> Tuple[List[Dict[str, str]], Optional[str]]:
    """
    Run a strict HPO term extraction pass.

    Parameters
    ----------
    clinical_text : str
        The PDF-derived plain text. We do *not* modify or normalize it.
    model : str
        Ollama model name (e.g., "llama3.2:latest").
    max_pheno_items : int
        Max number of terms to keep after validation (soft cap).
    timeout_s : int
        Timeout for each model call.
    return_raw_model_text : bool
        If True, return the raw text produced by the model.
    debug_logging : bool
        If True, prints extra logs.

    Returns
    -------
    (items, raw_model_text)
        items: list of { "hpo_id": "HP:#######", "hpo_label": "Primary Label" }
        raw_model_text: str or None
    """
    if not isinstance(clinical_text, str) or not clinical_text.strip():
        return ([], None)

    prompt = _format_prompt(clinical_text, max_items=max_pheno_items)
    if debug_logging:
        print(
            "[extract] Sending prompt to model with deterministic settings (temperature=0)."
        )

    raw_text = _ask_model(model, prompt, timeout_s=timeout_s, debug=debug_logging)
    if debug_logging:
        print(f"[extract] Raw model text length: {len(raw_text)}")

    def _try_load_and_validate(raw: Optional[str]) -> List[Dict[str, str]]:
        if raw is None:
            return []
        try:
            loaded = json.loads(raw)
            arr = _ensure_list(loaded)
            if arr is None:
                return []
            return _validate_and_filter_items(
                arr, clinical_text, max_items=max_pheno_items
            )
        except Exception:
            return []

    # First attempt: look for our sentinels
    items: List[Dict[str, str]] = []
    parsed = _slice_between_sentinels(raw_text)
    if parsed is not None:
        validated = _try_load_and_validate(parsed)
        if debug_logging:
            print(f"[extract] Validated {len(validated)} HPO term(s) on first pass.")
        items = validated
    else:
        if debug_logging:
            print("[extract] Markers not found on first pass. Trying array scavenger…")
        scavenged = _find_any_json_array_block(raw_text)
        if scavenged:
            validated = _try_load_and_validate(scavenged)
            if debug_logging:
                print(
                    f"[extract] Validated {len(validated)} HPO term(s) via scavenger."
                )
            items = validated
        else:
            # Last resort: maybe the whole output is a single JSON object
            try:
                maybe = json.loads(raw_text)
                if _dict_looks_like_item(maybe):
                    validated = _validate_and_filter_items(
                        [maybe], clinical_text, max_items=max_pheno_items
                    )
                    if debug_logging:
                        print(
                            f"[extract] Validated {len(validated)} HPO term(s) from single-object output."
                        )
                    items = validated
            except Exception:
                pass

        # If first pass produced nothing, do one retry: full task + same clinical text
    if not items:
        retry_prompt = _format_retry_prompt(clinical_text, max_items=max_pheno_items)
        if debug_logging:
            print("[extract] First pass invalid → doing single full retry.")
        raw_text_retry = _ask_model(
            model, retry_prompt, timeout_s=timeout_s, debug=debug_logging
        )
        if debug_logging:
            print(f"[extract] Retry raw length: {len(raw_text_retry)}")

        parsed_retry = _slice_between_sentinels(raw_text_retry)
        if parsed_retry is not None:
            validated_retry = _try_load_and_validate(parsed_retry)
            if debug_logging:
                print(
                    f"[extract] Validated {len(validated_retry)} HPO term(s) on retry."
                )
            items = validated_retry
        else:
            if debug_logging:
                print("[extract] Markers not found on retry. Trying array scavenger…")
            scavenged_retry = _find_any_json_array_block(raw_text_retry)
            if scavenged_retry:
                validated_retry = _try_load_and_validate(scavenged_retry)
                if debug_logging:
                    print(
                        f"[extract] Validated {len(validated_retry)} HPO term(s) via scavenger (retry)."
                    )
                items = validated_retry
            else:
                # Last resort on retry: maybe the whole retry output is a single JSON object
                try:
                    maybe_retry = json.loads(raw_text_retry)
                    if _dict_looks_like_item(maybe_retry):
                        validated_retry = _validate_and_filter_items(
                            [maybe_retry], clinical_text, max_items=max_pheno_items
                        )
                        if debug_logging:
                            print(
                                f"[extract] Validated {len(validated_retry)} HPO term(s) from single-object output (retry)."
                            )
                        items = validated_retry
                except Exception:
                    pass

        # Keep both raw outputs for auditing if requested
        raw_text = (raw_text or "") + "\n\n--- RETRY ---\n\n" + (raw_text_retry or "")

    return (items, (raw_text if return_raw_model_text else None))


def build_minimal_phenopacket_from_hpo_list(
    patient_id: str,
    hpo_list: List[Dict[str, str]],
    *,
    created_by: str = "P5-demo-notebook",
    schema_version: str = "2.0.2",
) -> Dict[str, Any]:
    """
    Build a minimal phenopacket dict from a list of items like:
        {"hpo_id": "HP:0001250", "hpo_label": "Seizure"}

    No normalization or ontology fetch is performed — we trust the input list.
    """
    phenos = []
    for it in hpo_list:
        hpo_id = it.get("hpo_id")
        hpo_label = it.get("hpo_label")
        if (
            isinstance(hpo_id, str)
            and _HPO_ID_RE.match(hpo_id)
            and isinstance(hpo_label, str)
            and hpo_label.strip()
        ):
            phenos.append({"type": {"id": hpo_id, "label": hpo_label}})

    packet = {
        "id": patient_id,
        "subject": {"id": patient_id},
        "phenotypicFeatures": phenos,
        "metaData": {
            "created": _now_iso_utc(),
            "createdBy": created_by,
            "phenopacketSchemaVersion": schema_version,
        },
    }
    return packet
