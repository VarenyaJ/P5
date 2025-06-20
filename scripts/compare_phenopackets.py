from typing import Any, List, Tuple, Union

from jsoncomparison import Compare, NO_DIFF


def _count_leaf_fields(reference_json: Any) -> int:
   """
   Count the number of leaf fields in a JSON-like structure.

   A "leaf field" is any non-dict, non-list value.
   Conventions:
     - Empty dict `{}` counts as 1 leaf (field with no children).
     - Empty list `[]` counts as 0 leaves.

   Parameters
   ----------
   reference_json : Any
       A dict, list, or scalar value.

   Returns
   -------
   int
       Total number of leaf fields.
   """
   if isinstance(reference_json, dict):
       total = sum(_count_leaf_fields(v) for v in reference_json.values())
       return total or 1
   if isinstance(reference_json, list):
       return sum(_count_leaf_fields(item) for item in reference_json)
   return 1


def _count_extra_keys(
   reference_json: Union[dict, List[Any]],
   experimental_intake_json: Union[dict, List[Any]]
) -> int:
   """
   Count keys present in experimental_intake_json but absent from reference_json.

   Each extra key at any nesting level is a False Positive.

   Parameters
   ----------
   reference_json : dict or list
   experimental_intake_json : dict or list

   Returns
   -------
   int
       Number of extra dict keys.
   """
   extra = 0
   if isinstance(reference_json, dict) and isinstance(experimental_intake_json, dict):
       missing = set(experimental_intake_json) - set(reference_json)
       extra += len(missing)
       for key in set(reference_json) & set(experimental_intake_json):
           extra += _count_extra_keys(
               reference_json[key], experimental_intake_json[key]
           )
   elif isinstance(reference_json, list) and isinstance(experimental_intake_json, list):
       for ref_item, cand_item in zip(reference_json, experimental_intake_json):
           extra += _count_extra_keys(ref_item, cand_item)
   return extra


def _tally_diff_fp_fn(diff_tree: Any) -> Tuple[int, int]:
   """
   Walk a jsoncomparison diff tree to count FPs and FNs.

   * If diff_tree is a dict whose "_message" is "Lengths not equal", treat it
     as a single list-length mismatch (stop immediately).
   * If diff_tree is a bare tuple of two ints, same deal.
   * Otherwise, recurse into dicts:
       - "Values not equal" or "Types not equal" => +1 FP & +1 FN
       - "Key does not exists" or "Value not found" => +1 FN
       - "Lengths not equal" => +N FP or +N FN (stop that branch)

   Parameters
   ----------
   diff_tree : Any
       The output of Compare().check(...), either NO_DIFF, a dict tree,
       or an (expected, received) tuple.

   Returns
   -------
   (fp_count, fn_count)
   """
   # 1) Root-dict length mismatch short-circuit:
   if isinstance(diff_tree, dict):
       root_msg = diff_tree.get("_message", "")
       if "Lengths not equal" in root_msg:
           exp, rec = diff_tree.get("_expected", 0), diff_tree.get("_received", 0)
           if rec > exp:
               return rec - exp, 0
           if exp > rec:
               return 0, exp - rec
           return 0, 0

   # 2) Tuple form length mismatch:
   if isinstance(diff_tree, tuple) and len(diff_tree) == 2 and all(isinstance(x, int) for x in diff_tree):
       exp, rec = diff_tree
       if rec > exp:
           return rec - exp, 0
       if exp > rec:
           return 0, exp - rec
       return 0, 0

   # 3) Perfect match:
   if diff_tree is NO_DIFF:
       return 0, 0

   # 4) Recurse into diff dicts:
   def _recurse(node: Any) -> Tuple[int, int]:
       fp_local = fn_local = 0
       if not isinstance(node, dict):
           return 0, 0

       msg = node.get("_message", "")
       if "Values not equal" in msg or "Types not equal" in msg:
           fp_local += 1
           fn_local += 1
       elif "Key does not exists" in msg or "Value not found" in msg:
           fn_local += 1
       elif "Lengths not equal" in msg:
           exp, rec = node.get("_expected", 0), node.get("_received", 0)
           if rec > exp:
               fp_local += rec - exp
           elif exp > rec:
               fn_local += exp - rec
           return fp_local, fn_local  # stop this branch

       for child in node.values():
           cfp, cfn = _recurse(child)
           fp_local += cfp
           fn_local += cfn

       return fp_local, fn_local

   return _recurse(diff_tree)


def compare_jsons(
   reference_json: Union[dict, List[Any]],
   experimental_intake_json: Union[dict, List[Any], str]
) -> dict[str, int]:
   """
   Compare two JSON-like structures and compute TP, FP, FN.

   Parameters
   ----------
   reference_json : dict or list
       The ground-truth phenopacket (or any JSON).
   experimental_intake_json : dict, list, or str
       The JSON under test, or anything else (treated as totally invalid).

   Returns
   -------
   dict[str, int]
       {"TP": int, "FP": int, "FN": int}
   """
   total_expected = _count_leaf_fields(reference_json)

   # Non-JSON input => all FN+FP
   if not isinstance(experimental_intake_json, (dict, list)):
       return {"TP": 0, "FP": total_expected, "FN": total_expected}

   extra_fp = _count_extra_keys(reference_json, experimental_intake_json)

   try:
       diff_tree = Compare().check(reference_json, experimental_intake_json)
   except Exception:
       # If the library blows up, treat as completely wrong
       return {"TP": 0, "FP": total_expected, "FN": total_expected}

   diff_fp, diff_fn = _tally_diff_fp_fn(diff_tree)
   fp = extra_fp + diff_fp
   fn = diff_fn
   tp = max(total_expected - fn, 0)

   return {"TP": tp, "FP": fp, "FN": fn}


def compute_prf(metrics: dict[str, int]) -> dict[str, float]:
   """
   Compute precision, recall, and F1 score from TP/FP/FN.

   Parameters
   ----------
   metrics : dict[str, int]
       Must contain "TP", "FP", and "FN".

   Returns
   -------
   dict[str, float]
       {"precision": float, "recall": float, "f1": float}
   """
   tp, fp, fn = metrics.get("TP", 0), metrics.get("FP", 0), metrics.get("FN", 0)

   precision = tp / (tp + fp) if (tp + fp) else 0.0
   recall    = tp / (tp + fn) if (tp + fn) else 0.0
   f1        = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

   return {"precision": precision, "recall": recall, "f1": f1}