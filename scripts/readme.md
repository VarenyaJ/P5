#### To run these commands, please go to P5/scripts. The generated folders will be within the 'P5/scripts/data/' subdirectory, not 'P5/data/'

### Pull phenopackets
To pull all the phenopackets from Phenopacket store run:
```shell
python -m pull_git_files "data/tmp/phenopacket_store" "https://github.com/monarch-initiative/phenopacket-store" "notebooks"
```

### create_pmid_pkl script
Run: 
```shell
python -m create_pmid_pkl "data/tmp/phenopacket_store/notebooks" "data/tmp/phenopacket_store/pmids.pkl" "--recursive_dir_search"
```
This will look at every filename in the directory *data/tmp/phenopacket_store/notebooks*, and whenever a filename contains a string of the form
"PMID_{1-8 digits}", that PMID will be added to the .pkl file *data/tmp/phenopacket_store/pmids.pkl*. 

### PMID downloader script
Run: 
```shell
python -m PMID_downloader "data/tmp/phenopacket_store/pmids.pkl" "data/tmp/phenopacket_store/pmid_pdfs" "0"
```
For every PMID in the .pkl file, a PDF will be downloaded to the directory *data/tmp/phenopacket_store/pmid_pdfs* whenever this is possible (i.e. whenever there is a valid PMCID). 

### Create LLM output files <span style="color:orange">(DOES NOT EXIST YET... OUTPUT FILES = E.G. HPO TERMS OR PHENOPACKETS)</span>

Run: 
```shell
python -m scripts.llm_output "data/tmp/phenopacket_store/pmid_pdfs" "data/tmp/phenopacket_store/llm_output_dir"
```

Uses the script file_to_phenopacket to take every PDF in the folder and pmid_pdfs and outputs some sort of LLM generated response to files named PMID_1234567.something

### Create "Real Phenopacket VS LLM Output" comparison table

Create a CSV file with columns *PMID, PMID PDF file path, and phenopacket file path*.
```shell
python -m scripts.create_phenopacket_dataset "scripts/data/tmp/phenopacket_store/pmid_pdfs" "scripts/data/tmp/phenopacket_store/notebooks" "scripts/data/tmp/PMID_PDF_Phenopacket_list_in_phenopacket_store.csv" --recursive_ground_truth_dir True
```

# <span style="color:orange">BELOW NOT CURRENTLY PART OF THE PIPELINE</span>

### File to Phenopacket Script
Make sure ollama is installed on your machine and your env. Start the server.
Then download the model of your choice via:
```shell
conda activate p5
python
>>> import ollama
>>> ollama.pull('<model_name>')
>>> exit()
```

If you successfully installed the model switch into the scripts directory and:
```shell 
python -m scripts.file_to_phenopacket "data/tmp/phenopacket_store/pmid_pdfs" "data/tmp/phenopacket_store/llm_jsons" "<prompt>" "<model_name>" --file-type .pdf
```

For example, you could run:
```shell 
python -m scripts.file_to_phenopacket "data/tmp/phenopacket_store/pmid_pdfs" "data/tmp/phenopacket_store/llm_jsons" "Please take this PubMed article, and for JUST ONE of the patients described in it, can you create me a valid Phenopacket in JSON format. Please make sure it is a valid JSON." "llama3.2:latest" --file-type .pdf
```
