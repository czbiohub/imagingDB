import boto3
import json
from moto import mock_s3
import nose.tools
import numpy as np
import numpy.testing
import os
from testfixtures import TempDirectory
import tifffile
import unittest

import imaging_db.images.ometif_splitter as ometif_splitter
import imaging_db.utils.image_utils as im_utils


class TestOmeTiffSplitter(unittest.TestCase):

    def _get_ijmeta(self):
        """
        Helper function that creates IJMetadata
        :return: IJMetadata as string
        """
        ijinfo = {"InitialPositionList": [{"Label": "Pos1"}, {"Label": "Pos3"}]}
        return {"Info": json.dumps(ijinfo)}

    def _get_mmmeta(self, pos_idx=1):
        """
        Helper function that creates MicroManagerMetadata
        :param pos_idx: Position index
        :return: metadata as string
        """
        return json.dumps({
            "ChannelIndex": self.channel_idx,
            "Slice": self.slice_idx,
            "FrameIndex": self.time_idx,
            "PositionIndex": pos_idx,
            "Channel": self.channel_name,
        })

    def setUp(self):
        """
        Set up temporary test directory and mock S3 bucket connection
        """
        # Test metadata parameters
        self.channel_idx = 1
        self.slice_idx = 2
        self.time_idx = 3
        self.channel_name = "TESTCHANNEL"
        # Mock S3 dir
        self.s3_dir = "raw_frames/ISP-2005-06-09-20-00-00-0001"
        # Create temporary directory and write temp image
        self.tempdir = TempDirectory()
        self.temp_path = self.tempdir.path
        # Temporary frame
        self.im = np.ones((10, 15), dtype=np.uint16)
        self.im[2:5, 3:12] = 50000
        # Metadata
        mmmetadata = self._get_mmmeta()
        ijmeta = self._get_ijmeta()
        extra_tags = [('MicroManagerMetadata', 's', 0, mmmetadata, True)]
        # Save test ome tif file
        self.file_path1 = os.path.join(self.temp_path, "test_Pos1.ome.tif")
        tifffile.imsave(self.file_path1,
                        self.im,
                        ijmetadata=ijmeta,
                        extratags=extra_tags,
                        )
        mmmetadata = self._get_mmmeta(pos_idx=3)
        extra_tags = [('MicroManagerMetadata', 's', 0, mmmetadata, True)]
        # Save test ome tif file
        self.file_path3 = os.path.join(self.temp_path, "test_Pos3.ome.tif")
        tifffile.imsave(self.file_path3,
                        self.im,
                        ijmetadata=ijmeta,
                        extratags=extra_tags)
        # Setup mock S3 bucket
        self.mock = mock_s3()
        self.mock.start()
        self.conn = boto3.resource('s3', region_name='us-east-1')
        self.bucket_name = 'czbiohub-imaging'
        self.conn.create_bucket(Bucket=self.bucket_name)
        # Instantiate file parser class
        self.frames_inst = ometif_splitter.OmeTiffSplitter(
            data_path=self.temp_path,
            s3_dir="raw_frames/ISP-2005-06-09-20-00-00-0001",
            override=False,
            file_format=".png",
        )
        # Get path to json schema file
        dir_name = os.path.dirname(__file__)
        self.schema_file_path = os.path.realpath(
            os.path.join(dir_name, '../../metadata_schema.json'),
        )
        # Upload data
        self.frames_inst.get_frames_and_metadata(
            schema_filename=self.schema_file_path,
            positions='[1, 3]',
        )

    def tearDown(self):
        """
        Tear down temporary folder and files and stop S3 mock
        """
        TempDirectory.cleanup_all()
        nose.tools.assert_equal(os.path.isdir(self.temp_path), False)
        self.mock.stop()

    def test_get_frames_and_meta(self):
        # Expected uploaded im names based on test metadata parameters
        im_names = [
            "im_c001_z002_t003_p001.png",
            "im_c001_z002_t003_p003.png",
        ]
        # Download uploaded data and compare to im
        for im_name in im_names:
            key = "/".join([self.s3_dir, im_name])
            byte_string = self.conn.Object(
                self.bucket_name, key).get()['Body'].read()
            # Construct an array from the bytes and decode image
            im = im_utils.deserialize_im(byte_string)
            # Assert that contents are the same
            nose.tools.assert_equal(im.dtype, np.uint16)
            numpy.testing.assert_array_equal(im, self.im)

    def test_set_frame_info(self):
        expected_shape = [self.im.shape[0], self.im.shape[1]]
        nose.tools.assert_equal(self.frames_inst.frame_shape, expected_shape)
        nose.tools.assert_equal(self.frames_inst.bit_depth, 'uint16')
        nose.tools.assert_equal(self.frames_inst.im_colors, 1)

    def test_split_file(self):
        # Test splitting file with position idx 3
        frames_meta, im_stack = self.frames_inst.split_file(
            file_path=self.file_path3,
            schema_filename=self.schema_file_path,
        )
        # meta
        nose.tools.assert_equal(frames_meta.loc[0, 'channel_idx'],
                                self.channel_idx)
        nose.tools.assert_equal(frames_meta.loc[0, 'time_idx'],
                                self.time_idx)
        nose.tools.assert_equal(frames_meta.loc[0, 'slice_idx'],
                                self.slice_idx)
        nose.tools.assert_equal(frames_meta.loc[0, 'channel_name'],
                                self.channel_name)
        nose.tools.assert_equal(frames_meta.loc[0, 'pos_idx'],
                                3)
        nose.tools.assert_equal(frames_meta.loc[0, 'file_name'],
                                "im_c001_z002_t003_p003.png")
        # The file has one frame and is gray, expecting shape (10, 15, 1, 1)
        self.assertSequenceEqual(im_stack.shape, (10, 15, 1, 1))
        # Assert that im_stack without extra dimensions is self.im
        numpy.testing.assert_array_equal(np.squeeze(im_stack), self.im)

    def test_validate_file_paths(self):
        postions = [0, 3]
        file_paths = [self.file_path1, self.file_path3]
        found_paths = self.frames_inst._validate_file_paths(
            positions=postions,
            glob_paths=file_paths,
        )
        # position 0 doesn't exist, only path for pos 3 should be returned
        nose.tools.assert_equal(len(found_paths), 1)
        nose.tools.assert_equal(found_paths[0], self.file_path3)

    @nose.tools.raises(AssertionError)
    def test_validate_no_matching_paths(self):
        postions = [100, 200]
        file_paths = [self.file_path1, self.file_path3]
        found_paths = self.frames_inst._validate_file_paths(
            positions=postions,
            glob_paths=file_paths,
        )
