#!/usr/bin/env python3
"""Python package install script"""

import os
from sys import platform

from setuptools import setup

from topic_modeling_browser import __version__

setup(
    name="topic-modeling-browser",
    version=__version__,
    author="The ARTFL Project",
    author_email="clovisgladstone@gmail.com",
    packages=["topic_modeling_browser"],
    scripts=["scripts/topic_modeling_browser"],
    install_requires=[
        "scikit-learn",
        "networkx",
        "pandas",
        "scipy",
        "numpy",
        "nltk",
        "flask",
        "flask_cors",
        "tqdm",
        "joblib",
        "matplotlib",
        "text_preprocessing @ git+https://github.com/ARTFL-Project/text-preprocessing@v0.8#egg=text_preprocessing",
    ],
)
