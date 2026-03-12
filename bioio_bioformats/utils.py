from __future__ import annotations

from typing import TYPE_CHECKING

from bioio_base import types

if TYPE_CHECKING:
    from ome_types import OME


def physical_pixel_sizes(ome: OME, scene: int = 0) -> types.PhysicalPixelSizes:
    """
    Returns
    -------
    sizes: PhysicalPixelSizes
        Using available metadata, the floats representing physical pixel sizes for
        dimensions Z, Y, and X.

    Notes
    -----
    We currently do not handle unit attachment to these values. Please see the file
    metadata for unit information.
    """
    p = ome.images[scene].pixels
    return types.PhysicalPixelSizes(
        p.physical_size_z, p.physical_size_y, p.physical_size_x
    )
