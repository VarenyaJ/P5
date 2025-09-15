"""
notebooks/utils/hpo_batch.py

Batch LLM HPO extraction:
- Iterates aligned (pmid, input_path, patient_id) triples
- Calls the single-case extractor with chunking and timeouts
- Saves raw model output and a minimal predicted Phenopacket JSON
- Returns wrapped Phenopacket utils for downstream evaluation

Dependencies:
 - notebooks.utils.hpo_extraction
 - phenopacket.Phenopacket utility
"""

from pathlib import Path
from tqdm import tqdm
import logging
from .hpo_extraction import extract_hpo_terms, build_minimal_phenopacket_from_hpo_list
from .pdf_text_cache import PdfTextCache
from phenopacket import Phenopacket as UtilPhenopacket

logger = logging.getLogger(__name__)


def run_hpo_batch_inference(
   list_of_pmids_aligned,
   list_of_input_paths_aligned,
   list_of_patient_ids_aligned,
   directory_for_raw_llm_outputs,
   directory_for_predicted_jsons,
   ollama_model_name: str = "llama3.2:latest",
   sleep_seconds_between_cases: float = 0.0,
   write_raw_model_text: bool = True,
   write_predicted_json: bool = True,
   debug_logging: bool = False,
   timeout_s: int = 60,
   chunk_max_chars: int = 3000,
   chunk_overlap_chars: int = 300,
):
   """
   Batch inference over aligned cases.

   Uses cached `.txt` files from experimental-data/text_cache/debug_dumps/
   if available, otherwise falls back to PDF parsing.

   Args:
       list_of_pmids_aligned: List of PMIDs (aligned to ground-truth).
       list_of_input_paths_aligned: Corresponding list of input file paths (PDFs).
       list_of_patient_ids_aligned: Corresponding list of patient IDs from truth.
       directory_for_raw_llm_outputs: Folder for saving raw LLM outputs.
       directory_for_predicted_jsons: Folder for saving predicted phenopacket JSONs.
       ollama_model_name: Model identifier (default: llama3.2:latest).
       sleep_seconds_between_cases: Optional sleep between cases.
       write_raw_model_text: If True, dump raw LLM text to disk.
       write_predicted_json: If True, dump validated JSON to disk.
       debug_logging: Enable verbose logs per case/chunk.
       timeout_s: Max seconds per chunk before timeout.
       chunk_max_chars: Maximum characters per chunk for model input.
       chunk_overlap_chars: Overlap between chunks for context continuity.

   Returns:
       BatchResult: dynamic object with attributes:
         - successful_outcomes: list of successful Outcome objects
         - failed_outcomes: list of failed Outcome objects
         - total_successes(): count of successes
         - total_failures(): count of failures
   """
   pdf_text_cache = PdfTextCache(
       experimental_data_root=str(Path(directory_for_raw_llm_outputs).parents[1])
   )

   total_cases = len(list_of_pmids_aligned)
   successful_outcomes = []
   failed_outcomes = []

   with tqdm(total=total_cases, desc="Batch HPO Extraction", unit="case") as pbar:
       for pmid, input_path, patient_id in zip(
           list_of_pmids_aligned, list_of_input_paths_aligned, list_of_patient_ids_aligned
       ):
           try:
               # Prefer cached .txt dump if available
               cached_txt_path = (
                   Path(directory_for_raw_llm_outputs).parents[0]
                   / "text_cache"
                   / "debug_dumps"
                   / f"{Path(input_path).stem}.txt"
               )
               if cached_txt_path.is_file():
                   clinical_text = cached_txt_path.read_text(encoding="utf-8")
               else:
                   clinical_text = pdf_text_cache.get_text(str(input_path))

               items, raw_model_text = extract_hpo_terms(
                   clinical_text=clinical_text,
                   model=ollama_model_name,
                   return_raw_model_text=True,
                   debug_logging=debug_logging,
                   timeout_s=timeout_s,
                   chunk_max_chars=chunk_max_chars,
                   chunk_overlap_chars=chunk_overlap_chars,
               )

               predicted_packet_json = build_minimal_phenopacket_from_hpo_list(
                   patient_id=patient_id,
                   hpo_list=items,
               )
               predicted_packet_util = UtilPhenopacket(predicted_packet_json)

               if write_raw_model_text:
                   raw_path = Path(directory_for_raw_llm_outputs) / f"{pmid}__raw.txt"
                   raw_path.write_text(raw_model_text or "", encoding="utf-8")
               else:
                   raw_path = None

               if write_predicted_json:
                   json_path = Path(directory_for_predicted_jsons) / f"{pmid}__{patient_id}.json"
                   json_path.write_text(predicted_packet_util.to_json(indent=2), encoding="utf-8")
               else:
                   json_path = None

               successful_outcomes.append(
                   type("Outcome", (), {
                       "pmid": pmid,
                       "raw_output_path": str(raw_path) if raw_path else None,
                       "predicted_json_path": str(json_path) if json_path else None,
                       "predicted_packet_util": predicted_packet_util,
                   })
               )

           except Exception as error:
               failed_outcomes.append(
                   type("Outcome", (), {
                       "pmid": pmid,
                       "error_message": str(error),
                       "predicted_packet_util": None,
                   })
               )
           finally:
               pbar.update(1)

   return type("BatchResult", (), {
       "successful_outcomes": successful_outcomes,
       "failed_outcomes": failed_outcomes,
       "total_successes": lambda self: len(successful_outcomes),
       "total_failures": lambda self: len(failed_outcomes),
   })()