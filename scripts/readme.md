### Pull Test data
To get the test data run the following scripts in order:

To pull the summaries of PubMed cases run:
```shell
python pull_git_files.py "data/tmp" "https://github.com/P2GX/phenopacket2prompt" "docs/cases/"
```

To pull the test phenopackets run:
```shell
python pull_git_files.py "data/tmp" "https://github.com/monarch-initiative/phenopacket-store" "notebooks"
```

To filter the phenopackets by the cases use:
```shell
python create_phenopacket_dataset.py "./data/tmp/cases" "./data/tmp/notebooks" "./data/tmp/phenopacket_dataset.csv" --recursive_ground_truth_dir True
```

### create_pmid_pkl script
Run: 
```shell
python scripts/create_pmid_pkl.py "data/tmp/cases" "data/tmp/pmids.pkl --recursive_dir_search"
```
This will look at every filename in the directory *data/tmp/cases*, and whenever a filename contains a string of the form
"PMID_{1-8 digits}", that PMID will be added to the .pkl file *pmids.pkl*. 

### PMID downloader script
Run: 
```shell
python scripts/PMID_downloader.py "tmp/pmids.pkl" "data/tmp/pmid_pdfs"
```
For every PMID in the .pkl file, a PDF will be downloaded to the directory data/tmp/pmid_pdfs whenever this is possible (i.e. whenever there is a valid PMCID).

### PDF to Phenopacket Script
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
python pdf_converter.py <input_dir> <output_dir> "<prompt>" "<model>" --file-type .pdf
```