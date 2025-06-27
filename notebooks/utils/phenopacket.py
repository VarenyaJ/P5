import json
import copy
import logging
from logging import NullHandler
from typing import Any, List
from google.protobuf.json_format import ParseDict, ParseError
from phenopackets import Phenopacket as ProtoPhenopacket

# Create a module-named logger and attach a NullHandler so this library never prints logs unless an application specifically configures logging
logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())


class InvalidPhenopacketError(ValueError):
    """
    Exception raised when a JSON payload does not conform to minimal Phenopacket expectations.
    """


class Phenopacket:

    def __init__(self, phenopacket_json: Any) -> None:
        """
        Initialize and validate a Phenopacket instance.

        This constructor enforces the GA4GH Phenopacket schema in one step:
            1. Parses and validates the entire JSON payload against the Protobuf definition via ParseDict (raising ParseError on schema mismatch).
            2. Attempts to extract `phenotypicFeatures` (raising KeyError if missing, or TypeError if the payload is not indexable as a dict).

        Any caught TypeError, KeyError, or ParseError is re-raised as InvalidPhenopacketError.

        Parameters
        ----------
        phenopacket_json : Any
        A JSON-decoded object expected to be a dict representing a GA4GH Phenopacket, with `phenotypicFeatures` as a list of feature dicts.

        Raises
        ------
        InvalidPhenopacketError
            If validation or extraction fails for any reason.
        """
        logger.debug("Initializing and Validating Phenopacket")
        try:
            _ = ParseDict(phenopacket_json, ProtoPhenopacket())
            feats = phenopacket_json["phenotypicFeatures"]
        except (TypeError, ParseError) as e:
            logger.error("Failed to validate phenopacket: %s", e, exc_info=True)
            raise InvalidPhenopacketError(f"Failed to validate phenopacket: {e}")

        # If we reach this step then phenopacket_json is guaranteed to be valid, so we can successfully cache the raw JSON and the features list
        self._json = phenopacket_json
        # We assume the Protobuf-validated dict always has this key:
        self._phenotypicFeatures: List[dict[str, Any]] = feats
        logger.info(f"Successfully validated %d phenotypic feature(s)", len(feats))
        logger.debug("Successfully validated phenotypic feature(s): %r", feats)

    @classmethod
    def load_from_file(cls, path: str) -> "Phenopacket":
        """
        Load a Phenopacket from a JSON file and validate it.

        Steps:
            1. Open the file at `path` (FileNotFoundError if missing).
            2. Parse its contents as JSON (JSONDecodeError on invalid JSON).
            3. Delegate to __init__ for schema validation.

        Parameters
        ----------
        path : str
            Path to the .json file containing a GA4GH Phenopacket.

        Returns
        -------
        Phenopacket
            A validated Phenopacket instance.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        json.JSONDecodeError
            If the file contents are not valid JSON.
        InvalidPhenopacketError
            If the JSON payload fails GA4GH schema validation.
        """
        logger.debug("Loading Phenopacket from file: %s", path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Loaded JSON data from %s", path)
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
        present = hpo_label in self.list_phenotypes()
        logger.debug("Checking for phenotype %r: %s", hpo_label, present)
        return present

    @property
    def count_phenotypes(self) -> int:
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
        labels = [feat["type"]["label"] for feat in self._phenotypicFeatures]
        logger.debug("Listing phenotypes: %r", labels)
        return labels

    def to_json(self) -> dict[str, Any]:
        """
        Return a deep copy of the original JSON dict to avoid external mutations because returning the exact same dict/internal state allows for accidental mutations
        """
        logger.debug("Creating deep copy of original JSON")
        return copy.deepcopy(self._json)

    def __repr__(self) -> str:
        return f"<Phenopacket phenotypes={self.count_phenotypes}>"

    def __str__(self) -> str:
        """
        Output a Human-friendly summary of this Phenopacket if count is zero.
        """
        c = self.count_phenotypes
        if c == 0:
            return "Phenopacket with no phenotypic features"
        return f"Phenopacket with {c} phenotypic feature{'s' if c != 1 else ''}"
