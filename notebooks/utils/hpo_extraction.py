# notebooks/utils/hpo_extraction.py
"""
Deterministic HPO extraction with strict, text-grounded validation (no normalizer).

- The model must output a top-level JSON array between <<<JSON ... JSON>>>.
- Each item requires: {"hpo_id","hpo_label","evidence"}.
- evidence must be an exact (case-insensitive) substring of the source text.
- We accept the first chunk that validates; otherwise retry once on the first chunk.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

__all__ = ["extract_hpo_terms", "build_minimal_phenopacket_from_hpo_list"]

logger = logging.getLogger(__name__)

# -----------------------------
# Constants & simple utilities
# -----------------------------

_JSON_START = "<<<JSON"
_JSON_END = "JSON>>>"

_HPO_ID_RE = re.compile(r"^HP:\d{7}$")
# Small guard for common drift when seizures aren't mentioned in the source text.
_COMMON_FAKE_DEFAULTS = {"Seizure", "seizure"}


def _now_iso_utc() -> str:
    """Return current UTC timestamp in compact ISO-8601 (Z) form."""
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
"""


def _format_user_prompt(clinical_text: str, max_items: int) -> str:
    """Render the user-facing instructions with the current text and limit."""
    return _USER_INSTRUCTIONS.format(max_items=max_items, clinical_text=clinical_text)


def _format_retry_prompt(original_clinical_text: str, max_items: int) -> str:
    """Tightened retry prompt that resends the full task and the same text."""
    tightened = (
        "Your previous output did not follow format or could not be validated.\n"
        "Return ONLY a valid top-level JSON array of objects with keys "
        '"hpo_id", "hpo_label", "evidence" — wrapped between <<<JSON and JSON>>>.\n'
        "Do not add any commentary.\n"
    )
    return (
        tightened
        + "\n\n"
        + _format_user_prompt(original_clinical_text, max_items=max_items)
    )


# -----------------------------
# Text chunking
# -----------------------------


