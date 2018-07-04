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
              "Exposure-ms",
              "FileName"]

DF_NAMES = ["channel_idx",
            "slice_idx",
            "frame_idx",
            "channel_name",
            "exposure_ms",
            "file_name"]

def get_imname(meta_i, file_format, int2str_len):
    return "im_c" + \
            str(meta_i["channel_idx"]).zfill(int2str_len) + \
            "_z" + str(meta_i["slice_idx"]).zfill(int2str_len) + \
            "_t" + str(meta_i["frame_idx"]).zfill(int2str_len) + \
            file_format


def read_ome_tiff(file_name,
                  schema_filename,
                  file_format=".png",
                  int2str_len=3):
    """
    TODO: Convert this into classes once we have more file types
    reads ome.tiff file into memory and separates image files and metadata.
    Workaround in case I need to read ome-xml:
    https://github.com/soft-matter/pims/issues/125
    It is assumed that all metadata lives as dicts inside tiff frame tags.
    NOTE: It seems like the IJMetadata Info field is a dict converted into
    string, and it's only present in the first frame...

    :param str file_name: full path to file
    :param str schema_filename: full path to metadata json schema file
    :param str file_format: file format for image slice name
    :param int int2str_len: format file name using ints converted to specific
        string length
    :return np.array im_stack: image stack
    :return pd.DataFrame slice_meta: associated metadata for each slice
    :return dict slice_json: wildcard metadata for each slice
    :return dict global_meta: global metadata for file
    """
    frames = pims.TiffStack(file_name)
    # Get global metadata
    frame_shape = frames.frame_shape
    # Encode color channel information
    im_colors = 1
    if len(frame_shape) == 3:
        im_colors = frame_shape[2]
    global_meta = {
        "nbr_frames": len(frames),
        "im_width": frame_shape[0],
        "im_height": frame_shape[1],
        "im_colors": im_colors,
        "bit_depth": str(frames.pixel_type),
    }
    # Create image stack with image bit depth 16 or 8
    im_stack = np.empty((frame_shape[0],
                         frame_shape[1],
                         im_colors,
                         global_meta["nbr_frames"]),
                        dtype=frames.pixel_type)

    # Get metadata schema
    meta_schema = json_validator.read_json_file(schema_filename)
    # IJMetadata only exists in first frame, so that goes into global json
    global_json, channel_names = json_validator.get_global_meta(
        frame=frames._tiff[0],
        file_name=file_name,
    )

    # Convert frames to numpy stack and collect metadata
    # Separate structure metadata (with known fields)
    # from unstructured, which goes slice_json
    slice_meta = pd.DataFrame(
        index=range(global_meta["nbr_frames"]),
        columns=DF_NAMES)
    # Pandas doesn't really support inserting dicts into dataframes,
    # so micromanager metadata goes into a separate list
    slice_json = []
    for i in range(global_meta["nbr_frames"]):
        frame = frames._tiff[i]
        im_stack[..., i] = np.atleast_3d(frame.asarray())
        # Get dict with metadata from json schema
        json_i, meta_i = json_validator.get_metadata_from_tags(
            frame=frame,
            meta_schema=meta_schema,
            validate=True,
        )
        slice_json.append(json_i)
        # Add required metadata fields to data frame
        for meta_name, df_name in zip(META_NAMES, DF_NAMES):
            if meta_name in meta_i.keys():
                slice_meta.loc[i, df_name] = meta_i[meta_name]
            else:
                # Add special cases here
                # ChNames is a list that should be translated to ChannelName
                if meta_name == "ChannelName":
                    # Check if ChNames (list of names) is present
                    slice_meta.loc[i, "channel_name"] = \
                        channel_names[meta_i["ChannelIndex"]]

        # Create a file name and add it
        im_name = get_imname(slice_meta.loc[i], file_format, int2str_len)
        slice_meta.loc[i, "file_name"] = im_name

    return im_stack, slice_meta, slice_json, global_meta, global_json









