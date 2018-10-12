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


def get_ijmeta():
    """
    Helper function that creates IJMetadata
    :return: IJMetadata as string
    """
    ijmeta = {"Info": {"InitialPositionList": [{"Label": "Pos1"},
                                               {"Label": "Pos3"}]}}

    ijmeta = json.dumps(ijmeta)
    ijmeta = ijmeta.encode('utf-16<')
    return ijmeta

def get_mmmeta(pos_idx=1):
    """
    Helper function that creates MicroManagerMetadata
    :param pos_idx: Position index
    :return: metadata as string
    """
    return json.dumps({
            "ChannelIndex": 1,
            "Slice": 2,
            "FrameIndex": 3,
            "PositionIndex": pos_idx,
            "Channel": "channel_name",
        })


class TestOmeTiffSplitter(unittest.TestCase):

    def setUp(self):
        """
        Set up temporary test directory and mock S3 bucket connection
        """
        self.s3_dir = "raw_frames/ISP-2005-06-09-20-00-00-0001"
        # Create temporary directory and write temp image
        self.tempdir = TempDirectory()
        self.temp_path = self.tempdir.path
        # Temporary frame
        self.im = np.zeros((15, 12), dtype=np.uint16)
        self.im[0:5, 3:7] = 5000
        # Metadata
        mmmetadata = get_mmmeta()
        ijmetadata = get_ijmeta()
        extra_tags = [('MicroManagerMetadata', 's', 0, mmmetadata, True),
                      ('IJMetadata', 's', 0, ijmetadata, True),
                      ('IJMetadata', 's', 0, ijmetadata, True)]
        # Save test ome tif file
        file_path = os.path.join(self.temp_path, "test_Pos_1.ome.tif")
        tifffile.imsave(file_path,
                        self.im,
                        extratags=extra_tags)

        mmmetadata = get_mmmeta(pos_idx=3)
        extra_tags = [('MicroManagerMetadata', 's', 0, mmmetadata, True),
                      ('IJMetadata', 's', 0, ijmetadata, True)]
        # Save test ome tif file
        file_path = os.path.join(self.temp_path, "test_Pos_3.ome.tif")
        tifffile.imsave(file_path,
                        self.im,
                        description="test",
                        extratags=extra_tags)
        # Setup mock S3 bucket
        self.mock = mock_s3()
        self.mock.start()
        self.conn = boto3.resource('s3', region_name='us-east-1')
        self.bucket_name = 'czbiohub-imaging'
        self.conn.create_bucket(Bucket=self.bucket_name)

    def tearDown(self):
        """
        Tear down temporary folder and files and stop S3 mock
        """
        TempDirectory.cleanup_all()
        nose.tools.assert_equal(os.path.isdir(self.temp_path), False)
        self.mock.stop()

    def test_init(self):
        file_path = os.path.join(self.temp_path, "test_Pos_1.ome.tif")
        frames = tifffile.TiffFile(file_path)
        print(len(frames.pages))
        page = frames.pages[0]
        print("MMMetadata", page.tags['MicroManagerMetadata'].value)
        ijmeta = page.tags['IJMetadata'].value
        print("meta type", type(ijmeta))
        print(ijmeta)
        ijmeta = json.loads(ijmeta)
        print("IJMetadata", ijmeta)

        assert 0 == 1