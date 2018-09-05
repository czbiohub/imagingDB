import numpy as np
import pandas as pd
import pims

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
    # Get metadata and oath for each frame
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
            "stack_depth",
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
    if np.all(keys_valid) is False:
        raise AssertionError("Not all required metadata keys are present")


def _get_imname(meta_i, file_format, int2str_len):
    """
    Generate image (frame) name given frame metadata and file format.

    :param dict meta_i: Metadata for frame, must contain frame indices
    :param str file_format: Image file format (preferred is png)
    :param int int2str_len: How many integers will be added to each index
    :return str imname: Image file name
    """
    return "im_c" + str(meta_i["channel_idx"]).zfill(int2str_len) + \
        "_z" + str(meta_i["slice_idx"]).zfill(int2str_len) + \
        "_t" + str(meta_i["time_idx"]).zfill(int2str_len) + \
        "_p" + str(meta_i["pos_idx"]).zfill(int2str_len) + \
        file_format


def read_ome_tiff(file_name,
                  schema_filename,
                  folder_name,
                  file_format=".png",
                  int2str_len=3):
    """
    TODO: Convert this into classes once we have more file types
    reads ome.tiff file into memory and separates image frames and metadata.
    Workaround in case I need to read ome-xml:
    https://github.com/soft-matter/pims/issues/125
    It is assumed that all metadata lives as dicts inside tiff frame tags.
    NOTE: It seems like the IJMetadata Info field is a dict converted into
    string, and it's only present in the first frame...

    :param str file_name: Full path to file
    :param str schema_filename: Gull path to metadata json schema file
    :param str folder_name: Folder name on S3 where data will be stored
    :param str file_format: File format for image slice name
    :param int int2str_len: Format file name using ints converted to specific
        string length
    :return np.array im_stack: Image stack
    :return pd.DataFrame frames_meta: Associated metadata for each frame
    :return dict frames_json: Wildcard metadata for each frame
    :return dict global_meta: Global metadata for file
    """
    frames = pims.TiffStack(file_name)
    # Get global metadata
    frame_shape = frames.frame_shape
    nbr_frames = len(frames)
    # Encode color channel information
    im_colors = 1
    if len(frame_shape) == 3:
        im_colors = frame_shape[2]

    # Create image stack with image bit depth 16 or 8
    im_stack = np.empty((frame_shape[0],
                         frame_shape[1],
                         im_colors,
                         nbr_frames),
                        dtype=frames.pixel_type)

    # Get metadata schema
    meta_schema = json_validator.read_json_file(schema_filename)
    # IJMetadata only exists in first frame, so that goes into global json
    global_json, channel_names = json_validator.get_global_meta(
        frame=frames._tiff[0],
        file_name=file_name,
    )

    # Convert frames to numpy stack and collect metadata
    # Separate structured metadata (with known fields)
    # from unstructured, the latter goes into frames_json
    frames_meta = make_dataframe(nbr_frames=nbr_frames)
    # Pandas doesn't really support inserting dicts into dataframes,
    # so micromanager metadata goes into a separate list
    frames_json = []
    for i in range(nbr_frames):
        frame = frames._tiff[i]
        im_stack[..., i] = np.atleast_3d(frame.asarray())
        # Get dict with metadata from json schema
        json_i, meta_i = json_validator.get_metadata_from_tags(
            frame=frame,
            meta_schema=meta_schema,
            validate=True,
        )
        frames_json.append(json_i)
        # Add required metadata fields to data frame
        for meta_name, df_name in zip(META_NAMES, DF_NAMES):
            if meta_name in meta_i.keys():
                frames_meta.loc[i, df_name] = meta_i[meta_name]
            else:
                # Add special cases here
                # ChNames is a list that should be translated to channel name
                if meta_name == "ChannelName" and len(channel_names) > 0:
                    # Check if ChNames (list of names) is present
                    frames_meta.loc[i, "channel_name"] = \
                        channel_names[meta_i["ChannelIndex"]]

        # Create a file name and add it
        im_name = _get_imname(frames_meta.loc[i], file_format, int2str_len)
        frames_meta.loc[i, "file_name"] = im_name

    # Lastly, add values to global_meta now that we have them all
    global_meta = {
        "folder_name": folder_name,
        "nbr_frames": nbr_frames,
        "im_width": frame_shape[0],
        "im_height": frame_shape[1],
        "im_colors": im_colors,
        "bit_depth": str(frames.pixel_type),
        "stack_depth": len(np.unique(frames_meta["slice_idx"])),
        "nbr_channels": len(np.unique(frames_meta["channel_idx"])),
        "nbr_timepoints": len(np.unique(frames_meta["time_idx"])),
        "nbr_positions": len(np.unique(frames_meta["pos_idx"])),
    }
    validate_global_meta(global_meta)

    return im_stack, frames_meta, frames_json, global_meta, global_json









