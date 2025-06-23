# P5/notebooks/utils/phenopacket.py

import json
import os
from typing import Any, Dict, List, Optional


class Phenopacket:
    """
    A minimal helper class for working with GA4GH-style phenopacket JSON files.

    Phenopacket JSON is expected to contain a top-level key "phenotypicFeatures",
    which is a list of objects, each with a "type" field containing an HPO term:
        {
          "phenotypicFeatures": [
            {
              "type": {
                "id": "HP:0000001",
                "label": "Phenotype Label"
              },
              ...
            },
            ...
          ]
        }

    This class lets you load such a JSON, count its phenotypes, and test membership.
    """

    def __init__(self, phenopacket_json: Dict[str, Any]) -> None:
        """
        Initialize from a JSON-decoded dict.

        Parameters
        ----------
        phenopacket_json
            A dict parsed from a GA4GH phenopacket JSON file.
        """
        self._json = phenopacket_json
        # Safely grab the list of phenotypic features; default to empty list.
        self._features: List[Dict[str, Any]] = phenopacket_json.get(
            "phenotypicFeatures", []
        )

    @staticmethod
    def load(path: str) -> "Phenopacket":
        """
        Load a phenopacket JSON file from disk and return a Phenopacket instance.

        Parameters
        ----------
        path
            Path to a .json file containing a GA4GH phenopacket.

        Returns
        -------
        Phenopacket
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Phenopacket(data)

    def contains_phenotype(self, hpo_label: str) -> bool:
        """
        Check whether the phenopacket includes a given phenotype by its label.

        Parameters
        ----------
        hpo_label
            The human-readable name of an HPO term (e.g. "Short stature").

        Returns
        -------
        bool
            True if any phenotypicFeature has a type.label matching hpo_label.
        """
        for feat in self._features:
            term = feat.get("type", {})
            if term.get("label") == hpo_label:
                return True
        return False

    @property
    def count_phenotypes(self) -> int:
        """
        Count how many phenotypic features are in the phenopacket.

        Returns
        -------
        int
            Number of HPO-annotated phenotypes.
        """
        return len(self._features)
