#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="P5",
    version="0.1.0",
    description="Prompt-driven Parsing of Prenatal PDFs to Phenopackets",
    author="Varenya Jain",
    author_email="varenyajj@gmail.com",
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.13",
    entry_points={
        "console_scripts": [
            "p5 = P5.scripts.__main__:cli",
            "pull-git-files = P5.scripts.pull_git_files:pull_git_files",
            "create-pmid-pkl = P5.scripts.create_pmid_pkl:create_pmid_pkl",
            "pmid-downloader = P5.scripts.pmid_downloader:pmid_downloader",
            "create-phenopacket-dataset = "
                "P5.scripts.create_phenopacket_dataset:create_phenopacket_dataset",
            "file-to-phenopacket = P5.scripts.file_to_phenopacket:file_to_phenopacket",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
)