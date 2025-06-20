# scripts/compare_phenopackets.py

from typing import Any, Union, List, Tuple
from jsoncomparison import Compare, NO_DIFF


def _count_leaf_fields(node: Any) -> int:
    """
    Recursively count leaf fields in a JSON-like structure.

    A leaf is any non-list, non-dict value. By convention:
      - {} → 1 leaf   (a field with no children)
      - [] → 0 leaves (an empty list)
    """
    if isinstance(node, dict):
        total = sum(_count_leaf_fields(v) for v in node.values())
        return total or 1
    if isinstance(node, list):
        return sum(_count_leaf_fields(v) for v in node)
    return 1


def _count_extra_keys(
    reference: Union[dict, List[Any]], candidate: Union[dict, List[Any]]
) -> int:
    """
    Count keys in `candidate` that are not present in `reference`.
    Each extra key at any nesting level counts as +1 FP.
    """
    extra = 0
    if isinstance(reference, dict) and isinstance(candidate, dict):
        new_keys = set(candidate) - set(reference)
        extra += len(new_keys)
        for key in set(reference) & set(candidate):
            extra += _count_extra_keys(reference[key], candidate[key])
    elif isinstance(reference, list) and isinstance(candidate, list):
        for r, c in zip(reference, candidate):
            extra += _count_extra_keys(r, c)
    return extra


def _tally_diff_fp_fn(diff: Any) -> Tuple[int, int]:
    """
    Walk a jsoncomparison diff tree to count (FP, FN).

    Special‐cased for list‐length mismatches:
      - jsoncomparison often reports them as a 2-tuple of ints,
        but it overcounts “missing” by 2×. We halve that delta.
    """
    # 1) Perfect match
    if diff is NO_DIFF:
        return 0, 0

    # 2) Root‐dict length mismatch (sometimes lists come back as dicts)
    if isinstance(diff, dict) and "Lengths not equal" in diff.get("_message", ""):
        exp = diff.get("_expected", 0)
        rec = diff.get("_received", 0)
        if rec > exp:
            return rec - exp, 0
        if exp > rec:
            return 0, exp - rec
        return 0, 0

    # 3) Pure tuple/list of ints → list-length diff
    if (
        isinstance(diff, (list, tuple))
        and len(diff) == 2
        and all(isinstance(x, int) for x in diff)
    ):
        a, b = diff
        if a > b:
            # candidate longer → FP = a
            return a, 0
        if b > a:
            # candidate shorter → raw missing=b-a,
            # but jsoncomparison reports 2× the true missing count
            return 0, (b - a) // 2
        return 0, 0

    # 4) Generic dict‐node: value/type mismatches & missing keys
    if isinstance(diff, dict):
        fp = fn = 0
        msg = diff.get("_message", "")
        if "Values not equal" in msg or "Types not equal" in msg:
            fp += 1
            fn += 1
        elif "Key does not exists" in msg or "Value not found" in msg:
            fn += 1
        # Recurse
        for child in diff.values():
            c_fp, c_fn = _tally_diff_fp_fn(child)
            fp += c_fp
            fn += c_fn
        return fp, fn

    # 5) Anything else → no errors here
    return 0, 0


def compute_prf(metrics: dict[str, int]) -> dict[str, float]:
    """
    Compute precision, recall, and F1 from TP/FP/FN.

    precision = TP/(TP+FP) or 0.0 if denom=0
    recall    = TP/(TP+FN) or 0.0 if denom=0
    f1        = 2*P*R/(P+R) or 0.0 if denom=0
    """
    tp = metrics.get("TP", 0)
    fp = metrics.get("FP", 0)
    fn = metrics.get("FN", 0)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    )

    return {"precision": precision, "recall": recall, "f1": f1}


def compare_jsons(
    reference_json: Union[dict, List[Any]], candidate_json: Union[dict, List[Any], str]
) -> dict[str, int]:
    """
    Compare two JSON‐like objects and return {"TP", "FP", "FN"}.

    - TP: correctly extracted fields
    - FP: extra or wrong fields in candidate
    - FN: missing or wrong fields vs. reference

    If `candidate_json` isn’t a dict/list, it’s treated as entirely invalid.
    """
    total_expected = _count_leaf_fields(reference_json)

    # entirely invalid → everything is FP & FN
    if not isinstance(candidate_json, (dict, list)):
        return {"TP": 0, "FP": total_expected, "FN": total_expected}

    # 1) extra‐key FPs
    extra_fp = _count_extra_keys(reference_json, candidate_json)

    # 2) structural diff
    try:
        diff_tree = Compare().check(reference_json, candidate_json)
    except Exception:
        return {"TP": 0, "FP": total_expected, "FN": total_expected}

    # 3) tally diff‐derived FP/FN
    diff_fp, diff_fn = _tally_diff_fp_fn(diff_tree)

    # 4) compute TP
    tp = max(total_expected - diff_fn, 0)

    return {"TP": tp, "FP": extra_fp + diff_fp, "FN": diff_fn}
