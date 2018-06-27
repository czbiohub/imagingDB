import numpy as np
import pandas as pd
import pims
import re

import imaging_db.metadata.json_validator as json_validator

MICROMETA_NAMES = ["ChannelIndex",
                   "Slice",
                   "FrameIndex",
                   "Exposure-ms",
                   "XResolution",
                   "YResolution",
                   "ResolutionUnit",
                   "FileName",
                   "MicroManagerMetadata"]


def get_image_description(image_str):
    """
    Update: make this obsolete and rely on MicroManagerMetadata instead

    It seems the only way to get key image organization parameters is in a
    weird ImageJ ImageDescription1 tag which is a string...
    Is this really how image descriptors are stored in all ome-tif files?

    :param str image_str: string containing key image data
    :return int nbr_channels: number of channels
    :return int nbr_slices: number of slices
    :return str slice_order: string describing how slices are ordered,
        e.g. 'zct'
    Note: What permutations of order are possible?
    """
    str_list = image_str.split()
    # Find channels
    temp_str = [s for s in str_list if "channel" in s]
    assert len(temp_str) == 1, "Cant find channels in {}".format(image_str)
    nbr_channels = re.findall("\d+", temp_str[0])
    # Find number of slices
    temp_str = [s for s in str_list if "slice" in s]
    assert len(temp_str) == 1, "Cant find slices in {}".format(image_str)
    nbr_slices = re.findall("\d+", temp_str[0])
    temp_str = [s for s in str_list if "order" in s]
    assert len(temp_str) == 1, "Cant find order in {}".format(image_str)
    temp_str = temp_str[0]
    slice_order = temp_str[temp_str.find("=") + 1:]
    return nbr_channels, nbr_slices, slice_order


def read_ome_tiff(file_name, file_format=".png", int2str_len=3):
    """
    reads ome.tiff file into memory and separates image files and metadata.

    :param str file_name: full path to file
    :param str file_format: file format for image name
    :param int int2str_len: format file name using ints converted to specific
        string length
    :return np.array im_stack: image stack
    :return pd.DataFrame metadata: associated metadata for each slice
    """
    frames = pims.TiffStack(file_name)
    # Get global metadata
    frame_shape = frames.frame_shape
    global_metadata = {
        "nbr_frames": len(frames),
        "im_width": frame_shape[0],
        "im_height": frame_shape[1],
        "bit_depth": str(frames.pixel_type),
    }
    # Create image stack with image bit depth 16 or 8
    im_stack = np.empty((frame_shape[0],
                         frame_shape[0],
                         global_metadata["nbr_frames"]),
                        dtype=frames.pixel_type)

    # Convert frames to numpy stack and collect metadata
    # Separate structure metadata (with known fields)
    # from unstructured, which goes in last column
    metadata = pd.DataFrame(
        index=range(global_metadata["nbr_frames"]),
        columns=MICROMETA_NAMES)
    for i, im_nbr in enumerate(range(global_metadata["nbr_frames"])):
        frame = frames._tiff[im_nbr]
        im_stack[:, :, im_nbr] = frame.asarray()
        # Starting with just MicroManager meta for now
        # it seems to contain the juciest data
        micromanager_meta = frame.tags["MicroManagerMetadata"].value
        # Validate metadata
        json_validator.validate_schema(micromanager_meta, "MICROMETA_SCHEMA")
        # Add structured metadata and Micromanager metadata to dataframe
        row = []
        # First four names come from micrometa
        for meta_name in MICROMETA_NAMES[:4]:
            row.append(micromanager_meta[meta_name])
        # Last three are from other tags
        # XResolution, YResolution, ResolutionUnit
        row.append(frame.tags[MICROMETA_NAMES[4]].value[0])
        row.append(frame.tags[MICROMETA_NAMES[5]].value[0])
        row.append(str(frame.tags[MICROMETA_NAMES[6]].value))
        # Create a file name and add it
        im_name = "im_channel" + str(row[0]).zfill(int2str_len) + \
            "_slice" + str(row[1]).zfill(int2str_len) + \
            "_frame" + str(row[2]).zfill(int2str_len) + file_format
        row.append(im_name)
        row.append(micromanager_meta)
        # Insert row in dataframe
        metadata.loc[i] = row
    return im_stack, metadata









