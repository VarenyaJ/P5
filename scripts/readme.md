### Pull Test data
To get the test data run the following scripts in order:

To pull the summaries of PubMed cases run:
```shell
python -m scripts.pull_git_files "data/tmp/phenopacket_store" "https://github.com/P2GX/phenopacket2prompt" "docs/cases/"
```

To pull the test phenopackets run:
```shell
python -m scripts.pull_git_files "data/tmp/phenopacket_store" "https://github.com/monarch-initiative/phenopacket-store" "notebooks"
```

To filter the phenopackets by the cases use:
```shell
python -m scripts.create_phenopacket_dataset "./data/tmp/phenopacket_store/cases" "./data/tmp/phenopacket_store/notebooks" "./data/tmp/phenopacket_store/phenopacket_dataset.csv" --recursive_ground_truth_dir True
```

### create_pmid_pkl script
Run: 
```shell
python -m scripts.create_pmid_pkl "data/tmp/phenopacket_store/notebooks" "data/tmp/phenopacket_store/pmids.pkl" "--recursive_dir_search"
```
This will look at every filename in the directory *data/tmp/phenopacket_store/notebooks*, and whenever a filename contains a string of the form
"PMID_{1-8 digits}", that PMID will be added to the .pkl file *data/tmp/phenopacket_store/pmids.pkl*. 

### PMID downloader script
Run: 
```shell
python -m scripts.PMID_downloader "data/tmp/phenopacket_store/pmids.pkl" "data/tmp/phenopacket_store/pmid_pdfs" "20"
```
For every PMID in the .pkl file, a PDF will be downloaded to the directory *data/tmp/phenopacket_store/pmid_pdfs* whenever this is possible (i.e. whenever there is a valid PMCID). 

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