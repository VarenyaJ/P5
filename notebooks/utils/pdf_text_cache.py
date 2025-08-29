"""
notebooks/utils/pdf_text_cache.py

Lightweight, persistent PDF→text caching for clinical documents.

Usage:
    from notebooks.utils.pdf_text_cache import PdfTextCache

    cache = PdfTextCache(experimental_data_root=experimental_data_root)
    text  = cache.get_text("/abs/path/to/document.pdf")  # or .txt
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Dict

from docling.document_converter import DocumentConverter, ConversionError
from pypdfium2._helpers.misc import PdfiumError


class PdfTextCache:
    """
    Convert PDFs (or read .txt) to plain text with a persistent cache.

    - Cache file lives at: <experimental_data_root>/text_cache/cache.pkl
    - If a file path is present in cache, return cached text
    - If path ends with .txt, read as UTF-8 and strip optional "[text]" header
    - If path ends with .pdf, convert with docling DocumentConverter
    """

    def __init__(self, experimental_data_root: str):
        self.experimental_data_root = experimental_data_root
        self.cache_dir = Path(experimental_data_root) / "text_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / "cache.pkl"

        self._converter = DocumentConverter()
        self._cache: Dict[str, str] = self._load_cache()

    # ---------- public API ----------

    def get_text(self, input_path: str) -> str:
        """
        Return plain text for the given input_path (.pdf or .txt).
        Uses in-memory + on-disk caching to avoid rework.

        Raises:
            FileNotFoundError, ConversionError, PdfiumError
        """
        if input_path in self._cache:
            return self._cache[input_path]

        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if input_path.lower().endswith(".txt"):
            text = self._read_txt(input_path)
        else:
            text = self._convert_pdf_to_text(input_path)

        self._cache[input_path] = text
        self._persist_cache()
        return text

    # ---------- internals ----------

    def _read_txt(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Some of our sources may prepend a marker like "[text]"; strip if present
        if "[text]" in content:
            content = content.split("[text]", 1)[-1]
        return content

    def _convert_pdf_to_text(self, path: str) -> str:
        try:
            doc = self._converter.convert(path)
            return doc.document.export_to_text()
        except (ConversionError, PdfiumError) as e:
            raise ConversionError(f"Could not convert {os.path.basename(path)}: {e}")

    def _load_cache(self) -> Dict[str, str]:
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "rb") as f:
                    return pickle.load(f)
            except Exception:
                # Corrupt cache → start fresh
                return {}
        return {}

    def _persist_cache(self) -> None:
        try:
            with open(self.cache_path, "wb") as f:
                pickle.dump(self._cache, f)
        except Exception:
            # Non-fatal: if persistence fails, in-memory cache still helps
            pass
