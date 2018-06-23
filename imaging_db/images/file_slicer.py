import cv2
import numpy as np
import pims
import re


def get_image_description(image_str):
    """
    It seems the only way to get key image organization parameters is in a
    weird ImageJ ImageDescription1 tag which is a string...
    Is this really how image descriptors are stored in all ome-tif files?

    :param str image_str: string containing key image data
    :return int nbr_channels: number of channels
    :return int nbr_slices: number of slices
    :return str slice_order: string describing how slices are ordered,
        e.g. 'zct'
    Note: there is no parameter describing time here, does it show up for time series?
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


def read_ome_tiff(file_name):
    """
    reads ome.tiff file into memory and separates image files and metadata.

    :param str file_name: full path to file
    :return:
    """
    frames = pims.TiffStack(file_name)
    # Get the first frame, slice information should be contained there
    frame0 = frames._tiff[0]
    # Get image order from weird string
    nbr_channels, nbr_slices, slice_order = get_image_description(
        frame0.tags['ImageDescription1'].value)
    global_metadata = {
        "nbr_frames": len(frames)
        "im_width": frame0.tags['ImageWidth'].value,
        "im_height": frame0.tags['ImageLength'].value,
        "bit_depth": frame0.tags['BitsPerSample'].value,
        "nbr_channels": nbr_channels,
        "nbr_slices": nbr_slices,
        "slice_order": slice_order,
    }
    # Create image stack with image bit depth 16 or 8
    imtype = np.uint16
    if global_metadata["bit_depth"] == 8:
        imtype = np.uint8
    im_stack = np.empty((global_metadata["im_width"],
                         global_metadata["im_height"],
                         global_metadata["nbr_frames"]),
                        dtype=imtype)
    # Convert frames to numpy stack
    for im_nbr in range(global_metadata["nbr_frames"]):
        im_stack[:,:, im_nbr] = frames._tiff[im_nbr]
