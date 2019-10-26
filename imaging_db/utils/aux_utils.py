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
                             'tiff_id',
                             'slide_explorer'}, \
        ("frames_format should be 'ome_tiff', 'tif_folder' or 'tif_id'",
         "not {}".format(frames_format))

    class_dict = {'ome_tiff': 'OmeTiffSplitter',
                  'ome_tif': 'OmeTiffSplitter',
                  'slide_explorer': 'SlideExplorerSplitter',
                  'tif_folder': 'TifFolderSplitter',
                  'tiff_folder': 'TifFolderSplitter',
                  'tif_id': 'TifIDSplitter',
                  'tiff_id': 'TifIDSplitter',
                  'tiff': 'OmeTiffSplitter',
                  }
    module_dict = {'ome_tiff': 'images.ometif_splitter',
                   'ome_tif': 'images.ometif_splitter',
                   'slide_explorer': 'images.slide_explorer_splitter',
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


def get_storage_class(storage_type):
    """
    Given storage_type, 'local' or 's3', import filestorage class.

    :param str storage_type: What format your files are stored in
    :return class storage_class: Filestorage class
    """
    storage_type = storage_type.lower()
    assert storage_type in {'local', 's3'},\
        "storage should be local or s3, not {}".format(storage_type)

    class_dict = {'s3': 'S3Storage',
                  'local': 'LocalStorage',
                  }
    module_dict = {'s3': 'filestorage.s3_storage',
                   'local': 'filestorage.local_storage',
                   }
    # Dynamically import class
    storage_class = import_class(
        module_dict[storage_type],
        class_dict[storage_type],
    )
    return storage_class
