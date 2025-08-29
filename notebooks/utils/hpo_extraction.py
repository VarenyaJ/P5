# notebooks/utils/hpo_extraction.py
"""
HPO extraction utilities (deterministic, strict validation, no normalizer).

Overview
--------
- The model must infer the *exact* HPO id (HP:#######) and the official primary label.
- Deterministic decoding: temperature=0, top_p=1 (where supported).
- Output contract (preferred): a top-level JSON array bracketed by <<<JSON ... JSON>>> sentinels.
- Client-side strict validation:
  • hpo_id must match r'^HP:\\d{7}$'
  • hpo_label must be a non-empty string
  • evidence must be an exact substring of the given text (case-insensitive)
- Evidence is **dropped** before returning; it is only used to force text-grounding.
- Prompt chunking keeps inputs under the model's context window.
- If no valid items are produced across all chunks, perform exactly **one retry** on the first chunk.
- Fallback parsing accepts {"results":[...]} or a single object that looks like an item.
- No ontology lookup, mapping, or normalization is performed.

Public API
----------
- extract_hpo_terms(clinical_text, model="llama3.2:latest", return_raw_model_text=False, ...)
    -> (list[dict], raw_model_text or None)
- build_minimal_phenopacket_from_hpo_list(patient_id, hpo_list) -> dict
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

__all__ = [
    "extract_hpo_terms",
    "build_minimal_phenopacket_from_hpo_list",
]

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
    """Return current UTC timestamp in ISO 8601 (seconds precision)."""
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
[{{"hpo_id":"HP:0001250","hpo_label":"Seizure","evidence":"drug-resistant infantile epilepsy"}}]
JSON>>>
(Use the correct id/label for THIS text; the above line is just a format example. Omit an item if you cannot quote exact evidence.)
"""

def _format_user_prompt(clinical_text: str, max_items: int) -> str:
    """Build the user prompt (system preamble is provided separately where supported)."""
    return _USER_INSTRUCTIONS.format(max_items=max_items, clinical_text=clinical_text)

# On retry, we resend the full task + the SAME text with a tightened "output-only" rule.
def _format_retry_prompt(original_clinical_text: str, max_items: int) -> str:
    """Construct a stricter retry prompt (user message)."""
    tightened = (
        "Your previous output did not follow format or could not be validated.\n"
        "Return ONLY a valid top-level JSON array of objects with keys "
        '"hpo_id", "hpo_label", "evidence" — wrapped between <<<JSON and JSON>>>.\n'
        "Do not add any commentary.\n"
    )
    return tightened + "\n\n" + _format_user_prompt(original_clinical_text, max_items=max_items)

# -----------------------------
# Text chunking
# -----------------------------

def _chunk_text(text: str, max_chars: int = 5500, overlap: int = 300) -> Iterable[str]:
    """
    Yield overlapping text chunks to keep prompts under typical small-model context limits.
    Overlap helps avoid cutting evidence strings across chunk boundaries.
    """
    s = (text or "").strip()
    n = len(s)
    if n <= max_chars:
        if s:
            yield s
        return
    start = 0
    while start < n:
        end = min(n, start + max_chars)
        yield s[start:end]
        if end == n:
            break
        start = max(0, end - overlap)

# -----------------------------
# Ollama call helpers
# -----------------------------

def _call_ollama_http(model: str, user_prompt: str, timeout_s: int = 180) -> str:
    """
    Call the Ollama HTTP API (http://localhost:11434) using a system + user message.
    Streams are concatenated. We intentionally DO NOT set "format":"json" to preserve custom sentinels.
    """
    import http.client
    import json as _json

    conn = http.client.HTTPConnection("localhost", 11434, timeout=timeout_s)
    body = _json.dumps({
        "model": model,
        "system": _SYSTEM_PREAMBLE,  # leverage system slot to reinforce rules
        "prompt": user_prompt,       # user content (chunked text + instructions)
        "options": {
            "temperature": 0,
            "top_p": 1,
            "repeat_penalty": 1.0,
            # Some models honor this and reduce truncation:
            "num_ctx": 8192,
        },
        "stream": True,
    })
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
            piece = json.loads(line.decode("utf-8"))
            raw_chunks.append(piece.get("response", ""))
            if piece.get("done"):
                break
        except Exception:
            # Ignore any non-JSON heartbeat/noise lines
            continue
    return "".join(raw_chunks)

def _call_ollama_cli(model: str, user_prompt: str, timeout_s: int = 180) -> str:
    """
    Fallback to `ollama run` if HTTP isn't available.
    Since the CLI cannot pass a separate system message, we prepend it to the user prompt.
    """
    combined_prompt = f"{_SYSTEM_PREAMBLE}\n\n{user_prompt}"
    cmd = ["ollama", "run", model]
    try:
        proc = subprocess.run(
            cmd,
            input=combined_prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
        )
    except FileNotFoundError:
        raise RuntimeError("Ollama not found. Install Ollama or start the daemon.")
    if proc.returncode != 0:
        raise RuntimeError(f"Ollama CLI error {proc.returncode}: {proc.stderr.decode('utf-8', 'ignore')}")
    return proc.stdout.decode("utf-8", "ignore")

