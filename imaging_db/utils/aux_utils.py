import importlib
import inspect
import os

import imaging_db.utils.meta_utils as meta_utils


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
        raise e


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


def parse_sms_name(file_name, channel_names, meta_row):
    """
    Parse metadata from file name or file path.
    This function is custom for the computational microscopy (SMS)
    group, who has the following file naming convention:
    File naming convention is assumed to be:
        img_channelname_t***_p***_z***.tif

    :param str file_name: File name or path
    :param list[str] channel_names: Expanding list of channel names
    :param dict meta_row: Metadata for frame (one row in dataframe)
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
