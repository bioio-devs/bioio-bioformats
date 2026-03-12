from __future__ import annotations

from typing import Any, Dict, List, Union

import numpy as np
from bioio_base import dimensions, types
from ome_types import OME

###############################################################################


def get_coords_from_ome(
    ome: OME,
    scene_index: int,
    image_shape: tuple[int, ...] | None = None,
) -> Dict[str, Union[List[Any], Union[types.ArrayLike, Any]]]:
    """
    Process the OME metadata to retrieve the coordinate planes.

    Parameters
    ----------
    ome: OME
        A constructed OME object to retrieve data from.
    scene_index: int
        The current operating scene index to pull metadata from.
    image_shape : tuple, optional
        Actual image shape as (T, C, Z, Y, X) or (T, C, Z, Y, X, S).
        When provided (e.g. for sub-resolution reads), spatial coordinate
        arrays are built from these sizes instead of the OME pixel counts,
        and pixel sizes are scaled accordingly.

    Returns
    -------
    coords: Dict[str, Union[List[Any], Union[types.ArrayLike, Any]]]
        The coordinate planes / data for each dimension.
    """

    # Select scene
    scene_meta = ome.images[scene_index]
    pixels = scene_meta.pixels

    # Actual spatial sizes (from image_shape if given, else OME metadata)
    if image_shape is not None:
        size_z = image_shape[2]
        size_y = image_shape[3]
        size_x = image_shape[4]
    else:
        size_z = pixels.size_z
        size_y = pixels.size_y
        size_x = pixels.size_x

    # Get coordinate planes
    coords: Dict[str, Union[List[str], np.ndarray]] = {}

    # Channels
    coords[dimensions.DimensionNames.Channel] = [
        channel.name if channel.name is not None else channel.id
        for channel in pixels.channels
    ]

    # Time
    if pixels.time_increment is not None:
        coords[dimensions.DimensionNames.Time] = generate_coord_array(
            0, pixels.size_t, pixels.time_increment
        )
    elif pixels.size_t > 1:
        if len(pixels.planes) > 0:
            t_index_to_delta_map = {
                p.the_t: p.delta_t for p in pixels.planes
            }
            coords[dimensions.DimensionNames.Time] = list(
                t_index_to_delta_map.values()
            )
        else:
            coords[dimensions.DimensionNames.Time] = np.linspace(
                0, pixels.size_t - 1, pixels.size_t
            )

    # Spatial dimensions — scale pixel size when reading sub-resolutions
    if pixels.physical_size_z is not None:
        step_z = pixels.physical_size_z * (pixels.size_z / size_z)
        coords[dimensions.DimensionNames.SpatialZ] = generate_coord_array(
            0, size_z, step_z
        )
    if pixels.physical_size_y is not None:
        step_y = pixels.physical_size_y * (pixels.size_y / size_y)
        coords[dimensions.DimensionNames.SpatialY] = generate_coord_array(
            0, size_y, step_y
        )
    if pixels.physical_size_x is not None:
        step_x = pixels.physical_size_x * (pixels.size_x / size_x)
        coords[dimensions.DimensionNames.SpatialX] = generate_coord_array(
            0, size_x, step_x
        )

    return coords


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


def generate_coord_array(
    start: Union[int, float], stop: Union[int, float], step_size: Union[int, float]
) -> np.ndarray:
    """
    Generate an np.ndarray for coordinate values.

    Parameters
    ----------
    start: Union[int, float]
        The start value.
    stop: Union[int, float]
        The stop value.
    step_size: Union[int, float]
        How large each step should be.

    Returns
    -------
    coords: np.ndarray
        The coordinate array.

    Notes
    -----
    In general, we have learned that floating point math is hard....
    This block of code used to use `np.arange` with floats as parameters and
    it was causing errors. To solve, we generate the range with ints and then
    multiply by a float across the entire range to get the proper coords.
    See: https://github.com/AllenCellModeling/aicsimageio/issues/249
    """
    return np.arange(start, stop) * step_size
