import boto3
import itertools
import json
from moto import mock_s3
import natsort
import nose.tools
import numpy as np
import numpy.testing
import os
from testfixtures import TempDirectory
import tifffile
import unittest
from unittest.mock import patch

import imaging_db.images.tiffolder_splitter as tif_splitter
import imaging_db.images.filename_parsers as file_parsers
import imaging_db.metadata.json_operations as json_ops
import imaging_db.utils.aux_utils as aux_utils
import imaging_db.utils.image_utils as im_utils
import imaging_db.utils.meta_utils as meta_utils


def map_mock(fn, *iterables):
    """
    Mocking out the map function of multiprocessing because moto
    doesn't play well with multiprocessing
    """
    res = []
    for i in iterables[0]:
        temp_res = fn(i)
        res.append(temp_res)
    return res


class TestTifFolderSplitter(unittest.TestCase):

    @patch('concurrent.futures.ProcessPoolExecutor')
    def setUp(self, MockPoolExecutor):
        """
        Set up temporary test directory and mock S3 bucket connection
        """
        # Magic mocking of multiprocessing
        MockPoolExecutor().__enter__().map = map_mock
        # Mock S3 directory for upload
        self.storage_dir = "raw_frames/SMS-2010-01-01-00-00-00-0001"
        # Create temporary directory and write temp image
        self.tempdir = TempDirectory()
        self.temp_path = self.tempdir.path
        # Temporary frame
        self.im = np.ones((10, 15), dtype=np.uint16)
        self.im[2:5, 3:12] = 10000
        # Save test tif files
        self.channel_names = ['phase', 'brightfield', '666']
        # Write files in dir
        for c in self.channel_names:
            for z in range(2):
                file_name = 'img_{}_t000_p050_z00{}.tif'.format(c, z)
                file_path = os.path.join(self.temp_path, file_name)
                ijmeta = {"Info": json.dumps({"c": c, "z": z})}
                tifffile.imsave(
                    file_path,
                    self.im + 5000 * z,
                    ijmetadata=ijmeta,
                )
        # Write external metadata in dir
        self.meta_dict = {
            'Summary': {'Slices': 26,
                        'PixelType': 'GRAY16',
                        'Time': '2018-11-01 19:20:34 -0700',
                        'z-step_um': 0.5,
                        'PixelSize_um': 0,
                        'BitDepth': 16,
                        'Width': 15,
                        'Height': 10},
        }
        self.json_filename = os.path.join(self.temp_path, 'metadata.txt')
        json_ops.write_json_file(self.meta_dict, self.json_filename)

        # Setup mock S3 bucket
        self.mock = mock_s3()
        self.mock.start()
        self.conn = boto3.resource('s3', region_name='us-east-1')
        self.bucket_name = 'czbiohub-imaging'
        self.conn.create_bucket(Bucket=self.bucket_name)
        # Instantiate file parser class
        storage_class = aux_utils.get_storage_class('s3')
        self.frames_inst = tif_splitter.TifFolderSplitter(
            data_path=self.temp_path,
            storage_dir=self.storage_dir,
            storage_class=storage_class,
        )
        # Upload data
        self.frames_inst.get_frames_and_metadata(
            filename_parser='parse_sms_name',
        )

    def tearDown(self):
        """
        Tear down temporary folder and files and stop S3 mock
        """
        TempDirectory.cleanup_all()
        nose.tools.assert_equal(os.path.isdir(self.temp_path), False)
        self.mock.stop()

    def test_get_global_meta(self):
        global_meta = self.frames_inst.get_global_meta()

        self.assertEqual(global_meta['nbr_frames'], 6)
        self.assertEqual(global_meta['bit_depth'], 'uint16')
        self.assertEqual(global_meta['nbr_channels'], 3)
        self.assertEqual(global_meta['nbr_slices'], 2)
        self.assertEqual(global_meta['nbr_timepoints'], 1)
        self.assertEqual(global_meta['nbr_positions'], 1)
        self.assertEqual(global_meta['im_colors'], 1)
        self.assertEqual(global_meta['im_height'], self.im.shape[0])
        self.assertEqual(global_meta['im_width'], self.im.shape[1])

    def test_get_global_json(self):
        global_json = self.frames_inst.get_global_json()
        self.assertDictEqual(global_json, self.meta_dict)

    def test_get_frames_meta(self):
        frames_meta = self.frames_inst.get_frames_meta()
        for i, (c, z) in enumerate(itertools.product(range(3), range(2))):
            # Validate file name
            expected_name = 'im_c00{}_z00{}_t000_p050.png'.format(c, z)
            self.assertEqual(frames_meta.loc[i, 'file_name'], expected_name)
            # Validate checksum
            expected_sha = meta_utils.gen_sha256(self.im + 5000 * z)
            self.assertEqual(frames_meta.loc[i, 'sha256'], expected_sha)
            # Validate indices
            self.assertEqual(frames_meta.loc[i, 'channel_idx'], c)
            self.assertEqual(frames_meta.loc[i, 'slice_idx'], z)
            self.assertEqual(frames_meta.loc[i, 'time_idx'], 0)
            self.assertEqual(frames_meta.loc[i, 'pos_idx'], 50)

    def test_get_frames_json(self):
        frames_json = self.frames_inst.get_frames_json()
        # Channels will be sorted
        sorted_channels = natsort.natsorted(self.channel_names)
        self.assertEqual(len(frames_json), 6)
        for i, (c, z) in enumerate(itertools.product(range(3), range(2))):
            frame_i = frames_json[i]
            meta_info = json.loads(frame_i['IJMetadata']['Info'])
            self.assertDictEqual(
                meta_info,
                {"c": sorted_channels[c], "z": z},
            )
            frame_i['BitsPerSample'] = 16
            frame_i['ImageWidth'] = 15
            frame_i['ImageLength'] = 10

    def test_set_frame_info(self):
        meta_dict = {'PixelType': 'RGB',
                     'BitDepth': 8,
                     'Width': 250,
                     'Height': 150,
                     }
        self.frames_inst.set_frame_info(meta_dict)
        self.assertEqual(self.frames_inst.bit_depth, 'uint8')
        self.assertEqual(self.frames_inst.im_colors, 3)
        self.assertListEqual(self.frames_inst.frame_shape, [150, 250])

    def test_set_frame_info_uint16(self):
        meta_dict = {'PixelType': 'GRAY',
                     'BitDepth': 16,
                     'Width': 250,
                     'Height': 150,
                     }
        self.frames_inst.set_frame_info(meta_dict)
        self.assertEqual(self.frames_inst.bit_depth, 'uint16')
        self.assertEqual(self.frames_inst.im_colors, 1)

    @nose.tools.raises(ValueError)
    def test_set_frame_info(self):
        meta_dict = {'PixelType': 'RGB',
                     'BitDepth': 'float32',
                     'Width': 250,
                     'Height': 150,
                     }
        self.frames_inst.set_frame_info(meta_dict)

    def test_set_frame_info_from_file(self):
        file_name = 'img_phase_t000_p050_z001.tif'
        file_path = os.path.join(self.temp_path, file_name)
        self.frames_inst.set_frame_info_from_file(file_path)
        self.assertEqual(self.frames_inst.bit_depth, 'uint16')
        self.assertEqual(self.frames_inst.im_colors, 1)
        self.assertListEqual(self.frames_inst.frame_shape, [10, 15])

    def test_set_frame_info_from_file_color(self):
        self.tempdir.makedir('test_dir')
        file_path = os.path.join(self.temp_path, 'test_dir/im_temp.tif')
        im = np.zeros((10, 20, 3), dtype=np.uint8)
        tifffile.imsave(file_path, im)
        self.frames_inst.set_frame_info_from_file(file_path)
        self.assertEqual(self.frames_inst.bit_depth, 'uint8')
        self.assertEqual(self.frames_inst.im_colors, 3)
        self.assertListEqual(self.frames_inst.frame_shape, [10, 20])

    @nose.tools.raises(ValueError)
    def test_set_frame_info_from_file_float(self):
        self.tempdir.makedir('test_dir')
        file_path = os.path.join(self.temp_path, 'test_dir/im_temp.tif')
        im = np.zeros((10, 20, 3), dtype=np.float32)
        tifffile.imsave(file_path, im)
        self.frames_inst.set_frame_info_from_file(file_path)

    def test_set_frame_meta(self):
        parse_func = getattr(file_parsers, 'parse_sms_name')
        file_name = 'im_weird_channel_with_underscores_t020_z030_p040.tif'
        meta_row = self.frames_inst._set_frame_meta(parse_func, file_name)
        self.assertEqual(
            meta_row['channel_name'],
            'weird_channel_with_underscores',
        )
        self.assertEqual(meta_row['channel_idx'], 3)
        self.assertEqual(meta_row['time_idx'], 20)
        self.assertEqual(meta_row['slice_idx'], 30)
        self.assertEqual(meta_row['pos_idx'], 40)

    def test_get_frames_and_metadata(self):
        # Download uploaded data and compare to self.im
        for i, (c, z) in enumerate(itertools.product(range(3), range(2))):
            im_name = 'im_c00{}_z00{}_t000_p050.png'.format(c, z)
            key = "/".join([self.storage_dir, im_name])
            byte_string = self.conn.Object(
                self.bucket_name, key).get()['Body'].read()
            # Construct an array from the bytes and decode image
            im = im_utils.deserialize_im(byte_string)
            # Assert that contents are the same
            self.assertEqual(im.dtype, np.uint16)
            numpy.testing.assert_array_equal(im, self.im + 5000 * z)

    @nose.tools.raises(AttributeError)
    def test_get_frames_and_metadata_no_parser(self):
        self.frames_inst.get_frames_and_metadata(
            filename_parser='nonexisting_function',
        )

    @patch('concurrent.futures.ProcessPoolExecutor')
    def test_get_frames_no_metadata(self, MockPoolExecutor):
        # Magic mocking of multiprocessing
        MockPoolExecutor().__enter__().map = map_mock
        os.remove(self.json_filename)
        self.frames_inst.get_frames_and_metadata(
            filename_parser='parse_sms_name',
        )
        frames_meta = self.frames_inst.get_frames_meta()
        for i, (c, z) in enumerate(itertools.product(range(3), range(2))):
            # Validate file name
            expected_name = 'im_c00{}_z00{}_t000_p050.png'.format(c, z)
            self.assertEqual(frames_meta.loc[i, 'file_name'], expected_name)
            # Validate checksum
            expected_sha = meta_utils.gen_sha256(self.im + 5000 * z)
            self.assertEqual(frames_meta.loc[i, 'sha256'], expected_sha)
            # Validate indices
            self.assertEqual(frames_meta.loc[i, 'channel_idx'], c)
            self.assertEqual(frames_meta.loc[i, 'slice_idx'], z)
            self.assertEqual(frames_meta.loc[i, 'time_idx'], 0)
            self.assertEqual(frames_meta.loc[i, 'pos_idx'], 50)
