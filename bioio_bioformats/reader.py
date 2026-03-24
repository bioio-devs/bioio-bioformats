#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from contextlib import AbstractContextManager
from functools import cached_property
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

import xarray as xr
from bffile import BioFile
from bioio_base import constants, dimensions, exceptions, io, reader, types
from fsspec.implementations.local import LocalFileSystem
from resource_backed_dask_array import ResourceBackedDaskArray

from . import utils

if TYPE_CHECKING:
    from fsspec.spec import AbstractFileSystem
    from ome_types import OME

###############################################################################


class Reader(reader.Reader):
    """Read files using bioformats.

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
    _current_resolution_level: int = 0
    # Do not provide default value because
    # they may not need to be used by your reader (i.e. input param is an array)
    _fs: "AbstractFileSystem"
    _path: str

    @staticmethod
    def _is_supported_image(fs: AbstractFileSystem, path: str, **kwargs: Any) -> bool:
        """
        Returns
        -------
        is_supported: bool
            True if the file is supported by bioformats, exception with error otherwise
        """
        try:
            if isinstance(fs, LocalFileSystem):
                with BioFile(path, meta=False):
                    pass
                return True
            raise exceptions.UnsupportedFileFormatError(
                reader_name="bioformats ",
                path=path,
                msg_extra="must be local file system",
            )
        except Exception as e:
            raise exceptions.UnsupportedFileFormatError(
                reader_name="bioformats ", path=path, msg_extra=str(e)
            )

    def __init__(
        self,
        image: types.PathLike,
        *,
        original_meta: bool = False,
        memoize: Union[int, bool] = 0,
        options: Optional[Dict[str, bool]] = None,
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

        self._bf_kwargs: dict[str, Any] = {
            "original_meta": original_meta,
            "memoize": memoize,
        }
        if options:
            self._bf_kwargs["options"] = options

        self._dask_tiles = dask_tiles
        self._tile_size = tile_size

        try:
            self._bf = BioFile(self._path, **self._bf_kwargs)
            with self._bf.ensure_open():
                self._scenes = tuple(series.name for series in self._bf)
        except RuntimeError:
            raise
        except Exception as e:
            raise exceptions.UnsupportedFileFormatError(
                self.__class__.__name__, self._path
            ) from e

    @property
    def scenes(self) -> Optional[Tuple[str, ...]]:
        return self._scenes

    @property
    def resolution_levels(self) -> Tuple[int, ...]:
        """Return available resolution levels for the current scene."""
        with self._bf.ensure_open():
            meta = self._bf.core_metadata(series=self.current_scene_index)
        return tuple(range(meta.resolution_count))

    def _read_delayed(self) -> xr.DataArray:
        return self._to_xarray(delayed=True)

    def _read_immediate(self) -> xr.DataArray:
        return self._to_xarray(delayed=False)

    # note: bffile also caches this... so this is not strictly necessary
    @cached_property
    def ome_metadata(self) -> OME:
        """Return OME object parsed by ome_types."""
        with self._bf.ensure_open():
            return self._bf.ome_metadata

    @cached_property
    def ome_xml(self) -> str:
        """Return OME-XML string from bioformats reader."""
        with self._bf.ensure_open():
            return self._bf.ome_xml

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
        with self._bf.ensure_open():
            lazy_arr = data = self._bf.as_array(
                series=self.current_scene_index,
                resolution=self._current_resolution_level,
            )
            dims = lazy_arr.dims
            coords = lazy_arr.coords

            if delayed:
                if self._dask_tiles:
                    ts = self._tile_size or "auto"
                    dask_arr = lazy_arr.to_dask(tile_size=ts)
                else:
                    chunks: tuple[int, ...] = (1, 1, 1, -1, -1)
                    if lazy_arr.is_rgb:
                        chunks = chunks + (-1,)
                    dask_arr = lazy_arr.to_dask(chunks=chunks)
                data = ResourceBackedDaskArray.from_array(
                    dask_arr, _BioFileContext(self._bf)
                )

        return xr.DataArray(
            data,
            dims=dims,
            coords=coords,
            attrs={
                constants.METADATA_UNPROCESSED: self.ome_xml,
                constants.METADATA_PROCESSED: self.ome_metadata,
            },
        )

    @staticmethod
    def bioformats_version() -> str:
        """The version of the bioformats_package.jar being used."""
        return BioFile.bioformats_version()


class _BioFileContext(AbstractContextManager):
    """Adapter giving ResourceBackedDaskArray open/close/closed semantics."""

    def __init__(self, bf: BioFile) -> None:
        self._bf = bf

    @property
    def closed(self) -> bool:
        return self._bf.closed

    def __enter__(self) -> BioFile:
        self._bf.open()
        return self._bf

    def __exit__(self, *exc: object) -> None:
        self._bf.close()
