#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import cached_property
from typing import Any, Dict, Optional, Tuple, Union

import xarray as xr
from bioio_base import constants, dimensions, exceptions, io, reader, types
from fsspec.implementations.local import LocalFileSystem
from fsspec.spec import AbstractFileSystem
from ome_types import OME

from . import utils
from .biofile import BioFile

###############################################################################


class Reader(reader.Reader):
    """Read files using bioformats.

    This reader requires `bioformats_jar` to be installed in the environment, and
    requires the java executable to be available on the path (or via the JAVA_HOME
    environment variable), along with the `mvn` executable.

    To install java and maven with conda, run `conda install -c conda-forge scyjava`.
    You may need to deactivate/reactivate your environment after installing.  If you
    are *still* getting a `JVMNotFoundException`, try setting JAVA_HOME as follows:

        # mac and linux:
        export JAVA_HOME=$CONDA_PREFIX

        # windows:
        set JAVA_HOME=%CONDA_PREFIX%\\Library

    Parameters
    ----------
    image : Path or str
        path to file
    original_meta : bool, optional
        whether to also retrieve the proprietary metadata as structured annotations in
        the OME output, by default False
    memoize : bool or int, optional
        threshold (in milliseconds) for memoizing the reader. If the the time
        required to call `reader.setId()` is larger than this number, the initialized
        reader (including all reader wrappers) will be cached in a memo file, reducing
        time to load the file on future reads.  By default, this results in a hidden
        `.bfmemo` file in the same directory as the file. The `BIOFORMATS_MEMO_DIR`
        environment can be used to change the memo file directory.
        Set `memoize` to greater than 0 to turn on memoization. by default it's off.
        https://downloads.openmicroscopy.org/bio-formats/latest/api/loci/formats/Memoizer.html
    options : Dict[str, bool], optional
        A mapping of option-name -> bool specifying additional reader-specific options.
        see: https://docs.openmicroscopy.org/bio-formats/latest/formats/options.html
        For example: to turn off chunkmap table reading for ND2 files, use
        `options={"nativend2.chunkmap": False}`
    dask_tiles: bool, optional
        Whether to chunk the bioformats dask array by tiles to easily read sub-regions
        with numpy-like array indexing
        Defaults to false and iamges are read by entire planes
    tile_size: Optional[Tuple[int, int]]
        Tuple that sets the tile size of y and x axis, respectively
        By default, it will use optimal values computed by bioformats itself
    fs_kwargs: Dict[str, Any]
        Any specific keyword arguments to pass down to the fsspec created filesystem.
        Default: {}

    Raises
    ------
    exceptions.UnsupportedFileFormatError
        If the file is not supported by bioformats.
    """

    _xarray_dask_data: Optional["xr.DataArray"] = None
    _xarray_data: Optional["xr.DataArray"] = None
    _mosaic_xarray_dask_data: Optional["xr.DataArray"] = None
    _mosaic_xarray_data: Optional["xr.DataArray"] = None
    _dims: Optional[dimensions.Dimensions] = None
    _metadata: Optional[Any] = None
    _scenes: Optional[Tuple[str, ...]] = None
    _current_scene_index: int = 0
    # Do not provide default value because
    # they may not need to be used by your reader (i.e. input param is an array)
    _fs: "AbstractFileSystem"
    _path: str

    @staticmethod
    def _is_supported_image(fs: AbstractFileSystem, path: str, **kwargs: Any) -> bool:
        try:
            if not isinstance(fs, LocalFileSystem):
                return False
            f = BioFile(path, meta=False, memoize=False)
            f.close()
            return True

        except Exception:
            return False

    def __init__(
        self,
        image: types.PathLike,
        *,
        original_meta: bool = False,
        memoize: Union[int, bool] = 0,
        options: Dict[str, bool] = {},
        dask_tiles: bool = False,
        tile_size: Optional[Tuple[int, int]] = None,
        fs_kwargs: Dict[str, Any] = {},
    ):
        self._fs, self._path = io.pathlike_to_fs(
            image,
            enforce_exists=True,
            fs_kwargs=fs_kwargs,
        )
        # Catch non-local file system
        if not isinstance(self._fs, LocalFileSystem):
            raise ValueError(
                f"Cannot read Bioformats from non-local file system. "
                f"Received URI: {self._path}, which points to {type(self._fs)}."
            )

        self._bf_kwargs = {
            "options": options,
            "original_meta": original_meta,
            "memoize": memoize,
            "dask_tiles": dask_tiles,
            "tile_size": tile_size,
        }
        try:
            with BioFile(self._path, **self._bf_kwargs) as rdr:  # type: ignore
                md = rdr._r.getMetadataStore()
                self._scenes: Tuple[str, ...] = tuple(
                    str(md.getImageName(i)) for i in range(md.getImageCount())
                )
        except RuntimeError:
            raise
        except Exception as e:
            raise exceptions.UnsupportedFileFormatError(
                self.__class__.__name__, self._path
            ) from e

    @property
    def scenes(self) -> Optional[Tuple[str, ...]]:
        return self._scenes

    def _read_delayed(self) -> xr.DataArray:
        return self._to_xarray(delayed=True)

    def _read_immediate(self) -> xr.DataArray:
        return self._to_xarray(delayed=False)

    @cached_property
    def ome_metadata(self) -> OME:
        """Return OME object parsed by ome_types."""
        with BioFile(self._path, **self._bf_kwargs) as rdr:  # type: ignore
            meta = rdr.ome_metadata
        return meta

    @property
    def physical_pixel_sizes(self) -> types.PhysicalPixelSizes:
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
        return utils.physical_pixel_sizes(self.metadata, self.current_scene_index)

    def _to_xarray(self, delayed: bool = True) -> xr.DataArray:
        with BioFile(
            self._path,
            series=self.current_scene_index,
            **self._bf_kwargs,  # type: ignore
        ) as rdr:
            image_data = rdr.to_dask() if delayed else rdr.to_numpy()
            coords = utils.get_coords_from_ome(
                ome=rdr.ome_metadata,
                scene_index=self.current_scene_index,
            )

        return xr.DataArray(
            image_data,
            dims=dimensions.DEFAULT_DIMENSION_ORDER_LIST_WITH_SAMPLES
            if rdr.core_meta.is_rgb
            else dimensions.DEFAULT_DIMENSION_ORDER_LIST,
            coords=coords,
            attrs={
                constants.METADATA_UNPROCESSED: rdr.ome_xml,
                constants.METADATA_PROCESSED: rdr.ome_metadata,
            },
        )

    @staticmethod
    def bioformats_version() -> str:
        """The version of the bioformats_package.jar being used."""
        return utils._try_get_loci().__version__
