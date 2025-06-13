#### Pull Test data
To get the test data run the following scripts in order:

To pull the test phenopackets run:
```shell
python scripts/pull_git_files.py "data/tmp" "https://github.com/P2GX/phenopacket2prompt" "docs/cases/"
```

To pull the test phenopackets run:
```shell
python scripts/pull_git_files.py "data/tmp" "https://github.com/monarch-initiative/phenopacket-store" "notebooks"
```
#### PDF to Phenopacket Script
Make sure ollama is installed on your machine and your env. Start the server.
Then download the model of your choice via:
```shell
conda activate p5
python
>>> ollama.pull('<model_name>')
>>> exit()
```

If you successfully installed the model switch into the scripts directory and:
```shell 
python pdf_converter.py <input_dir> <output_dir> "<prompt>" "<model>" --file-type .pdf
```