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

import imaging_db.images.tiffolder_splitter as tif_splitter
import imaging_db.metadata.json_validator as json_ops
import imaging_db.utils.image_utils as im_utils


class TestTifFolderSplitter(unittest.TestCase):

    def setUp(self):
        """
        Set up temporary test directory and mock S3 bucket connection
        """
        # Mock S3 dir
        self.s3_dir = "raw_frames/SMS-2010-01-01-00-00-00-0001"
        # Create temporary directory and write temp image
        self.tempdir = TempDirectory()
        self.temp_path = self.tempdir.path
        # Temporary frame
        self.im = np.ones((10, 15), dtype=np.uint16)
        self.im[2:5, 3:12] = 10000
        # File metadata
        ijmeta = {"Info": json.dumps({"testkey": "testvalue"})}
        # Save test tif files
        self.channel_names = ['phase', 'brightfield', 'phase', '666']
        # Write files in dir
        for i, c in enumerate(self.channel_names):
            file_name = 'img_{}_t000_p050_z00{}.tif'.format(c, i)
            file_path = os.path.join(self.temp_path, file_name)
            tifffile.imsave(file_path,
                            self.im + 5000 * i,
                            ijmetadata=ijmeta,
                            )
        # Write external metadata in dir
        meta_dict = {'Summary': {'Slices': 26,
                                'PixelType': 'GRAY16',
                                'Time': '2018-11-01 19:20:34 -0700',
                                'z-step_um': 0.5,
                                'PixelSize_um': 0,
                                'BitDepth': 16,
                                'Width': 15,
                                'Height': 10},
                    }
        json_filename = os.path.join(self.temp_path, 'metadata.txt')
        json_ops.write_json_file(meta_dict, json_filename)

        # Setup mock S3 bucket
        self.mock = mock_s3()
        self.mock.start()
        self.conn = boto3.resource('s3', region_name='us-east-1')
        self.bucket_name = 'czbiohub-imaging'
        self.conn.create_bucket(Bucket=self.bucket_name)
        # Instantiate file parser class
        self.frames_inst = tif_splitter.TifFolderSplitter(
            data_path=self.temp_path,
            s3_dir=self.s3_dir,
            override=False,
            file_format=".png",
        )
        # Upload data
        self.frames_inst.get_frames_and_metadata(
            filename_parser='parse_sms_name'
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

        self.assertEqual(global_meta['nbr_frames'], 4)
        self.assertEqual(global_meta['bit_depth'], 'uint16')
        self.assertEqual(global_meta['nbr_channels'], 3)
