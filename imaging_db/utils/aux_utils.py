import os


def parse_filename(file_name):
    """
    Parse metadata from file name or file path.
    This function is custom for the ML group, who has the following file
    naming convention:
    "[plate ID]_[number]_[protein name]_PyProcessed.tif”
    And they would like to include plate_id, number, and protein_name in their
    global metadata.

    :param str file_name: File name or path
    :return dict meta_json: Global metadata
    :raises AssertionError: If the file name contains less than 3 '_'
    """
    # Get rid of path if present
    file_str = os.path.basename(file_name)
    str_list = file_str.split('_')
    assert len(str_list) >= 4, "File name is supposed to contain at least 3 '_'"
    meta_json = {"plate_id": str_list[0],
                 "number": str_list[1],
                 "protein_name": str_list[-2]}

    return meta_json
