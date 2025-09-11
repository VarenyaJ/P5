# tests/notebooks/utils/test_pdf_text_cache.py
"""
Unit tests for notebooks.utils.pdf_text_cache.

We use a .txt input to avoid any PDF engine dependency. The cache should:
- return extracted text,
- persist a cache file under experimental_data_root/text_cache/cache.pkl,
- return the same text on a second call (reads from cache transparently).
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
   sys.path.insert(0, PROJECT_ROOT)

from notebooks.utils.pdf_text_cache import PdfTextCache  # noqa: E402


def test_pdf_text_cache_with_txt_input(tmp_path: Path):
   # Arrange
   experimental_root = tmp_path / "exp"
   experimental_root.mkdir(parents=True, exist_ok=True)

   txt = tmp_path / "note.txt"
   original_text = "alpha beta gamma"
   txt.write_text(original_text, encoding="utf-8")

   cache = PdfTextCache(experimental_data_root=str(experimental_root))

   # Act: first call extracts and caches
   t1 = cache.get_text(str(txt))

   # Assert: content matches
   assert t1 == original_text

   # Cache file should exist
   cache_pkl = experimental_root / "text_cache" / "cache.pkl"
   assert cache_pkl.exists()

   # Act: second call should produce the same text (likely via cache)
   t2 = cache.get_text(str(txt))
   assert t2 == original_text