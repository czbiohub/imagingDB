import numpy as np
import pandas as pd
import hashlib

CHUNK_SIZE = 4096


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
            "pos_idx",
            "sha256"]


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

def gen_sha256(image):
    """
    Generate the sha-256 hash of an image. If the user
    passes in a numpy ndarray (usually a frame), hash the
    whole numpy. If the user passes in a file path, the 
    function will hash the file in 4kB chucks


    :param ndarray/String image: ndarray containing the image to hash
                                or string containing path to file
                                to hash 
    :return String sha256: sha-256 hash of the input image
    """

    sha = hashlib.sha256()

    # If a frame is passed in, hash the numpy array
    if isinstance(image, np.ndarray):
        sha.update(image.tobytes())
    
    # If a file path is passed in, hash the file in 4kB chunks
    elif isinstance(image, str):
        with open(image,"rb") as im:
            for byte_block in iter(lambda: im.read(CHUNK_SIZE),b""):
                sha.update(byte_block)

    else:
        raise TypeError('image must be a numpy ndarray (frame)',
                        'or str (file path)')

    return sha.hexdigest()