def _ask_model(model: str, user_prompt: str, timeout_s: int = 180, debug: bool = False) -> str:
    """
    Try HTTP first, then CLI. Returns raw text from the model.
    """
    try:
        out = _call_ollama_http(model, user_prompt, timeout_s=timeout_s)
        if debug:
            print("[extract] used Ollama HTTP")
        return out
    except Exception as e_http:
        if debug:
            print(f"[extract] HTTP failed: {e_http}. Falling back to CLI...")
        out = _call_ollama_cli(model, user_prompt, timeout_s=timeout_s)
        if debug:
            print("[extract] used Ollama CLI")
        return out

# -----------------------------
# Parsing & validation
# -----------------------------

def _slice_between_sentinels(text: str, start_tok: str = _JSON_START, end_tok: str = _JSON_END) -> Optional[str]:
    """
    Extract substring between the first <<<JSON and the next JSON>>>. Returns None if not found.
    """
    i = text.find(start_tok)
    if i < 0:
        return None
    j = text.find(end_tok, i + len(start_tok))
    if j < 0:
        return None
    return text[i + len(start_tok): j].strip()

def _ensure_list(obj: Any) -> Optional[List[Any]]:
    """Return obj if it is a list, else None."""
    return obj if isinstance(obj, list) else None

def _dict_looks_like_item(obj: Any) -> bool:
    """Lightweight structural check for a single item-like dict."""
    return (
        isinstance(obj, dict)
        and "hpo_id" in obj
        and "hpo_label" in obj
        and "evidence" in obj
    )

# Fallback: find any JSON array block in the text
_JSON_ARRAY_FINDER = re.compile(r"\[\s*\{.*?\}\s*\]", flags=re.DOTALL)

# Fallback: find "results": [ ... ] and return the array substring
_RESULTS_ARRAY_FINDER = re.compile(r'"results"\s*:\s*(\[\s*\{.*?\}\s*\])', flags=re.DOTALL)

def _find_any_json_array_block(text: str) -> Optional[str]:
    """Return the first top-level array-looking substring, if any."""
    m = _JSON_ARRAY_FINDER.search(text or "")
    return m.group(0) if m else None

