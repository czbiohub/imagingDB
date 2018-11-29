import nose.tools

import imaging_db.utils.aux_utils as aux_utils


def test_parse_ml_name():
    file_name = '/Volumes/MicroscopyData/p6A1_1_CTRL1_PyProcessed.tif'
    meta_json = aux_utils.parse_ml_name(file_name)
    nose.tools.assert_equal(meta_json['plate_id'], 'p6A1')
    nose.tools.assert_equal(meta_json['stack_nbr'], 1)
    nose.tools.assert_equal(meta_json['protein_name'], 'CTRL1')


def test_parse_ml_name_long_protein():
    file_name = 'p6A1_5_Jin_G4_FBXO9_PyProcessed.tif'
    meta_json = aux_utils.parse_ml_name(file_name)
    nose.tools.assert_equal(meta_json['plate_id'], 'p6A1')
    nose.tools.assert_equal(meta_json['stack_nbr'], 5)
    nose.tools.assert_equal(meta_json['protein_name'], 'FBXO9')


@nose.tools.raises(AssertionError)
def test_parse_ml_name_no_underscores():
    file_name = '/Volumes/MicroscopyData/p6A1_1CTRL1PyProcessed.tif'
    aux_utils.parse_ml_name(file_name)


@nose.tools.raises(ValueError)
def test_parse_ml_name_stack_str():
    file_name = '/Volumes/MicroscopyData/p6A1_A_CTRL1_PyProcessed.tif'
    aux_utils.parse_ml_name(file_name)
