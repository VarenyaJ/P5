# P5/notebooks/utils/phenopacket.py

import json
import logging
import os
from typing import Any, List

logger = logging.getLogger(__name__)


class InvalidPhenopacketError(ValueError):
  """Raised when a given JSON does not conform to minimal phenopacket expectations."""


class Phenopacket:
  """
  A helper for loading and querying GA4GH Phenopacket JSON files.
  """
  # CHANGED: moved all details into init

  def __init__(self, phenopacket_json: dict[str, Any]):
      """
      Initialize from a JSON-decoded dict.

      Parameters
      ----------
      phenopacket_json : dict
          Parsed JSON object for a phenopacket.
          A valid phenopacket must be a dict containing:
          - "phenotypicFeatures": a list of feature objects, each with a "type" dict:
              {
                "id": "HP:0000001",
                "label": "Phenotype label"
              }

      Raises
      ------
      InvalidPhenopacketError
          If the input is not a dict or phenotypicFeatures is malformed.
      """

      self._validate_structure(phenopacket_json)
      self._json: dict[str, Any] = phenopacket_json
      self._phenotypicFeatures: List[dict[str, Any]] = phenopacket_json["phenotypicFeatures"]

  @staticmethod
  def _validate_structure(data: dict[str, Any]) -> None:
      """ Minimal schema checks extracted from __init__; Raises InvalidPhenopacketError on failure. """
      if not isinstance(data, dict):
          raise InvalidPhenopacketError("Phenopacket JSON must be a dict.")
      features = data.get("phenotypicFeatures", [])
      if not isinstance(features, list):
          raise InvalidPhenopacketError("`phenotypicFeatures` must be a list.")
      # - All other validation can be centralized here per Rouven's suggestion.

  @classmethod
  def load_from_file(cls, path: str) -> "Phenopacket":
      """
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

      # CHANGED: removed explicit os.path.isfile check; open()/json.load() will raise if missing or invalid
      with open(path, "r", encoding="utf-8") as f:
          data = json.load(f)
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
      # CHANGED: simplified to single line, using list_phenotypes()
      return hpo_label in self.list_phenotypes()

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
      Get the number of phenotypic features, reutrn an `int` length of the `phenotypicFeatures` list.
      """
      return len(self._phenotypicFeatures)

  def list_phenotypes(self) -> List[str]:
      """
      List all human-readable phenotype labels in a phenopacket.

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

  def to_json(self) -> dict[str, Any]:
      """
      Return the original JSON dict.

      Returns
      -------
      dict
          The raw JSON object loaded at init.
      """
      return self._json

  def __repr__(self) -> str:
      return f"<Phenopacket phenotypes={self.count_phenotypes}>"

  def __str__(self) -> str:
      """
      Human-friendly string for printing.

      Returns
      -------
      str
          e.g. "Phenopacket with 3 phenotypic features"
      """
      c = self.count_phenotypes

      # CHANGED: Add explicit zero case
      if c == 0:
          return "Phenopacket with no phenotypic features"
      return f"Phenopacket with {c} phenotypic feature{'s' if c != 1 else ''}"

  #


#