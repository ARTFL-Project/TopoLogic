#!/usr/bin/env python3
"""Python package install script"""

from setuptools import setup

setup(
    name="topologic",
    version="0.3",
    author="The ARTFL Project",
    author_email="clovisgladstone@gmail.com",
    packages=["topologic"],
    install_requires=[
        "scikit-learn",
        "pandas",
        "scipy",
        "numpy",
        "tqdm",
        "joblib",
        "matplotlib",
        "fastapi==0.110.3",
        "gunicorn",
        "uvicorn",
        "uvloop",
        "httptools",
        "annoy",
        "psycopg2",
        "multiprocess",
        "text_preprocessing @ git+https://github.com/ARTFL-Project/text-preprocessing@v1.0.5.5#egg=text_preprocessing",
        "philologic>=4.7.4.4",
    ],
)