def _chunk_text(text: str, max_chars: int = 5500, overlap: int = 300) -> Iterable[str]:
    """Yield overlapping chunks of text for long inputs to reduce truncation risk."""
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
    """Call Ollama via HTTP; concatenate streamed chunks into a single string."""
    import http.client
    import json as _json

    conn = http.client.HTTPConnection("localhost", 11434, timeout=timeout_s)
    body = _json.dumps(
        {
            "model": model,
            "system": _SYSTEM_PREAMBLE,
            "prompt": user_prompt,
            "options": {
                "temperature": 0,
                "top_p": 1,
                "repeat_penalty": 1.0,
                "num_ctx": 8192,
            },
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
            piece = json.loads(line.decode("utf-8"))
            raw_chunks.append(piece.get("response", ""))
            if piece.get("done"):
                break
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Ignore partial/garbled stream fragments; keep reading.
            continue
    return "".join(raw_chunks)


def _call_ollama_cli(model: str, user_prompt: str, timeout_s: int = 180) -> str:
    """Fallback to the `ollama run` CLI if the HTTP endpoint is unavailable."""
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
        raise RuntimeError(
            f"Ollama CLI error {proc.returncode}: {proc.stderr.decode('utf-8', 'ignore')}"
        )
    return proc.stdout.decode("utf-8", "ignore")


def _ask_model(
    model: str, user_prompt: str, timeout_s: int = 180, debug: bool = False
) -> str:
    """Try HTTP first, then CLI; return the raw model text."""
    try:
        out = _call_ollama_http(model, user_prompt, timeout_s=timeout_s)
        if debug:
            logger.debug("used Ollama HTTP")
        return out
    except (RuntimeError, OSError) as e_http:
        if debug:
            logger.debug("HTTP failed: %s. Falling back to CLI...", e_http)
        out = _call_ollama_cli(model, user_prompt, timeout_s=timeout_s)
        if debug:
            logger.debug("used Ollama CLI")
        return out


# -----------------------------
# Parsing & validation primitives
# -----------------------------


def _slice_between_sentinels(text: str) -> Optional[str]:
    """Return the substring between <<<JSON and JSON>>> if present."""
    i = text.find(_JSON_START)
    if i < 0:
        return None
    j = text.find(_JSON_END, i + len(_JSON_START))
    if j < 0:
        return None
    return text[i + len(_JSON_START) : j].strip()


def _ensure_list(obj: Any) -> Optional[List[Any]]:
    """Identity if obj is a list; otherwise None."""
    return obj if isinstance(obj, list) else None


def _dict_looks_like_item(obj: Any) -> bool:
    """Heuristic: object contains the three required keys."""
    return (
        isinstance(obj, dict)
        and "hpo_id" in obj
        and "hpo_label" in obj
        and "evidence" in obj
    )


_JSON_ARRAY_FINDER = re.compile(r"\[\s*\{.*?\}\s*\]", flags=re.DOTALL)
_RESULTS_ARRAY_FINDER = re.compile(
    r'"results"\s*:\s*(\[\s*\{.*?\}\s*\])', flags=re.DOTALL
)


def _find_any_json_array_block(text: str) -> Optional[str]:
    """Return the first top-level-looking JSON array block, if any."""
    m = _JSON_ARRAY_FINDER.search(text or "")
    return m.group(0) if m else None


def _find_results_array(text: str) -> Optional[str]:
    """Return the JSON array inside a 'results': [...] envelope, if present."""
    m = _RESULTS_ARRAY_FINDER.search(text or "")
    return m.group(1) if m else None


def _validate_and_filter_items(
    items: Iterable[Dict[str, Any]],
    source_text: str,
    max_items: int,
    apply_seizure_blocker: bool = True,
) -> List[Dict[str, str]]:
    """
    Validate candidate items and drop evidence. Enforces:
      - hpo_id matches ^HP:\d{7}$
      - hpo_label is non-empty
      - evidence is an exact substring of the source text (case-insensitive)
      - optional seizure drift guard when 'seiz' not in source text
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
        if evidence.lower() not in text_lower:
            continue
        if not allow_seizure and hpo_label in _COMMON_FAKE_DEFAULTS:
            continue

        out.append({"hpo_id": hpo_id, "hpo_label": hpo_label})
        if len(out) >= max_items:
            break
    return out


# -----------------------------
# Parsing strategies (split to reduce complexity)
# -----------------------------


def _try_parse_with_sentinels(
    raw_text: str, source_text: str, max_items: int, debug: bool, chunk_idx: Any
) -> List[Dict[str, str]]:
    parsed = _slice_between_sentinels(raw_text)
    if parsed is None:
        return []
    try:
        arr = json.loads(parsed)
        items = _validate_and_filter_items(arr, source_text, max_items=max_items)
        if debug:
            logger.debug(
                "[extract] Chunk %s: validated %d item(s) via sentinels.",
                chunk_idx,
                len(items),
            )
        return items
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _try_parse_with_array_scavenger(
    raw_text: str, source_text: str, max_items: int, debug: bool, chunk_idx: Any
) -> List[Dict[str, str]]:
    scavenged = _find_any_json_array_block(raw_text)
    if not scavenged:
        return []
    try:
        arr = json.loads(scavenged)
        items = _validate_and_filter_items(arr, source_text, max_items=max_items)
        if debug:
            logger.debug(
                "[extract] Chunk %s: validated %d item(s) via array scavenger.",
                chunk_idx,
                len(items),
            )
        return items
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _try_parse_with_results_array(
    raw_text: str, source_text: str, max_items: int, debug: bool, chunk_idx: Any
) -> List[Dict[str, str]]:
    results_arr = _find_results_array(raw_text)
    if not results_arr:
        return []
    try:
        arr = json.loads(results_arr)
        items = _validate_and_filter_items(arr, source_text, max_items=max_items)
        if debug:
            logger.debug(
                "[extract] Chunk %s: validated %d item(s) from results[].",
                chunk_idx,
                len(items),
            )
        return items
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _try_parse_with_single_object(
    raw_text: str, source_text: str, max_items: int, debug: bool, chunk_idx: Any
) -> List[Dict[str, str]]:
    try:
        maybe = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not _dict_looks_like_item(maybe):
        return []
    items = _validate_and_filter_items([maybe], source_text, max_items=max_items)
    if debug:
        logger.debug(
            "[extract] Chunk %s: validated %d item(s) from single-object.",
            chunk_idx,
            len(items),
        )
    return items


# -----------------------------
# Per-chunk parse/validate orchestration
# -----------------------------


def _parse_and_validate_chunk_output(
    raw_text: str,
    source_text: str,
    max_items: int,
    debug_logging: bool,
    chunk_idx: Optional[int] = None,
) -> List[Dict[str, str]]:
    """
    Try multiple parsing strategies (in order of preference) against one chunk's
    raw model output. Returns the first non-empty list of validated items.
    """
    strategies: List[Callable[[str, str, int, bool, Any], List[Dict[str, str]]]] = [
        _try_parse_with_sentinels,
        _try_parse_with_array_scavenger,
        _try_parse_with_results_array,
        _try_parse_with_single_object,
    ]
    for strat in strategies:
        items = strat(raw_text, source_text, max_items, debug_logging, chunk_idx)
        if items:
            return items
    return []


# -----------------------------
# Public API
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
    Extract HPO terms from clinical text via an Ollama-served model.

    The text is chunked to avoid context truncation. We accept the first chunk that
    yields valid items. If none do, we retry once on the first chunk with a
    tightened output-only instruction.
    """
    if not isinstance(clinical_text, str) or not clinical_text.strip():
        return ([], None)

    items: List[Dict[str, str]] = []
    raw_text_accum: List[str] = []

    for chunk_idx, text_chunk in enumerate(
        _chunk_text(
            clinical_text, max_chars=chunk_max_chars, overlap=chunk_overlap_chars
        ),
        start=1,
    ):
        user_prompt = _format_user_prompt(text_chunk, max_items=max_pheno_items)
        if debug_logging:
            logger.debug(
                "[extract] Sending chunk %d to model (len=%d).",
                chunk_idx,
                len(text_chunk),
            )
        raw_text = _ask_model(
            model, user_prompt, timeout_s=timeout_s, debug=debug_logging
        )
        raw_text_accum.append(raw_text or "")

        items = _parse_and_validate_chunk_output(
            raw_text,
            text_chunk,
            max_items=max_pheno_items,
            debug_logging=debug_logging,
            chunk_idx=chunk_idx,
        )
        if items:
            break

    if not items:
        # One full retry on the first chunk only (fail-closed behavior).
        first_chunk = next(
            _chunk_text(
                clinical_text, max_chars=chunk_max_chars, overlap=chunk_overlap_chars
            ),
            "",
        )
        retry_prompt = _format_retry_prompt(first_chunk, max_items=max_pheno_items)
        if debug_logging:
            logger.debug(
                "[extract] No valid items after chunks → single full retry on first chunk."
            )
        raw_text_retry = _ask_model(
            model, retry_prompt, timeout_s=timeout_s, debug=debug_logging
        )
        raw_text_accum.append("\n--- RETRY ---\n" + (raw_text_retry or ""))

        items = _parse_and_validate_chunk_output(
            raw_text_retry,
            first_chunk,
            max_items=max_pheno_items,
            debug_logging=debug_logging,
            chunk_idx="retry",
        )

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
    Construct a minimal Phenopacket dict from validated HPO items
    (no ontology lookup or normalization is performed).
    """
    phenos: List[Dict[str, Any]] = []
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
