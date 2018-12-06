import numpy as np
import pandas as pd


# Required metadata fields - everything else goes into a json
META_NAMES = ["ChannelIndex",
              "Slice",
              "FrameIndex",
              "Channel",
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

    :param [None, int] nbr_frames: The number of rows in the dataframe
    :param list of strs col_names: The dataframe column names
    :return dataframe frames_meta: Empty dataframe with given
        indices and column names
    """
    if nbr_frames is not None:
        # Get metadata and path for each frame
        frames_meta = pd.DataFrame(
            index=range(nbr_frames),
            columns=col_names,
        )
    else:
        frames_meta = pd.DataFrame(columns=col_names)
    return frames_meta


def validate_global_meta(global_meta):
    """
    Validate that global frames meta dictionary contain all required values.

    :param dict global_meta: Global frames metadata
    :raise AssertionError: if not all keys are present
    """
    keys = ["s3_dir",
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
