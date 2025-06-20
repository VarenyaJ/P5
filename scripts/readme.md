#### Pull Test data
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

#### PDF to Phenopacket Script
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