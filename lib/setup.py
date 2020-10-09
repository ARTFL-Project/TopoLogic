#!/usr/bin/env python3
"""Python package install script"""

import os
from sys import platform

from setuptools import setup


setup(
    name="topologic",
    version="0.3",
    author="The ARTFL Project",
    author_email="clovisgladstone@gmail.com",
    packages=["topologic"],
    scripts=["scripts/topologic"],
    install_requires=[
        "scikit-learn",
        "pandas",
        "scipy",
        "numpy",
        "nltk",
        "tqdm",
        "joblib",
        "matplotlib",
        "fastapi",
        "gunicorn",
        "uvicorn",
        "annoy",
        "text_preprocessing @ git+https://github.com/ARTFL-Project/text-preprocessing@v0.8.2#egg=text_preprocessing",
    ],
)