def _find_results_array(text: str) -> Optional[str]:
    """Return the array substring found under a 'results' key, if present."""
    m = _RESULTS_ARRAY_FINDER.search(text or "")
    return m.group(1) if m else None

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

        # Guard against spurious "Seizure" defaulting when 'seiz' never appears
        if not allow_seizure and hpo_label in _COMMON_FAKE_DEFAULTS:
            continue

        out.append({"hpo_id": hpo_id, "hpo_label": hpo_label})
        if len(out) >= max_items:
            break

    return out

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
    chunk_max_chars: int = 5500,
    chunk_overlap_chars: int = 300,
) -> Tuple[List[Dict[str, str]], Optional[str]]:
    """
    Run a strict HPO term extraction pass with text chunking and a single retry.

    Parameters
    ----------
    clinical_text : str
        The PDF-derived plain text. No modification or normalization is performed here.
    model : str
        Ollama model name (e.g., "llama3.2:latest").
    max_pheno_items : int
        Soft cap on number of validated items to keep.
    timeout_s : int
        Timeout for each model call in seconds.
    return_raw_model_text : bool
        If True, returns concatenated raw model outputs for auditing.
    debug_logging : bool
        If True, prints extra logs.
    chunk_max_chars : int
        Maximum characters per prompt chunk (helps stay under context window).
    chunk_overlap_chars : int
        Overlap between chunks to reduce evidence split across boundaries.

    Returns
    -------
    (items, raw_model_text)
        items: list of { "hpo_id": "HP:#######", "hpo_label": "Primary Label" }
        raw_model_text: str or None (concatenation of chunk outputs and retry, if any)
    """
    if not isinstance(clinical_text, str) or not clinical_text.strip():
        return ([], None)

    def _try_load_and_validate(raw: Optional[str], src_text: str) -> List[Dict[str, str]]:
        if raw is None:
            return []
        try:
            loaded = json.loads(raw)
            arr = _ensure_list(loaded)
            if arr is None:
                return []
            return _validate_and_filter_items(arr, src_text, max_items=max_pheno_items)
        except Exception:
            return []

    items: List[Dict[str, str]] = []
    raw_text_accum: List[str] = []

    # --- Primary pass: iterate over chunks, exit early on first valid set ---
    for chunk_idx, text_chunk in enumerate(
        _chunk_text(clinical_text, max_chars=chunk_max_chars, overlap=chunk_overlap_chars), start=1
    ):
        user_prompt = _format_user_prompt(text_chunk, max_items=max_pheno_items)
        if debug_logging:
            print(f"[extract] Sending chunk {chunk_idx} to model (len={len(text_chunk)}).")
        raw_text = _ask_model(model, user_prompt, timeout_s=timeout_s, debug=debug_logging)
        raw_text_accum.append(raw_text or "")

        # Preferred parse: look for our sentinel-bracketed array
        parsed = _slice_between_sentinels(raw_text)
        if parsed is not None:
            validated = _try_load_and_validate(parsed, text_chunk)
            if debug_logging:
                print(f"[extract] Chunk {chunk_idx}: validated {len(validated)} item(s) via sentinels.")
            items = validated

        else:
            # Fallback 1: find any array-looking block
            scavenged = _find_any_json_array_block(raw_text)
            if scavenged:
                validated = _try_load_and_validate(scavenged, text_chunk)
                if debug_logging:
                    print(f"[extract] Chunk {chunk_idx}: validated {len(validated)} item(s) via array scavenger.")
                items = validated
            else:
                # Fallback 2: {"results":[...]}
                results_arr = _find_results_array(raw_text)
                if results_arr:
                    try:
                        loaded = json.loads(results_arr)
                        validated = _validate_and_filter_items(loaded, text_chunk, max_items=max_pheno_items)
                        if debug_logging:
                            print(f"[extract] Chunk {chunk_idx}: validated {len(validated)} item(s) from results[].")
                        items = validated
                    except Exception:
                        pass
                else:
                    # Fallback 3: a single object that looks like an item
                    try:
                        maybe = json.loads(raw_text)
                        if _dict_looks_like_item(maybe):
                            validated = _validate_and_filter_items([maybe], text_chunk, max_items=max_pheno_items)
                            if debug_logging:
                                print(f"[extract] Chunk {chunk_idx}: validated {len(validated)} item(s) from single-object.")
                            items = validated
                    except Exception:
                        pass

        if items:
            break  # Early exit once we have any validated items

    # --- Single retry on the first chunk if no items were found ---
    if not items:
        first_chunk = next(_chunk_text(clinical_text, max_chars=chunk_max_chars, overlap=chunk_overlap_chars), "")
        retry_prompt = _format_retry_prompt(first_chunk, max_items=max_pheno_items)
        if debug_logging:
            print("[extract] No valid items after chunks → doing single full retry on first chunk.")
        raw_text_retry = _ask_model(model, retry_prompt, timeout_s=timeout_s, debug=debug_logging)
        raw_text_accum.append("\n--- RETRY ---\n" + (raw_text_retry or ""))

        parsed_retry = _slice_between_sentinels(raw_text_retry)
        if parsed_retry is not None:
            items = _try_load_and_validate(parsed_retry, first_chunk)
            if debug_logging:
                print(f"[extract] Retry: validated {len(items)} item(s) via sentinels.")
        else:
            scavenged_retry = _find_any_json_array_block(raw_text_retry)
            if scavenged_retry:
                items = _try_load_and_validate(scavenged_retry, first_chunk)
                if debug_logging:
                    print(f"[extract] Retry: validated {len(items)} item(s) via array scavenger.")
            else:
                # Retry fallbacks: {"results":[...]} or single-object
                results_retry = _find_results_array(raw_text_retry)
                if results_retry:
                    try:
                        loaded = json.loads(results_retry)
                        items = _validate_and_filter_items(loaded, first_chunk, max_items=max_pheno_items)
                        if debug_logging:
                            print(f"[extract] Retry: validated {len(items)} item(s) from results[].")
                    except Exception:
                        pass
                else:
                    try:
                        maybe_retry = json.loads(raw_text_retry)
                        if _dict_looks_like_item(maybe_retry):
                            items = _validate_and_filter_items([maybe_retry], first_chunk, max_items=max_pheno_items)
                            if debug_logging:
                                print(f"[extract] Retry: validated {len(items)} item(s) from single-object.")
                    except Exception:
                        pass

    raw_text_combined = "\n\n".join(raw_text_accum).strip()
    return (items, (raw_text_combined if return_raw_model_text else None))


def build_minimal_phenopacket_from_hpo_list(
    patient_id: str,
    hpo_list: List[Dict[str, str]],
    *,
    created_by: str = "P5-demo-notebook",
    schema_version: str = "2.0.2",
) -> Dict[str, Any]:
    """
    Build a minimal Phenopacket dict from items like: {"hpo_id":"HP:0001250","hpo_label":"Seizure"}.
    No normalization or ontology fetch is performed — the input is trusted if it passes local validation.
    """
    phenos = []
    for it in hpo_list:
        hpo_id = it.get("hpo_id")
        hpo_label = it.get("hpo_label")
        if isinstance(hpo_id, str) and _HPO_ID_RE.match(hpo_id) and isinstance(hpo_label, str) and hpo_label.strip():
            phenos.append({
                "type": {
                    "id": hpo_id,
                    "label": hpo_label,
                }
            })

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
