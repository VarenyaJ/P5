"""
notebooks/utils/hpo_batch.py

Batch LLM HPO extraction:
- iterates aligned (pmid, input_path, patient_id) triples
- calls the single-case extractor
- saves raw model output and a minimal predicted Phenopacket JSON
- returns wrapped Phenopacket utils for downstream evaluation

Dependencies:
  - notebooks.utils.hpo_extraction
  - the `phenopacket.Phenopacket` utility
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
   ollama_model_name="llama3.2:latest",
   sleep_seconds_between_cases: float = 0.0,
   write_raw_model_text: bool = True,
   write_predicted_json: bool = True,
   debug_logging: bool = False,
):
   """
   Batch inference over aligned cases. Prefers cached `.txt` files in
   experimental-data/text_cache/debug_dumps/ before falling back to PDF parsing.
   """

   pdf_text_cache = PdfTextCache(experimental_data_root=str(Path(directory_for_raw_llm_outputs).parents[1]))

   total_cases = len(list_of_pmids_aligned)
   successful_outcomes = []
   failed_outcomes = []

   with tqdm(total=total_cases, desc="Batch HPO Extraction", unit="case") as pbar:
       for case_index, (pmid, input_path, patient_id) in enumerate(
           zip(list_of_pmids_aligned, list_of_input_paths_aligned, list_of_patient_ids_aligned),
           start=1,
       ):
           try:
               # Prefer cached .txt dump if available
               cached_txt_path = Path(directory_for_raw_llm_outputs).parents[0] / "text_cache" / "debug_dumps" / f"{Path(input_path).stem}.txt"
               if cached_txt_path.is_file():
                   clinical_text = cached_txt_path.read_text(encoding="utf-8")
               else:
                   clinical_text = pdf_text_cache.get_text(str(input_path))

               items, raw_model_text = extract_hpo_terms(
                   clinical_text=clinical_text,
                   model=ollama_model_name,
                   return_raw_model_text=True,
                   debug_logging=debug_logging,
               )

               predicted_packet_json = build_minimal_phenopacket_from_hpo_list(
                   patient_id=patient_id,
                   hpo_list=items,
               )
               predicted_packet_util = UtilPhenopacket(predicted_packet_json)

               if write_raw_model_text:
                   raw_path = Path(directory_for_raw_llm_outputs) / f"{pmid}__raw.txt"
                   raw_path.write_text(raw_model_text or "", encoding="utf-8")

               if write_predicted_json:
                   json_path = Path(directory_for_predicted_jsons) / f"{pmid}__{patient_id}.json"
                   json_path.write_text(predicted_packet_util.to_json(indent=2), encoding="utf-8")

               successful_outcomes.append(
                   type("Outcome", (), {
                       "pmid": pmid,
                       "raw_output_path": str(raw_path) if write_raw_model_text else None,
                       "predicted_json_path": str(json_path) if write_predicted_json else None,
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