from abc import ABCMeta, abstractmethod
import glob
import numpy as np
import os
import pandas as pd
import pims
import tifffile

import imaging_db.metadata.json_validator as json_validator


# TODO: Create a metaname translator
# For all possible versions of a required variable, translate them
# into the standardized DF names
# e.g. name in {"Channel", "ChannelIndex", "ChannelIdx"} -> "channel_idx"

# Required metadata fields - everything else goes into a json
META_NAMES = ["ChannelIndex",
              "Slice",
              "FrameIndex",
              "ChannelName",
              "FileName",
              "PositionIndex"]

DF_NAMES = ["channel_idx",
            "slice_idx",
            "time_idx",
            "channel_name",
            "file_name",
            "pos_idx"]


def make_dataframe(nbr_frames, col_names=DF_NAMES):
    """
    Create empty pandas dataframe given indices and column names

    :param int nbr_frames: The number of rows in the dataframe
    :param list of strs col_names: The dataframe column names
    :return dataframe frames_meta: Empty dataframe with given
        indices and column names
    """
    # Get metadata and path for each frame
    frames_meta = pd.DataFrame(
        index=range(nbr_frames),
        columns=col_names,
    )
    return frames_meta


def validate_global_meta(global_meta):
    """
    Validate that global frames meta dictionary contain all required values.

    :param dict global_meta: Global frames metadata
    :raise AssertionError: if not all keys are present
    """
    keys = ["folder_name",
            "nbr_frames",
            "im_width",
            "im_height",
            "nbr_slices",
            "nbr_channels",
            "im_colors",
            "nbr_timepoints",
            "nbr_positions",
            "bit_depth"]

    keys_valid = np.zeros(len(keys), dtype='bool')
    for idx, key in enumerate(keys):
        key_valid = (key in global_meta) and \
                        (global_meta[key] is not None)
        keys_valid[idx] = key_valid
    assert np.all(keys_valid),\
        "Not all required metadata keys are present"


class FileSplitter(metaclass=ABCMeta):
    """Read different types of files and separate frame information"""

    def __init__(self,
                 data_path,
                 folder_name,
                 file_format=".png",
                 int2str_len=3):
        """
        :param str data_path: Full path to file (ome.tiff) or directory name
            (tif dir)
        :param str folder_name: Folder name on S3 where data will be stored
        :param str file_format: Image file format (preferred is png)
        :param int int2str_len: How many integers will be added to each index
        """
        self.data_path = data_path
        self.folder_name = folder_name
        self.file_format = file_format
        self.int2str_len = int2str_len
        self.im_stack = None
        self.frames_meta = None
        self.frames_json = None
        self.global_meta = None
        self.global_json = None

    def get_imstack(self):
        """
        Checks that image stack has been assigned and if so returns it
        :return np.array im_stack: Image stack
        """
        assert self.im_stack is not None,\
            "Image stack has not been assigned yet"
        return self.im_stack

    def get_global_meta(self):
        """
        Checks if metadata is assigned and if so returns it
        :return dict global_meta: Global metadata for file
        """
        assert self.global_meta is not None, \
            "global_meta has no values yet"
        return self.global_meta

    def get_global_json(self):
        """
        Checks if metadata is assigned and if so returns it
        :return dict global_json: Non-required (variable) global metadata
        """
        assert self.global_json is not None, \
            "global_json has no values yet"
        return self.global_json

    def get_frames_meta(self):
        """
        Checks if metadata is assigned and if so returns it
        :return pd.DataFrame frames_meta: Associated metadata for each frame
        """
        assert self.frames_meta is not None, \
            "frames_meta has no values yet"
        return self.frames_meta

    def get_frames_json(self):
        """
        Checks if metadata is assigned and if so returns it
        :return dict frames_json: Non-required (variable) metadata for
            each frame
        """
        assert self.frames_json is not None, \
            "frames_json has no values yet"
        return self.frames_json

    def _get_imname(self, meta_row):
        """
        Generate image (frame) name given frame metadata and file format.

        :param dict meta_row: Metadata for frame, must contain frame indices
        :return str imname: Image file name
        """
        return "im_c" + str(meta_row["channel_idx"]).zfill(self.int2str_len) + \
            "_z" + str(meta_row["slice_idx"]).zfill(self.int2str_len) + \
            "_t" + str(meta_row["time_idx"]).zfill(self.int2str_len) + \
            "_p" + str(meta_row["pos_idx"]).zfill(self.int2str_len) + \
            self.file_format

    def set_global_meta(self,
                        nbr_frames,
                        frame_shape,
                        im_colors,
                        pixel_type=np.uint16):
        """
        Lastly, add values to global_meta now that we have them all
        """
        self.global_meta = {
            "folder_name": self.folder_name,
            "nbr_frames": nbr_frames,
            "im_width": frame_shape[0],
            "im_height": frame_shape[1],
            "im_colors": im_colors,
            "bit_depth": str(pixel_type),
            "nbr_slices": len(np.unique(self.frames_meta["slice_idx"])),
            "nbr_channels": len(np.unique(self.frames_meta["channel_idx"])),
            "nbr_timepoints": len(np.unique(self.frames_meta["time_idx"])),
            "nbr_positions": len(np.unique(self.frames_meta["pos_idx"])),
        }
        validate_global_meta(self.global_meta)

    @abstractmethod
    def get_frames_and_metadata(self):
        """
        Function that will extract all necessary image and meta- data
        for uploading a dataset as Frames.
        """
        raise NotImplementedError


