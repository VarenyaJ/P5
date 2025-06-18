"""
compare_phenopackets.py

Provides `compare_jsons`, which compares two JSON-like structures
(e.g., generated vs. ground-truth phenopackets) and computes:
   - TP: True Positives (correctly extracted fields)
   - FP: False Positives (hallucinated or extra fields)
   - FN: False Negatives (missed or wrong fields)

We ignore True Negatives because in free-form information extraction
the "not-extracted" space is unbounded.

Dependencies:
   pip install jsoncomparison

Usage:
   from compare_phenopackets import compare_jsons
   metrics = compare_jsons(true_json_dict, generated_json_dict_or_str)
   print(metrics)  # -> {"TP": ..., "FP": ..., "FN": ...}
"""

from typing import Any, Dict, Union
from jsoncomparison import Compare, NO_DIFF

def compare_jsons(
   true_json: Any,
   gen_json: Union[Any, str]
) -> Dict[str, int]:
   """
   Compare generated JSON (`gen_json`) to ground-truth JSON (`true_json`).

   Returns:
       A dict with keys:
         - "TP": number of true positives
         - "FP": number of false positives
         - "FN": number of false negatives

   Behavior:
     1. Count all leaf fields in `true_json` to get `total_expected`.
     2. If `gen_json` is not a dict or list, treat as entirely invalid:
        FP = FN = total_expected, TP = 0.
     3. Recursively walk both JSONs to count **extra keys** in `gen_json`
        that aren't in `true_json`. Each extra key -> +1 FP.
     4. Use `jsoncomparison.Compare().check()` to compute a diff tree.
     5. Walk that diff tree to spot:
        - Wrong or mismatched values -> +1 FN, +1 FP
        - Missing fields -> +1 FN
        - List-length mismatches -> +N FN or +N FP
     6. TP = total_expected - FN (never negative).
   """

   def count_fields(obj: Any) -> int:
       """Recursively count all "leaf" fields in a JSON-like object."""
       if isinstance(obj, dict):
           # Sum over values; if empty dict, count as one field
           return sum(count_fields(v) for v in obj.values()) or 1
       if isinstance(obj, list):
           return sum(count_fields(v) for v in obj)
       # Any non-dict/list is one leaf field
       return 1

   total_expected = count_fields(true_json)

   # 2. Handle non-JSON output
   if not isinstance(gen_json, (dict, list)):
       return {"TP": 0, "FP": total_expected, "FN": total_expected}

   # 3. Count extra dict keys at all nesting levels
   def count_extra_keys(t: Any, g: Any) -> int:
       """
       Recursively count keys present in `g` but not in `t`.
       Works for nested dicts and lists-of-dicts.
       """
       extra = 0
       if isinstance(t, dict) and isinstance(g, dict):
           # Extra at this level:
           extra_keys = set(g.keys()) - set(t.keys())
           extra += len(extra_keys)
           # Recurse on shared keys:
           for key in set(t.keys()) & set(g.keys()):
               extra += count_extra_keys(t[key], g[key])
       elif isinstance(t, list) and isinstance(g, list):
           # Zip-pairwise up to shortest list:
           for item_t, item_g in zip(t, g):
               extra += count_extra_keys(item_t, item_g)
       return extra

   extra_fp = count_extra_keys(true_json, gen_json)

   # 4. Compute structural diff
   diff = Compare().check(true_json, gen_json)
   # 5a. Perfect match aside from extra keys
   if diff is NO_DIFF:
       return {
           "TP": total_expected,
           "FP": extra_fp,
           "FN": 0
       }

   # 5b. Walk diff tree for mismatches/missing/list errors
   fp = fn = 0

   def walk(node: Any):
       nonlocal fp, fn
       if not isinstance(node, dict):
           return

       msg = node.get("_message", "")
       # Wrong or type-mismatched value:
       if "Values not equal" in msg or "Types not equal" in msg:
           fn += 1
           fp += 1
       # Expected field missing in generated JSON:
       elif "Key does not exists" in msg or "Value not found" in msg:
           fn += 1
       # List-length mismatch:
       elif "Lengths not equal" in msg:
           exp = node.get("_expected", 0)
           rec = node.get("_received", 0)
           if exp > rec:
               fn += exp - rec
           elif rec > exp:
               fp += rec - exp

       # Recurse all children:
       for v in node.values():
           walk(v)

   walk(diff)

   # 5c. Add extra-key false positives
   fp += extra_fp

   # 6. Compute true positives
   tp = max(total_expected - fn, 0)

   return {"TP": tp, "FP": fp, "FN": fn}