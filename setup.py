import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "multimethods",
    version = "1.0.0",
    author = "Robert Kende",
    author_email = "robert.kende@gmail.com",
    description = ("A simple python multidispatch."),
    license = "MIT",
    keywords = "multimethods, multidispatch, dispatch, decorator",
    url = "http://packages.python.org/multimethods",
    packages=['multimethods', 'tests'],
    long_description=read('README'),
    test_suite='tests',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python",
        "Intended Audience :: Developers",
        "Topic :: Software Development",
        "License :: OSI Approved :: MIT License",
    ],
)