class OmeTiffSplitter(FileSplitter):
    """
    Subclass for reading and splitting ome tiff files
    """

    def get_frames_and_metadata(self, schema_filename):
        """
        reads ome.tiff file into memory and separates image frames and metadata.
        Workaround in case I need to read ome-xml:
        https://github.com/soft-matter/pims/issues/125
        It is assumed that all metadata lives as dicts inside tiff frame tags.
        NOTE: It seems like the IJMetadata Info field is a dict converted into
        string, and it's only present in the first frame.

        :param str schema_filename: Gull path to metadata json schema file
        """
        assert os.path.isfile(self.data_path), \
            "File doesn't exist: {}".format(self.data_path)
        assert self.data_path[-8:] == ".ome.tif", \
            "File extension must be .ome.tif, not {}".format(
                self.data_path[-8:],
            )

        frames = pims.TiffStack(self.data_path)
        # Get global metadata
        frame_shape = frames.frame_shape
        nbr_frames = len(frames)
        # Encode color channel information
        im_colors = 1
        if len(frame_shape) == 3:
            im_colors = frame_shape[2]

        # Create image stack with image bit depth 16 or 8
        self.im_stack = np.empty((frame_shape[0],
                                  frame_shape[1],
                                  im_colors,
                                  nbr_frames),
                                 dtype=frames.pixel_type)

        # Get metadata schema
        meta_schema = json_validator.read_json_file(schema_filename)
        # IJMetadata only exists in first frame, so that goes into global json
        self.global_json, channel_names = json_validator.get_global_meta(
            frame=frames._tiff[0],
            file_name=self.data_path,
        )

        # Convert frames to numpy stack and collect metadata
        # Separate structured metadata (with known fields)
        # from unstructured, the latter goes into frames_json
        self.frames_meta = make_dataframe(nbr_frames=nbr_frames)
        # Pandas doesn't really support inserting dicts into dataframes,
        # so micromanager metadata goes into a separate list
        self.frames_json = []
        for i in range(nbr_frames):
            frame = frames._tiff[i]
            self.im_stack[..., i] = np.atleast_3d(frame.asarray())
            # Get dict with metadata from json schema
            json_i, meta_i = json_validator.get_metadata_from_tags(
                frame=frame,
                meta_schema=meta_schema,
                validate=True,
            )
            self.frames_json.append(json_i)
            # Add required metadata fields to data frame
            for meta_name, df_name in zip(META_NAMES, DF_NAMES):
                if meta_name in meta_i.keys():
                    self.frames_meta.loc[i, df_name] = meta_i[meta_name]
                else:
                    # Add special cases here
                    # ChNames is a list that should be translated to channel name
                    if meta_name == "ChannelName" and len(channel_names) > 0:
                        # Check if ChNames (list of names) is present
                        self.frames_meta.loc[i, "channel_name"] = \
                            channel_names[meta_i["ChannelIndex"]]

            # Create a file name and add it
            im_name = self._get_imname(self.frames_meta.loc[i])
            self.frames_meta.loc[i, "file_name"] = im_name
            self.set_global_meta(
                nbr_frames=nbr_frames,
                frame_shape=frame_shape,
                im_colors=im_colors,
                pixel_type=frames.pixel_type
            )


