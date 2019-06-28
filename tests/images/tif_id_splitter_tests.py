import boto3
from moto import mock_s3
import nose.tools
import numpy as np
import numpy.testing
import os
from testfixtures import TempDirectory
import tifffile
import unittest
from unittest.mock import patch

import imaging_db.images.tif_id_splitter as tif_id_splitter
import imaging_db.utils.image_utils as im_utils


class TestTifIDSplitter(unittest.TestCase):

    def setUp(self):
        """
        Set up temporary test directory and mock S3 bucket connection
        """
        # Test metadata parameters
        self.nbr_channels = 2
        self.nbr_slices = 3
        # Mock S3 dir
        self.s3_dir = "raw_frames/ML-2005-06-09-20-00-00-1000"
        # Create temporary directory and write temp image
        self.tempdir = TempDirectory()
        self.temp_path = self.tempdir.path
        # Temporary file with 6 frames, tifffile stores channels first
        self.im = 50 * np.ones((6, 10, 15), dtype=np.uint16)
        self.im[0, :5, 3:12] = 50000
        self.im[2, :5, 3:12] = 40000
        self.im[4, :5, 3:12] = 30000
        # Metadata
        self.description = 'ImageJ=1.52e\nimages=6\nchannels=2\nslices=3\nmax=10411.0'
        # Save test tif file
        self.file_path = os.path.join(self.temp_path, "A1_2_PROTEIN_test.tif")
        tifffile.imsave(self.file_path,
                        self.im,
                        description=self.description,
                        )

        # Setup mock S3 bucket
        self.mock = mock_s3()
        self.mock.start()
        self.conn = boto3.resource('s3', region_name='us-east-1')
        self.bucket_name = 'czbiohub-imaging'
        self.conn.create_bucket(Bucket=self.bucket_name)
        # Instantiate file parser class
        self.frames_inst = tif_id_splitter.TifIDSplitter(
            data_path=self.file_path,
            s3_dir="raw_frames/ML-2005-06-09-20-00-00-1000",
            override=False,
            file_format=".png",
        )

        # Upload data
        self.frames_inst.get_frames_and_metadata(
            filename_parser="parse_ml_name",
        )

    def tearDown(self):
        """
        Tear down temporary folder and files and stop S3 mock
        """
        TempDirectory.cleanup_all()
        nose.tools.assert_equal(os.path.isdir(self.temp_path), False)
        self.mock.stop()

    def test_set_frame_info(self):
        expected_shape = [self.im.shape[1], self.im.shape[2]]
        nose.tools.assert_equal(self.frames_inst.frame_shape, expected_shape)
        nose.tools.assert_equal(self.frames_inst.bit_depth, 'uint16')
        nose.tools.assert_equal(self.frames_inst.im_colors, 1)

    def test_set_frame_info_uint8(self):
        frames = tifffile.TiffFile(self.file_path)
        page = frames.pages[0]
        page.tags["BitsPerSample"].value = 8
        self.frames_inst.set_frame_info(page)
        self.assertEqual(self.frames_inst.bit_depth, 'uint8')

    def test_set_frame_info_float_to_int(self):
        frames = tifffile.TiffFile(self.file_path)
        page = frames.pages[0]
        page.tags["BitsPerSample"].value = 32
        float2uint = self.frames_inst.set_frame_info(page)
        self.assertEqual(self.frames_inst.bit_depth, 'uint16')
        self.assertTrue(float2uint)

    @nose.tools.raises(ValueError)
    def test_set_frame_info_invalid_depth(self):
        frames = tifffile.TiffFile(self.file_path)
        page = frames.pages[0]
        page.tags["BitsPerSample"].value = 5
        self.frames_inst.set_frame_info(page)

    def test_get_params_from_string(self):
        indices = self.frames_inst._get_params_from_str(self.description)
        nose.tools.assert_equal(indices['nbr_channels'], self.nbr_channels)
        nose.tools.assert_equal(indices['nbr_slices'], self.nbr_slices)
        nose.tools.assert_equal(indices['nbr_timepoints'], 1)
        nose.tools.assert_equal(indices['nbr_positions'], 1)

    def test_get_params_from_string_frames_pos(self):
        description = 'ImageJ=1.52e\nimages=6\nframes=3\npositions=4\nmax=10411.0'
        indices = self.frames_inst._get_params_from_str(description)
        nose.tools.assert_equal(indices['nbr_channels'], 1)
        nose.tools.assert_equal(indices['nbr_slices'], 1)
        nose.tools.assert_equal(indices['nbr_timepoints'], 3)
        nose.tools.assert_equal(indices['nbr_positions'], 4)

    def test_get_frames_and_meta(self):
        # Expected uploaded im names, channels indices should increment before
        # slice to match self.im
        im_names = [
            "im_c000_z000_t000_p000.png",
            "im_c001_z000_t000_p000.png",
            "im_c000_z001_t000_p000.png",
            "im_c001_z001_t000_p000.png",
            "im_c000_z002_t000_p000.png",
            "im_c001_z002_t000_p000.png",
        ]
        # Download uploaded data and compare to im
        for i, im_name in enumerate(im_names):
            key = "/".join([self.s3_dir, im_name])
            byte_string = self.conn.Object(
                self.bucket_name, key).get()['Body'].read()
            # Construct an array from the bytes and decode image
            im = im_utils.deserialize_im(byte_string)
            # Assert that contents are the same
            nose.tools.assert_equal(im.dtype, np.uint16)
            numpy.testing.assert_array_equal(im, self.im[i, ...])

    @patch('imaging_db.images.tif_id_splitter.TifIDSplitter.set_frame_info')
    def test_get_frames_and_meta_no_parser(self, set_mock_info):
        set_mock_info.return_value = True
        self.frames_inst.get_frames_and_metadata()
        self.assertDictEqual(
            self.frames_inst.global_json,
            {'file_origin': self.file_path},
        )
        self.assertEqual(self.frames_inst.bit_depth, 'uint16')

    def test_generate_hash(self):
        expected_hash = [
            '5aafc4b96e20644bc0d237b8ec52f1f592c28609f01c0eb9d1342a6b6266ae75',
            '075aedba73ced5d4f1200f9304f5f1115bb83d05898c8d601e4b7a8a90a51754',
            '0515c9e343701f9e2551f91ea51d1a7231941d4db028e929ed2d338eac48b5cb',
            '075aedba73ced5d4f1200f9304f5f1115bb83d05898c8d601e4b7a8a90a51754',
            '001fa77b7c20cd157e725defa454609f7e278303f8e59645479ab8fb1ad57330',
            '075aedba73ced5d4f1200f9304f5f1115bb83d05898c8d601e4b7a8a90a51754',
        ]

        sha = self.frames_inst.frames_meta.sha256.tolist()

        nose.tools.assert_equal(expected_hash, sha)


