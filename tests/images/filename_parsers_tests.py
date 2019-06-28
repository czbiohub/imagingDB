import nose.tools

import imaging_db.images.filename_parsers as file_parsers
import imaging_db.utils.meta_utils as meta_utils


def test_parse_ml_name():
    file_name = '/Volumes/MicroscopyData/p6A1_1_CTRL1_PyProcessed.tif'
    meta_json = file_parsers.parse_ml_name(file_name)
    nose.tools.assert_equal(meta_json['plate_id'], 'p6A1')
    nose.tools.assert_equal(meta_json['stack_nbr'], 1)
    nose.tools.assert_equal(meta_json['protein_name'], 'CTRL1')


def test_parse_ml_name_long_protein():
    file_name = 'p6A1_5_FBXO9_Jin_G4_PyProcessed.tif'
    meta_json = file_parsers.parse_ml_name(file_name)
    nose.tools.assert_equal(meta_json['plate_id'], 'p6A1')
    nose.tools.assert_equal(meta_json['stack_nbr'], 5)
    nose.tools.assert_equal(meta_json['protein_name'], 'FBXO9')


@nose.tools.raises(AssertionError)
def test_parse_ml_name_no_underscores():
    file_name = '/Volumes/MicroscopyData/p6A1_1CTRL1PyProcessed.tif'
    file_parsers.parse_ml_name(file_name)


@nose.tools.raises(ValueError)
def test_parse_ml_name_stack_str():
    file_name = '/Volumes/MicroscopyData/p6A1_A_CTRL1_PyProcessed.tif'
    file_parsers.parse_ml_name(file_name)


def test_parse_sms_name():
    file_name = 'img_phase_t500_p400_z300.tif'
    channel_names = ['brightfield']
    meta_row = dict.fromkeys(meta_utils.DF_NAMES)
    file_parsers.parse_sms_name(file_name, meta_row, channel_names)
    nose.tools.assert_equal(channel_names, ['brightfield', 'phase'])
    nose.tools.assert_equal(meta_row['channel_name'], 'phase')
    nose.tools.assert_equal(meta_row['channel_idx'], 1)
    nose.tools.assert_equal(meta_row['time_idx'], 500)
    nose.tools.assert_equal(meta_row['pos_idx'], 400)
    nose.tools.assert_equal(meta_row['slice_idx'], 300)


def test_parse_sms_name_long_channel():
    file_name = 'img_long_c_name_t001_z002_p003.tif'
    channel_names = []
    meta_row = dict.fromkeys(meta_utils.DF_NAMES)
    file_parsers.parse_sms_name(file_name, meta_row, channel_names)
    nose.tools.assert_equal(channel_names, ['long_c_name'])
    nose.tools.assert_equal(meta_row['channel_name'], 'long_c_name')
    nose.tools.assert_equal(meta_row['channel_idx'], 0)
    nose.tools.assert_equal(meta_row['time_idx'], 1)
    nose.tools.assert_equal(meta_row['pos_idx'], 3)
    nose.tools.assert_equal(meta_row['slice_idx'], 2)


def test_parse_idx_from_name():
    file_name = 'im_c600_z500_t400_p300.png'
    channel_names = []
    meta_row = dict.fromkeys(meta_utils.DF_NAMES)
    file_parsers.parse_idx_from_name(file_name, meta_row, channel_names)
    nose.tools.assert_equal(channel_names, ['600'])
    nose.tools.assert_equal(meta_row['channel_name'], '600')
    nose.tools.assert_equal(meta_row['channel_idx'], 600)
    nose.tools.assert_equal(meta_row['slice_idx'], 500)
    nose.tools.assert_equal(meta_row['time_idx'], 400)
    nose.tools.assert_equal(meta_row['pos_idx'], 300)


@nose.tools.raises(AssertionError)
def test_parse_idx_from_name_no_channel():
    file_name = 'img_phase_t500_p400_z300.tif'
    channel_names = []
    meta_row = dict.fromkeys(meta_utils.DF_NAMES)
    file_parsers.parse_idx_from_name(file_name, meta_row, channel_names)
