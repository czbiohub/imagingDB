import nose.tools
from testfixtures import TempDirectory
import tifffile
import numpy as np
import os
import datetime

import imaging_db.utils.meta_utils as meta_utils


def test_make_dataframe():
    nbr_frames = 3
    test_col_names = ["A", "B"]
    frames_meta = meta_utils.make_dataframe(
        nbr_frames=nbr_frames,
        col_names=test_col_names,
    )
    nose.tools.assert_equal(frames_meta.shape, (nbr_frames, len(test_col_names)))
    nose.tools.assert_equal(test_col_names, list(frames_meta))


def test_make_empty_dataframe():
    expected_names = [
        "channel_idx",
        "slice_idx",
        "time_idx",
        "channel_name",
        "file_name",
        "pos_idx"]
    frames_meta = meta_utils.make_dataframe(nbr_frames=None)
    nose.tools.assert_equal(expected_names, list(frames_meta))
    nose.tools.assert_true(frames_meta.empty)


def test_validate_global_meta():
    global_meta = {
        "s3_dir": "dir_name",
        "nbr_frames": 5,
        "im_height": 256,
        "im_width": 256,
        "im_colors": 1,
        "bit_depth": "uint16",
        "nbr_slices": 6,
        "nbr_channels": 7,
        "nbr_timepoints": 8,
        "nbr_positions": 9,
    }
    meta_utils.validate_global_meta(global_meta)

def test_gen_sha256_numpy():
    expected_sha = 'd1b8118646637256b66ef034778f8d0add8d00436ad1ebb051ef09cf19dbf2d2'

    # Temporary file with 6 frames, tifffile stores channels first
    im = 50 * np.ones((6, 50, 50), dtype=np.uint16)

    sha = meta_utils.gen_sha256(im)
    nose.tools.assert_equal(expected_sha, sha)

def test_gen_sha256_file():
    expected_sha = 'af87894cc23928df908b02bd94842d063a5c7aae9eb1bbc2bb5c9475d674bcba'

    tempdir = TempDirectory()
    temp_path = tempdir.path

    # Temporary file with 6 frames, tifffile stores channels first
    im = 50 * np.ones((6, 10, 15), dtype=np.uint16)
    im[0, :5, 3:12] = 50000
    im[2, :5, 3:12] = 40000
    im[4, :5, 3:12] = 30000
    
    description = 'ImageJ=1.52e\nimages=6\nchannels=2\nslices=3\nmax=10411.0'

    # Save test tif file
    file_path = os.path.join(temp_path, "A1_2_PROTEIN_test.tif")
    tifffile.imsave(file=file_path,
                    data=im,
                    description=description,
                    datetime=datetime.datetime(2019, 1, 1))

    sha = meta_utils.gen_sha256(file_path)
    nose.tools.assert_equal(expected_sha, sha)

@nose.tools.raises(AssertionError)
def test_validate_global_meta_invalid():
    global_meta = {
        "s3_dir": "dir_name",
        "nbr_frames": 5,
        "im_height": 256,
        "im_width": 256,
        "im_colors": None,
        "bit_depth": "uint16",
        "nbr_slices": 6,
        "nbr_channels": 7,
        "nbr_timepoints": 8,
        "nbr_positions": 9,
    }
    meta_utils.validate_global_meta(global_meta)

@nose.tools.raises(AssertionError)
def test_validate_global_meta_missing():
    global_meta = {
        "s3_dir": "dir_name",
    }
    meta_utils.validate_global_meta(global_meta)

def tearDown(self):
        """
        Tear down temporary folder and files and stop S3 mock
        """
        TempDirectory.cleanup_all()