class TifFolderSplitter(FileSplitter):
    """
    Subclass for reading all tiff files in a folder
    """

    def _set_frame_meta_from_name(self, im_path, channel_names):
        """
        Assume file follows naming convention
        img_channelname_t***_p***_z***.tif

        Populates the frames_meta dict keys:
        "channel_idx", "slice_idx", "time_idx", "channel_name",
        "file_name", "pos_idx"
        :param im_path: Path to frame
        :return dict meta_row: Metadata for frame (one row in dataframe)
        """
        im_name = os.path.basename(im_path)[:-4]
        str_split = im_name.split("_")[1:]
        meta_row = dict.fromkeys(DF_NAMES)
        for s in str_split:
            # This is assuming no channel is named e.g. txxx
            if s in channel_names:
                meta_row["channel_name"] = s
                # Index channels by names
                meta_row["channel_idx"] = channel_names.index(s)
            elif s.find("t") == 0 and len(s) == 4:
                meta_row["time_idx"] = int(s[1:])
            elif s.find("p") == 0 and len(s) == 4:
                meta_row["pos_idx"] = int(s[1:])
            elif s.find("z") == 0 and len(s) == 4:
                meta_row["slice_idx"] = int(s[1:])
        meta_row["file_name"] = self._get_imname(meta_row)
        # Make sure meta row is properly filled
        assert None not in meta_row.values(),\
            "meta row has not been populated correctly"
        return meta_row

    def get_frames_and_metadata(self):
        """
        Global metadata dict is assumed to be in the same folder in a file
        named metadata.txt
        Frame metadata is extracted from each frame
        File naming convention is assumed to be:
        img_channelname_t***_p***_z***.tif
        """
        assert os.path.isdir(self.data_path), \
            "Directory doesn't exist: {}".format(self.data_path)

        frame_paths = glob.glob(os.path.join(self.data_path, "*.tif"))
        nbr_frames = len(frame_paths)

        self.global_json = json_validator.read_json_file(
            os.path.join(self.data_path, "metadata.txt"),
        )
        meta_summary = self.global_json["Summary"]
        channel_names = meta_summary["ChNames"]
        pixel_type = meta_summary["PixelType"]
        im_colors = 3
        if pixel_type.find("GRAY") >= 0:
            im_colors = 1
        if meta_summary["BitDepth"] == 16:
            bit_depth = np.uint16
        elif meta_summary["BitDepth"] == 8:
            bit_depth = np.uint8
        else:
            print("Bit depth must be 16 or 8, not {}".format(
                meta_summary["BitDepth"]))
            raise ValueError
        # Create empty image stack and metadata dataframe and list
        self.im_stack = np.empty((meta_summary["Width"],
                                  meta_summary["Height"],
                                  im_colors,
                                  nbr_frames),
                                 dtype=bit_depth)
        self.frames_meta = make_dataframe(nbr_frames=nbr_frames)
        self.frames_json = []
        # Loop over all the frames to get data and metadata
        for i, frame_path in enumerate(frame_paths):
            imtif = tifffile.TiffFile(frame_path)
            self.im_stack[..., i] = np.atleast_3d(imtif.asarray())
            tiftags = imtif.pages[0].tags
            # Get all frame specific metadata
            dict_i = {}
            for t in tiftags.keys():
                dict_i[t] = tiftags[t].value
            self.frames_json.append(dict_i)
            self.frames_meta.loc[i] = self._set_frame_meta_from_name(
                im_path=frame_path,
                channel_names=channel_names,
            )
        # Set global metadata
        self.set_global_meta(
            nbr_frames=nbr_frames,
            frame_shape=[meta_summary["Width"], meta_summary["Height"]],
            im_colors=im_colors,
            pixel_type=bit_depth,
        )
