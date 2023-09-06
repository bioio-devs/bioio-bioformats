# bioio-bioformats

[![Build Status](https://github.com/bioio-devs/bioio-bioformats/workflows/CI/badge.svg)](https://github.com/bioio-devs/bioio-bioformats/actions)
[![Documentation](https://github.com/bioio-devs/bioio-bioformats/workflows/Documentation/badge.svg)](https://bioio-devs.github.io/bioio-bioformats)

A BioIO reader for reading bioformats formatted images.

This plugin is intended to be used in conjunction with [bioio](https://github.com/bioio-devs/bioio)
---

## Installation

**Stable Release:** `pip install bioio-bioformats`<br>
**Development Head:** `pip install git+https://github.com/bioio-devs/bioio-bioformats.git`

## Quickstart

```python
from bioio_bioformats import Reader 

r = Reader("my-image.ext")
r.dims
```

## Documentation

For full package documentation please visit [bioio-devs.github.io/bioio-bioformats](https://bioio-devs.github.io/bioio-bioformats).

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for information related to developing the code.

**MIT License**
