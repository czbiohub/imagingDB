import inspect
import nose.tools

import imaging_db.utils.aux_utils as aux_utils


def test_import_class():
    module_name = 'images.ometif_splitter'
    class_name = 'OmeTiffSplitter'
    class_inst = aux_utils.import_class(module_name, class_name)
    nose.tools.assert_true(inspect.isclass(class_inst))
    nose.tools.assert_equal(class_inst.__name__, 'OmeTiffSplitter')


@nose.tools.raises(ImportError)
def test_import_class():
    module_name = 'images.ometif_splitter'
    class_name = 'BadSplitter'
    aux_utils.import_class(module_name, class_name)


def test_get_splitter_class():
    frames_format = 'tiff_folder'
    class_inst = aux_utils.get_splitter_class(frames_format)
    nose.tools.assert_true(inspect.isclass(class_inst))
    nose.tools.assert_equal(class_inst.__name__, 'TifFolderSplitter')
