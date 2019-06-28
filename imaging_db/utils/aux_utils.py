import importlib
import inspect


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
    except Exception as e:
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
