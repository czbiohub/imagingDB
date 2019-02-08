import boto3
import cv2
from moto import mock_s3
import nose.tools
import numpy as np
import numpy.testing
import os
from testfixtures import TempDirectory
import unittest

import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.utils.image_utils as im_utils
import imaging_db.utils.meta_utils as meta_utils


class TestDataStorage(unittest.TestCase):

    def setUp(self):
        """
        Set up temporary test directory and mock S3 bucket connection
        """
        self.s3_dir = "raw_frames/ISP-2005-06-09-20-00-00-0001"
        # Create temporary directory and write temp image
        self.tempdir = TempDirectory()
        self.temp_path = self.tempdir.path
        # Write temporary image
        self.im = np.zeros((15, 12), dtype=np.uint16)
        self.im[0:5, 3:7] = 5000
        self.im_encoded = im_utils.serialize_im(self.im)
        self.im_name = 'im_0.png'
        self.tempdir.write(self.im_name, self.im_encoded)
        self.file_path = os.path.join(self.temp_path, self.im_name)
        # Create a grayscale image stack for testing
        self.im_stack = np.ones((10, 15, 2), np.uint16) * 3000
        self.im_stack[0:5, 2:4, 0] = 42
        self.im_stack[3:7, 12:14, 1] = 10000
        self.stack_names = ["im1.png", "im2.png"]
        # Setup mock S3 bucket
        self.mock = mock_s3()
        self.mock.start()
        self.conn = boto3.resource('s3', region_name='us-east-1')
        self.bucket_name = 'czbiohub-imaging'
        self.conn.create_bucket(Bucket=self.bucket_name)
        self.nbr_workers = 4

    def tearDown(self):
        """
        Tear down temporary folder and files and stop S3 mock
        """
        TempDirectory.cleanup_all()
        nose.tools.assert_equal(os.path.isdir(self.temp_path), False)
        self.mock.stop()

    def test_upload_file(self):
        data_storage = s3_storage.DataStorage(self.s3_dir, self.nbr_workers)
        data_storage.upload_file(file_name=self.file_path)
        # Make sure the image uploaded in setUp is unchanged
        key = "/".join([self.s3_dir, self.im_name])
        byte_string = self.conn.Object(self.bucket_name,
                                  key).get()['Body'].read()
        # Construct an array from the bytes and decode image
        im_out = im_utils.deserialize_im(byte_string)
        # Assert that contents are the same
        nose.tools.assert_equal(im_out.dtype, np.uint16)
        numpy.testing.assert_array_equal(im_out, self.im)

    def test_upload_frames(self):
        # Upload image stack
        s3_dir = "raw_frames/ML-2005-05-23-10-00-00-0001"
        data_storage = s3_storage.DataStorage(s3_dir, self.nbr_workers)
        data_storage.upload_frames(self.stack_names, self.im_stack)
        # Get images from uploaded stack and validate that the contents are unchanged
        for im_nbr in range(len(self.stack_names)):
            key = "/".join([s3_dir, self.stack_names[im_nbr]])
            byte_string = self.conn.Object(self.bucket_name, key).get()['Body'].read()
            # Construct an array from the bytes and decode image
            im = im_utils.deserialize_im(byte_string)
            # Assert that contents are the same
            nose.tools.assert_equal(im.dtype, np.uint16)
            nose.tools.assert_equal(im.shape, (10, 15))
            numpy.testing.assert_array_equal(im, self.im_stack[..., im_nbr])

    def test_upload_frames_color(self):
        # Create color image stack
        im_stack = np.ones((10, 15, 3, 2), np.uint16) * 3000
        im_stack[0:5, 2:4, :, 0] = 42
        im_stack[3:7, 12:14, :, 1] = 10000
        # Expected color image shape
        expected_shape = im_stack[..., 0].shape
        # Mock frame upload
        s3_dir = "raw_frames/ML-2005-05-23-10-00-00-0001"
        data_storage = s3_storage.DataStorage(s3_dir, self.nbr_workers)
        data_storage.upload_frames(self.stack_names, im_stack)
        # Get images and validate that the contents are unchanged
        for im_nbr in range(len(self.stack_names)):
            key = "/".join([s3_dir, self.stack_names[im_nbr]])
            byte_string = self.conn.Object(self.bucket_name,
                                           key).get()['Body'].read()
            # Construct an array from the bytes and decode image
            im = im_utils.deserialize_im(byte_string)
            # Assert that contents are the same
            nose.tools.assert_equal(im.shape, expected_shape)
            nose.tools.assert_equal(im.dtype, np.uint16)
            numpy.testing.assert_array_equal(im, im_stack[..., im_nbr])

    def test_upload_serialized(self):
        data_storage = s3_storage.DataStorage(self.s3_dir, self.nbr_workers)
        key = "/".join([self.s3_dir, self.im_name])
        key_byte_tuple = (key, self.im_encoded)
        data_storage.upload_serialized(key_byte_tuple)
        byte_string = self.conn.Object(self.bucket_name, key).get()['Body'].read()
        nose.tools.assert_equal(byte_string, self.im_encoded)

    def test_upload_file_get_im(self):
        data_storage = s3_storage.DataStorage(self.s3_dir, self.nbr_workers)
        data_storage.upload_file(file_name=self.file_path)
        # Load the temporary image
        im_out = data_storage.get_im(file_name=self.im_name)
        # Assert that contents are the same
        nose.tools.assert_equal(im_out.dtype, np.uint16)
        numpy.testing.assert_array_equal(im_out, self.im)

    def test_get_stack(self):
        data_storage = s3_storage.DataStorage(self.s3_dir, self.nbr_workers)
        data_storage.upload_frames(self.stack_names, self.im_stack)
        # Load image stack in memory
        stack_shape = (10, 15, 1, 2)
        im_out = data_storage.get_stack(
            self.stack_names,
            stack_shape=stack_shape,
            bit_depth=np.uint16)
        im_out = np.squeeze(im_out)
        nose.tools.assert_equal(self.im_stack.shape, im_out.shape)
        for im_nbr in range(self.im_stack.shape[-1]):
            # Assert that contents are the same
            numpy.testing.assert_array_equal(im_out[..., im_nbr],
                                             self.im_stack[..., im_nbr])

    def test_get_stack_from_meta(self):
        # Upload image stack
        s3_dir = "raw_frames/ML-2005-05-23-10-00-00-0001"
        data_storage = s3_storage.DataStorage(s3_dir, self.nbr_workers)
        data_storage.upload_frames(self.stack_names, self.im_stack)
        global_meta = {
            "s3_dir": s3_dir,
            "nbr_frames": 2,
            "im_height": 10,
            "im_width": 15,
            "nbr_slices": 1,
            "nbr_channels": 2,
            "im_colors": 1,
            "bit_depth": "uint16",
            "nbr_timepoints": 1,
            "nbr_positions": 1,
        }
        frames_meta = meta_utils.make_dataframe(
            nbr_frames=global_meta["nbr_frames"],
        )

        nbr_frames = self.im_stack.shape[2]
        sha = [None] * nbr_frames
        for i in range(nbr_frames):
            sha[i] = meta_utils.gen_sha256(self.im_stack[...,i])

        frames_meta.loc[0] = [0, 0, 0, "A", "im1.png", 0, sha[0]]
        frames_meta.loc[1] = [1, 0, 0, "B", "im2.png", 0, sha[1]]
        im_stack, dim_order = data_storage.get_stack_from_meta(
            global_meta,
            frames_meta,
        )
        # Stack has X = 10, Y = 15, grayscale, Z = 1, C = 2, T = 1, P = 1
        # so expected stack shape and order should be:
        expected_shape = (10, 15, 2)
        nose.tools.assert_equal(im_stack.shape, expected_shape)
        nose.tools.assert_equal(dim_order, "XYC")

    def test_download_files(self):
        s3_dir = "raw_frames/ML-2005-05-23-10-00-00-0001"
        data_storage = s3_storage.DataStorage(s3_dir, self.nbr_workers)
        data_storage.upload_frames(self.stack_names, self.im_stack)
        data_storage.download_files(
            file_names=self.stack_names,
            dest_dir=self.temp_path,
        )
        # Read downloaded file and assert that contents are the same
        for i, im_name in enumerate(self.stack_names):
            dest_path = os.path.join(self.temp_path, im_name)
            im_out = cv2.imread(dest_path,
                                cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
            nose.tools.assert_equal(im_out.dtype, np.uint16)
            numpy.testing.assert_array_equal(im_out, self.im_stack[..., i])

    def test_download_file(self):
        data_storage = s3_storage.DataStorage(self.s3_dir, self.nbr_workers)
        data_storage.upload_file(file_name=self.file_path)
        # Download the temporary image then read it and validate
        data_storage.download_file(
            file_name=self.im_name,
            dest_dir=self.temp_path,
        )
        # Read downloaded file and assert that contents are the same
        dest_path = os.path.join(self.temp_path, self.im_name)
        im_out = cv2.imread(dest_path, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
        nose.tools.assert_equal(im_out.dtype, np.uint16)
        numpy.testing.assert_array_equal(im_out, self.im)

