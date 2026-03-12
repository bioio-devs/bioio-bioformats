# bioio-bioformats

[![Build Status](https://github.com/bioio-devs/bioio-bioformats/actions/workflows/ci.yml/badge.svg)](https://github.com/bioio-devs/bioio-bioformats/actions)
[![PyPI version](https://badge.fury.io/py/bioio-bioformats.svg)](https://badge.fury.io/py/bioio-bioformats)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10--3.13-blue.svg)](https://www.python.org/downloads/)

A BioIO reader plugin for reading [many file formats like as seen here](https://docs.openmicroscopy.org/bio-formats/5.8.2/supported-formats.html) using `bioformats`

---


## Documentation

[See the full documentation on our GitHub pages site](https://bioio-devs.github.io/bioio/OVERVIEW.html) - the generic use and installation instructions there will work for this package.

Information about the base reader this package relies on can be found in the `bioio-base` repository [here](https://github.com/bioio-devs/bioio-base)

## Installation

**Stable Release:** `pip install bioio-bioformats`<br>
**Development Head:** `pip install git+https://github.com/bioio-devs/bioio-bioformats.git`

## Special Installation Note

This package relies on [bffile](https://github.com/imaging-formats/bffile),
which uses [scyjava](https://github.com/scijava/scyjava) to fetch the
Bio-Formats maven artifacts, and [cjdk](https://github.com/cachedjdk/cjdk) to
fetch a Java runtime.  You do NOT need to install or setup java separately.

Read details in the [bffile
README](https://github.com/imaging-formats/bffile?tab=readme-ov-file#selecting-bio-formats-version)
on how to select the Bio-Formats version or Java runtime version if you need to.

## Example Usage (see full documentation for more examples)

Install bioio-bioformats alongside bioio:

`pip install bioio bioio-bioformats`


This example shows a simple use case for just accessing the pixel data of the image
by explicitly passing this `Reader` into the `BioImage`. Passing the `Reader` into
the `BioImage` instance is optional as `bioio` will automatically detect installed
plug-ins and auto-select the most recently installed plug-in that supports the file
passed in.
```python
from bioio import BioImage
import bioio_bioformats

img = BioImage("my_file.tiff", reader=bioio_bioformats.Reader)
img.data
```

## Issues
[_Click here to view all open issues in bioio-devs organization at once_](https://github.com/search?q=user%3Abioio-devs+is%3Aissue+is%3Aopen&type=issues&ref=advsearch) or check this repository's issue tab.


## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for information related to developing the code.
