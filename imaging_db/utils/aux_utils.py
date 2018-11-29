import importlib
import inspect
import os


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
    global metadata.

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
        raise
    meta_json = {"plate_id": str_list[0],
                 "stack_nbr": stack_nbr,
                 "protein_name": str_list[-2]}

    return meta_json
