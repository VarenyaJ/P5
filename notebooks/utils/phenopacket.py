import json
import logging
import os
from typing import Any, List

from google.protobuf.json_format import ParseDict, ParseError
from phenopackets import Phenopacket as ProtoPhenopacket

logger = logging.getLogger(__name__)


class InvalidPhenopacketError(ValueError):
    """
    Exception raised when a JSON payload does not conform to minimal
    Phenopacket expectations.
    """


class Phenopacket:
    """
    Helper for loading and querying GA4GH Phenopacket JSON files.

    Wraps the Protobuf-based Phenopacket model from the `phenopackets` package,
    providing minimal on-disk loading, basic schema validation via Protobuf,
    and simple phenotype queries.
    """

    def __init__(self, phenopacket_json: dict[str, Any]) -> None:
        """
        Initialize Phenopacket from a JSON-decoded dictionary.

        Performs minimal structural validation (presence and type of
        `phenotypicFeatures`) before storing the raw dictionary for
        downstream queries.

        Parameters
        ----------
        phenopacket_json : dict
            A JSON-decoded dict representing a GA4GH Phenopacket. It must
            contain a key `"phenotypicFeatures"` mapped to a list of feature
            objects, each of which should be a dict with at least:

            {
                "type": {
                    "id": "<HPO:NNNNNNN>",
                    "label": "<Phenotype Label>"
                }
            }

        Raises
        ------
        InvalidPhenopacketError
            If `phenopacket_json` is not a dict or if
            `"phenotypicFeatures"` is missing or not a list.
        """
        # CHANGED: Introduced two separate validation mechanisms. No longer need the custom '_validate_structure' as 'google.protobuf.json_format' has 'ParseDict' and 'ParseError'
        self._json = phenopacket_json
        # We assume the Protobuf-validated dict always has this key:
        self._phenotypicFeatures: List[dict[str, Any]] = phenopacket_json[
            "phenotypicFeatures"
        ]

    @classmethod
    def load_from_file(cls, path: str) -> "Phenopacket":
        """
        Load and validate a Phenopacket from a JSON file on disk.

        Reads the file at `path`, parses it as JSON, then invokes Protobuf's
        `ParseDict` to enforce the full GA4GH schema. If parsing succeeds,
        the raw dict is passed to `__init__` for minimal structural checks.

        Parameters
        ----------
        path : str
            Filesystem path to a `.json` file containing a GA4GH Phenopacket.

        Returns
        -------
        Phenopacket
            An initialized Phenopacket instance.

        Raises
        ------
        FileNotFoundError
            If no file exists at `path`.
        InvalidPhenopacketError
            If JSON parsing fails or the Protobuf schema validation fails.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        try:
            # Full schema validation via Protobuf
            _ = ParseDict(data, ProtoPhenopacket())
        except ParseError as e:
            raise InvalidPhenopacketError(f"Failed to parse phenopacket: {e}")

        # Hand the validated dict to our constructor
        return cls(data)

    def contains_phenotype(self, hpo_label: str) -> bool:
        """
        Check for the presence of a phenotype by its human-readable label.

        Parameters
        ----------
        hpo_label : str
            The HPO term's `label` to search for (e.g. "Short stature").

        Returns
        -------
        bool
            True if any phenotypic feature's `type.label` matches exactly,
            False otherwise.
        """
        return hpo_label in self.list_phenotypes()

    @property
    def count_phenotypes(self) -> int:
        """
        Number of phenotypic features in the packet.

        Returns
        -------
        int
            The length of the `"phenotypicFeatures"` list.
        """
        return len(self._phenotypicFeatures)

    def list_phenotypes(self) -> List[str]:
        """
        List all human-readable phenotype labels in this packet.

        Iterates over each feature in `"phenotypicFeatures"` and extracts
        the `type.label` string.

        Returns
        -------
        List[str]
            A list of phenotype labels, in insertion order.
        """
        labels: List[str] = []
        for feat in self._phenotypicFeatures:
            term = feat.get("type")
            if isinstance(term, dict) and "label" in term:
                labels.append(term["label"])
        return labels

    def to_json(self) -> dict[str, Any]:
        """
        Retrieve the original JSON dictionary.

        Returns
        -------
        dict
            The exact dict passed to `__init__`.
        """
        return self._json

    def __repr__(self) -> str:
        return f"<Phenopacket phenotypes={self.count_phenotypes}>"

    def __str__(self) -> str:
        """
        Human-friendly summary of this Phenopacket.

        Returns
        -------
        str
            A string like "Phenopacket with 3 phenotypic features", or
            "Phenopacket with no phenotypic features" if count is zero.
        """
        c = self.count_phenotypes
        if c == 0:
            return "Phenopacket with no phenotypic features"
        return f"Phenopacket with {c} phenotypic feature{'s' if c != 1 else ''}"
