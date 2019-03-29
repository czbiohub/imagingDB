import importlib
import inspect
import os
import re


def import_class(module_name, cls_name):
    """
    Imports a class dynamically

    :param str module_name: Module, e.g. 'images', 'metadata'
    :param str cls_name: Class name
    :return loaded class cls
    :raises ImportError: If class can't be loaded
    """

    full_module_name = ".".join(('imaging_db', module_name))
    try:
        module = importlib.import_module(full_module_name)
        cls = getattr(module, cls_name)

        if inspect.isclass(cls):
            return cls
    except ImportError as e:
        raise ImportError(e)


def get_splitter_class(frames_format):
    """
    Given frames_format (ome_tiff, tif_folder or tif_id), import the
    appropriate file splitter class.

    :param str frames_format: What format your files are stored in
    :return class splitter_class: File splitter class
    """
    assert frames_format in {'ome_tiff',
                             'ome_tif',
                             'tiff',
                             'tif_folder',
                             'tiff_folder',
                             'tif_id',
                             'tiff_id'}, \
        ("frames_format should be 'ome_tiff', 'tif_folder' or 'tif_id'",
         "not {}".format(frames_format))

    class_dict = {'ome_tiff': 'OmeTiffSplitter',
                  'ome_tif': 'OmeTiffSplitter',
                  'tif_folder': 'TifFolderSplitter',
                  'tiff_folder': 'TifFolderSplitter',
                  'tif_id': 'TifIDSplitter',
                  'tiff_id': 'TifIDSplitter',
                  'tiff': 'OmeTiffSplitter',
                  }
    module_dict = {'ome_tiff': 'images.ometif_splitter',
                   'ome_tif': 'images.ometif_splitter',
                   'tif_folder': 'images.tiffolder_splitter',
                   'tiff_folder': 'images.tiffolder_splitter',
                   'tif_id': 'images.tif_id_splitter',
                   'tiff_id': 'images.tif_id_splitter',
                   'tiff': 'images.ometif_splitter',
                   }
    # Dynamically import class
    splitter_class = import_class(
        module_dict[frames_format],
        class_dict[frames_format],
    )
    return splitter_class


def parse_ml_name(file_name):
    """
    Parse metadata from file name or file path.
    This function is custom for the ML group, who has the following file
    naming convention:
    "[plate ID]_[stack_nbr]_[protein name]_PyProcessed.tif”
    And they would like to include plate ID, stack number, and protein name in their
    global metadata. Use the first three parts of file name.

    :param str file_name: File name or path
    :return dict meta_json: Global metadata
    :raises AssertionError: If the file name contains less than 3 '_'
    :raises ValueError: If stack number is not an int
    """
    # Get rid of path if present
    file_str = os.path.basename(file_name)
    str_list = file_str.split('_')
    assert len(str_list) >= 4, "File name is supposed to contain at least 3 '_'"
    try:
        stack_nbr = int(str_list[1])
    except ValueError as e:
        print('Stack number {} should be an int'.format(str_list[1]))
        raise e
    meta_json = {"plate_id": str_list[0],
                 "stack_nbr": stack_nbr,
                 "protein_name": str_list[2]}

    return meta_json


def parse_sms_name(file_name, meta_row, channel_names):
    """
    Parse metadata from file name or file path.
    This function is custom for the computational microscopy (SMS)
    group, who has the following file naming convention:
    File naming convention is assumed to be:
        img_channelname_t***_p***_z***.tif
    This function will alter list and dict in place.

    :param str file_name: File name or path
    :param dict meta_row: Metadata for frame (one row in dataframe)
    :param list[str] channel_names: Expanding list of channel names
    """
    # Get rid of path if present
    file_str = os.path.basename(file_name)[:-4]
    str_split = file_str.split("_")[1:]

    if len(str_split) > 4:
        # this means they have introduced additional _ in the file name
        channel_name = '_'.join(str_split[:-3])
    else:
        channel_name = str_split[0]
    # Add channel name and index
    meta_row["channel_name"] = channel_name
    if channel_name not in channel_names:
        channel_names.append(channel_name)
    # Index channels by names
    meta_row["channel_idx"] = channel_names.index(channel_name)
    # Loop through the rest of the indices which should be in name
    str_split = str_split[-3:]
    for s in str_split:
        if s.find("t") == 0 and len(s) == 4:
            meta_row["time_idx"] = int(s[1:])
        elif s.find("p") == 0 and len(s) == 4:
            meta_row["pos_idx"] = int(s[1:])
        elif s.find("z") == 0 and len(s) == 4:
            meta_row["slice_idx"] = int(s[1:])


def parse_idx_from_name(file_name, meta_row, channel_names, order="cztp"):
    """
    Assumes file name contains all 4 indices necessary for imagingDB:
     channel_idx (c), slice_idx (z), time_idx (t) and pos_idx (p)
    E.g. im_c***_z***_p***_t***.png
    It doesn't care about the extension or the number of digits each index is
    represented by, it extracts all integers from the image file name and assigns
    them by order. By default it assumes that the order is c, z, t, p.

    :param str file_name: Image name without path
    :param dict meta_row: One row of metadata given image file name
    :param list[str] channel_names: Expanding list of channel names
    :param str order: Order in which c, z, t, p are given in the image (4 chars)
    """
    # Get rid of path if present
    file_str = os.path.basename(file_name)[:-4]
    order_list = list(order)
    assert len(set(order_list)) == 4,\
        "Order needs 4 unique values, not {}".format(order)

    # Find all integers in name string
    ints = re.findall(r'\d+', file_str)
    assert len(ints) == 4, "Expected 4 integers, found {}".format(len(ints))
    # Assign indices based on ints and order
    idx_dict = {"c": "channel_idx",
                "z": "slice_idx",
                "t": "time_idx",
                "p": "pos_idx"}
    for i in idx_dict.keys():
        assert i in order_list, "{} not in order".format(i)
    for i, order_char in enumerate(order_list):
        idx_name = idx_dict[order_char]
        meta_row[idx_name] = int(ints[i])
    # Channel name can't be retrieved from image name
    channel_name = str(meta_row['channel_idx'])
    if channel_name not in channel_names:
        channel_names.append(channel_name)
    meta_row["channel_name"] = channel_name
