import glob
import numpy as np
import os
import pandas as pd
import tifffile
from tqdm import tqdm

import imaging_db.images.file_splitter as file_splitter
import imaging_db.metadata.json_validator as json_validator
import imaging_db.utils.meta_utils as meta_utils


class OmeTiffSplitter(file_splitter.FileSplitter):
    """
    Subclass for reading and splitting ome tiff files
    """

    def set_frame_info(self, page):
        """
        Sets frame shape, im_colors and bit_depth for the class
        Must be called once before setting global metadata

        :param page page: Page read from tifffile
        """
        self.frame_shape = [page.tags["ImageLength"].value,
                       page.tags["ImageWidth"].value]
        # Encode color channel information
        self.im_colors = 1
        if len(self.frame_shape) == 3:
            self.im_colors = self.frame_shape[2]
        bits_val = page.tags["BitsPerSample"].value
        if bits_val == 16:
            self.bit_depth = "uint16"
        elif bits_val == 8:
            self.bit_depth = "uint8"
        else:
            print("Bit depth must be 16 or 8, not {}".format(bits_val))
            raise ValueError

    def split_file(self, file_path, schema_filename):
        """
        Splits file into frames and gets metadata for each frame.
        set_frame_info must be called prior to this function call.

        :param str file_path: Full path to file
        :param str schema_filename: Full path to schema file name
        :return dataframe frames_meta: Metadata for all frames
        :return np.array im_stack: Image stack extracted from file
        """
        frames = tifffile.TiffFile(file_path)
        # Get global metadata
        page = frames.pages[0]
        nbr_frames = len(frames.pages)
        # Create image stack with image bit depth 16 or 8
        im_stack = np.empty((self.frame_shape[0],
                             self.frame_shape[1],
                             self.im_colors,
                             nbr_frames),
                            dtype=self.bit_depth)

        # Get metadata schema
        meta_schema = json_validator.read_json_file(schema_filename)
        # Convert frames to numpy stack and collect metadata
        # Separate structured metadata (with known fields)
        # from unstructured, the latter goes into frames_json
        frames_meta = meta_utils.make_dataframe(nbr_frames=nbr_frames)
        # Pandas doesn't really support inserting dicts into dataframes,
        # so micromanager metadata goes into a separate list
        for i in range(nbr_frames):
            page = frames.pages[i]
            im_stack[..., i] = np.atleast_3d(page.asarray())
            # Get dict with metadata from json schema
            json_i, meta_i = json_validator.get_metadata_from_tags(
                page=page,
                meta_schema=meta_schema,
                validate=True,
            )
            self.frames_json.append(json_i)
            # Add required metadata fields to data frame
            meta_names = meta_utils.META_NAMES
            df_names = meta_utils.DF_NAMES
            for meta_name, df_name in zip(meta_names, df_names):
                if meta_name in meta_i.keys():
                    frames_meta.loc[i, df_name] = meta_i[meta_name]

            # Create a file name and add it
            im_name = self._get_imname(frames_meta.loc[i])
            frames_meta.loc[i, "file_name"] = im_name
        return frames_meta, im_stack

    def _validate_file_paths(self, positions, glob_paths):
        """
        Get only the file paths found by glob that correspond to the input
        parameter positions.

        :param list of ints positions: Positions to be uploaded
        :param list of strs glob_paths: Paths to files found in directory
        :return list of strs file_paths: Paths that exist in directory and
            in positions
        """
        position_list = self.global_json["IJMetadata"]["InitialPositionList"]
        file_paths = []
        for p in range(len(position_list)):
            label = position_list[p]["Label"]
            # Check if the value is in positions
            if int(label[3:]) in positions:
                file_path = next((s for s in glob_paths if label in s), None)
                if file_path is not None:
                    file_paths.append(file_path)
        assert len(file_paths) > 0, \
            "No positions correspond with IJMetadata PositionList"
        return file_paths

    def get_frames_and_metadata(self, schema_filename, positions=None):
        """
        Reads ome.tiff file into memory and separates image frames and metadata.
        Workaround in case I need to read ome-xml:
        https://github.com/soft-matter/pims/issues/125
        It is assumed that all metadata lives as dicts inside tiff frame tags.
        NOTE: It seems like the IJMetadata Info field is a dict converted into
        string, and it's only present in the first frame.

        :param str schema_filename: Full path to metadata json schema file
        :param [None, list of ints] positions: Position files to upload.
            If None,
        """
        if isinstance(positions, type(None)):
            positions = []
        if os.path.isfile(self.data_path):
            # Run through processing only once
            file_paths = [self.data_path]
        else:
            # Get position files in the folder
            file_paths = glob.glob(os.path.join(self.data_path, "*.ome.tif"))
            assert len(file_paths) > 0,\
                "Can't find ome.tifs in {}".format(self.data_path)
            # Parse positions
            if isinstance(positions, str):
                positions = json_validator.str2json(positions)

        # Read first file to find available positions
        frames = tifffile.TiffFile(file_paths[0])
        # Get global metadata
        page = frames.pages[0]
        # Set frame info. This should not vary between positions
        self.set_frame_info(page)
        # IJMetadata only exists in first frame, so that goes into global json
        self.global_json = json_validator.get_global_json(
            page=page,
            file_name=self.data_path,
        )
        # Validate given positions
        if len(positions) > 0:
            file_paths = self._validate_file_paths(
                positions=positions,
                glob_paths=file_paths,
            )
        self.frames_meta = meta_utils.make_dataframe(nbr_frames=None)
        self.frames_json = []

        pos_prog_bar = tqdm(file_paths, desc='Position')

        for file_path in pos_prog_bar:
            file_meta, self.im_stack = self.split_file(
                file_path,
                schema_filename,
            )
            self.frames_meta = self.frames_meta.append(
                file_meta,
                ignore_index=True,
            )
            # Upload frames in file to S3
            self.upload_stack(
                file_names=list(file_meta["file_name"]),
                im_stack=self.im_stack,
            )
        # Finally, set global metadata from frames_meta
        self.set_global_meta(nbr_frames=self.frames_meta.shape[0])
