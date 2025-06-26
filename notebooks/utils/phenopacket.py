import json
import copy
import logging
from typing import Any, List
from google.protobuf.json_format import ParseDict, ParseError
from phenopackets import Phenopacket as ProtoPhenopacket

logger = logging.getLogger(__name__)


class InvalidPhenopacketError(ValueError):
    """
    Exception raised when a JSON payload does not conform to minimal Phenopacket expectations.
    """


class Phenopacket:

    def __init__(self, phenopacket_json: Any) -> None:
        """
        Initialize a Phenopacket by validating and storing its JSON payload.
        This constructor enforces the full GA4GH Phenopacket schema in one step using Protobuf's ParseDict. It verifies that:
            1. The input is a mapping (i.e. dict-like).
            2. A `phenotypicFeatures` field exists and is a list.
            3. Each feature dict contains at least a `type.id` and `type.label`.

        On success, the raw JSON is stored, and the list of phenotypic features is cached for fast queries. Any schema mismatch or wrong top-level type is caught and re-raised as InvalidPhenopacketError.

        Parameters
        ----------
        phenopacket_json : Any
            A JSON-decoded object representing a GA4GH Phenopacket. Must be a dict with a `"phenotypicFeatures"` key mapping to a list of valid feature dicts.

        Raises
        ------
        InvalidPhenopacketError
            If the input is not a dict or if it fails Protobuf validation (e.g. missing or malformed `phenotypicFeatures`, wrong nested fields).
        """

        # Have one validation mechanic for everything: TypeError if phenopacket_json is not a dict, and ParseError if required fields/types are missing or incorrect
        try:
            _ = ParseDict(phenopacket_json, ProtoPhenopacket())
        except (TypeError, ParseError) as e:
            raise InvalidPhenopacketError(f"Failed to validate phenopacket: {e}")

        # If we reach this step then phenopacket_json is guaranteed to be valid
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
        # Removed explicit os.path.isfile check because `open(path)` raises FileNotFoundError already

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
        # lean on Protobuf guarantees
        # What: Simplified to a comprehension without defensive guards
        # Where: list_phenotypes
        # Why: After Protobuf & constructor validation, `.type.label` must exist
        return [feat["type"]["label"] for feat in self._phenotypicFeatures]

    def to_json(self) -> dict[str, Any]:
        """
        Return a deep copy of the original JSON dict to avoid external mutations
        """
        # Returning the exact same dict/internal state allows for accidental mutation
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
