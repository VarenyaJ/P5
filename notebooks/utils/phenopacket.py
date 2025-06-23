# P5/notebooks/utils/phenopacket.py

import json
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class InvalidPhenopacketError(ValueError):
    """Raised when a given JSON does not conform to minimal phenopacket expectations."""


class Phenopacket:
    """
    A helper for loading and querying GA4GH Phenopacket JSON files.

    A valid phenopacket must be a dict containing:
      - "phenotypicFeatures": a list of feature objects, each with a "type" dict:
            {
              "id": "HP:0000001",
              "label": "Phenotype label"
            }
    """

    def __init__(self, phenopacket_json: Dict[str, Any]) -> None:
        """
        Initialize from a JSON-decoded dict.

        Parameters
        ----------
        phenopacket_json : dict
            Parsed JSON object for a phenopacket.

        Raises
        ------
        InvalidPhenopacketError
            If the input is not a dict or phenotypicFeatures is malformed.
        """
        if not isinstance(phenopacket_json, dict):
            raise InvalidPhenopacketError("Phenopacket JSON must be a dict.")
        phenotypicFeatures = phenopacket_json.get("phenotypicFeatures", [])
        if not isinstance(phenotypicFeatures, list):
            raise InvalidPhenopacketError("`phenotypicFeatures` must be a list.")
        self._json: Dict[str, Any] = phenopacket_json
        self._phenotypicFeatures: List[Dict[str, Any]] = phenotypicFeatures

    @classmethod
    def load_from_file(cls, path: str) -> "Phenopacket":
        """
        Load a phenopacket JSON file from disk.

        Parameters
        ----------
        path : str
            Path to a .json file containing a GA4GH phenopacket.

        Returns
        -------
        Phenopacket
            Instance wrapping the loaded JSON.

        Raises
        ------
        FileNotFoundError
            If the given path does not exist.
        json.JSONDecodeError
            If the file cannot be parsed as JSON.
        InvalidPhenopacketError
            If the loaded JSON has the wrong structure.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load_from_file(f)
        return cls(data)

    def contains_phenotype(self, hpo_label: str) -> bool:
        """
        Check for presence of a phenotype by its human-readable label.

        Parameters
        ----------
        hpo_label : str
            The `type.label` of the phenotype to search for.

        Returns
        -------
        bool
            True if any feature has a matching label, False otherwise.
        """
        for feat in self._phenotypicFeatures:
            if not isinstance(feat, dict):
                logger.warning("Skipping malformed phenotypicFeature: not a dict")
                continue
            term = feat.get("type")
            if not isinstance(term, dict):
                logger.warning(
                    "Skipping malformed phenotypicFeature: no or non-dict `type` field"
                )
                continue
            if term.get("label") == hpo_label:
                return True
        return False

    def contains_phenotype_id(self, hpo_id: str) -> bool:
        """
        Check for presence by exact HPO identifier.

        Parameters
        ----------
        hpo_id : str
            The `type.id` of the phenotype to search for (e.g. "HP:0001250").

        Returns
        -------
        bool
            True if any feature has a matching id, False otherwise.
        """
        return any(
            isinstance(feat, dict)
            and isinstance(feat.get("type"), dict)
            and feat["type"].get("id") == hpo_id
            for feat in self._phenotypicFeatures
        )

    @property
    def count_phenotypes(self) -> int:
        """
        Get the number of phenotypic features.

        Returns
        -------
        int
            Length of the `phenotypicFeatures` list.
        """
        return len(self._phenotypicFeatures)

    def list_phenotypes(self) -> List[str]:
        """
        List all human-readable phenotype labels.

        Returns
        -------
        List[str]
            The `type.label` of each feature, skipping malformed entries.
        """
        labels: List[str] = []
        for feat in self._phenotypicFeatures:
            term = feat.get("type")
            if isinstance(term, dict) and "label" in term:
                labels.append(term["label"])
            else:
                logger.warning(
                    "Skipping malformed phenotypicFeature: missing `type.label`"
                )
        return labels

    def to_json(self) -> Dict[str, Any]:
        """
        Return the original JSON dict.

        Returns
        -------
        dict
            The raw JSON object loaded at init.
        """
        return self._json

    def __repr__(self) -> str:
        """
        Unambiguous representation, useful in REPL/debug sessions.

        Returns
        -------
        str
            e.g. "<Phenopacket phenotypes=3>"
        """
        return f"<Phenopacket phenotypes={self.count_phenotypes}>"

    def __str__(self) -> str:
        """
        Human-friendly string for printing.

        Returns
        -------
        str
            e.g. "Phenopacket with 3 phenotypic features"
        """
        return (
            f"Phenopacket with {self.count_phenotypes} "
            f"phenotypic feature{'s' if self.count_phenotypes != 1 else ''}"
        )

    #


#
