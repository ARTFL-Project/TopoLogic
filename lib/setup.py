#!/usr/bin/env python3
"""Python package install script"""

import os
from sys import platform

from setuptools import setup

from topologic import __version__

setup(
    name="topologic",
    version=__version__,
    author="The ARTFL Project",
    author_email="clovisgladstone@gmail.com",
    packages=["topologic"],
    scripts=["scripts/topologic"],
    install_requires=[
        "scikit-learn",
        "networkx",
        "pandas",
        "scipy",
        "numpy==1.15.4",  ## pinned until https://github.com/numpy/numpy/issues/14012 is fixed
        "nltk",
        "flask",
        "flask_cors",
        "tqdm",
        "joblib",
        "matplotlib",
        "text_preprocessing @ git+https://github.com/ARTFL-Project/text-preprocessing@v0.8#egg=text_preprocessing",
    ],
)
