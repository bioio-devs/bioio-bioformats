#!/usr/bin/env python
# -*- coding: utf-8 -*-
from typing import NamedTuple, Tuple

import numpy as np


class CoreMeta(NamedTuple):
    """NamedTuple with core bioformats metadata. (not OME meta)"""

    shape: Tuple[int, int, int, int, int, int]
    dtype: np.dtype
    series_count: int
    is_rgb: bool
    is_interleaved: bool
    dimension_order: str
    resolution_count: int
