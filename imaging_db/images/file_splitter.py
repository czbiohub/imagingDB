from abc import ABCMeta, abstractmethod
import numpy as np
import pandas as pd

import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.utils.meta_utils as meta_utils


class FileSplitter(metaclass=ABCMeta):
    """Read different types of files and separate frame information"""

    def __init__(self,
                 data_path,
                 s3_dir,
                 override=False,
                 file_format=".png",
                 int2str_len=3):
        """
        :param str data_path: Full path to file or directory name
        :param str s3_dir: Folder name on S3 where data will be stored
        :param bool override: Will not continue DataStorage if dataset is already
         present on S3.
        :param str file_format: Image file format (preferred is png)
        :param int int2str_len: How many integers will be added to each index
        """
        self.data_path = data_path
        self.s3_dir = s3_dir
        self.file_format = file_format
        self.int2str_len = int2str_len
        self.im_stack = None
        self.frames_meta = None
        self.frames_json = None
        self.global_meta = None
        self.global_json = None
        # The following three parameters will be set in set_frame
        self.frame_shape = None
        self.im_colors = None
        self.bit_depth = None
        self.data_uploader = s3_storage.DataStorage(
            s3_dir=s3_dir,
        )
        if not override:
            self.data_uploader.assert_unique_id()

    def get_imstack(self):
        """
        Checks that image stack has been assigned and if so returns it
        :return np.array im_stack: Image stack
        """
        assert self.im_stack is not None,\
            "Image stack has not been assigned yet"
        return self.im_stack

    def get_global_meta(self):
        """
        Checks if metadata is assigned and if so returns it
        :return dict global_meta: Global metadata for file
        """
        assert self.global_meta is not None, \
            "global_meta has no values yet"
        return self.global_meta

    def get_global_json(self):
        """
        Checks if metadata is assigned and if so returns it
        :return dict global_json: Non-required (variable) global metadata
        """
        assert self.global_json is not None, \
            "global_json has no values yet"
        return self.global_json

    def _generate_hash(self, im_stack):
        """
        calculates the sha256 checksum for all image slices

        :param ndarray im_stack: image to be hashed
        :return list sha: sha256 hashes indexed by the image index

        """

        if im_stack.shape[3] == 1:
            sha = meta_utils.gen_sha256(im_stack[...,0])
        else:
            sha = []
            for i in range(im_stack.shape[3]):
                sha.append(meta_utils.gen_sha256(im_stack[..., i]))

        return sha

    def get_frames_meta(self):
        """
        Checks if metadata is assigned and if so returns it
        :return pd.DataFrame frames_meta: Associated metadata for each frame
        """
        assert self.frames_meta is not None, \
            "frames_meta has no values yet"
        return self.frames_meta

    def get_frames_json(self):
        """
        Checks if metadata is assigned and if so returns it
        :return dict frames_json: Non-required (variable) metadata for
            each frame
        """
        assert self.frames_json is not None, \
            "frames_json has no values yet"
        return self.frames_json

    def upload_stack(self, file_names, im_stack):
        """
        Upload files to S3
        :param list of strs file_names: File names
        :param np.array im_stack: Image stack corresponding to file names
        """
        try:
            # Upload stack frames to S3
            self.data_uploader.upload_frames(
                file_names=file_names,
                im_stack=im_stack,
            )
        except AssertionError as e:
            print("S3 upload failed: {}".format(e))
            raise

    def _get_imname(self, meta_row):
        """
        Generate image (frame) name given frame metadata and file format.

        :param dict meta_row: Metadata for frame, must contain frame indices
        :return str imname: Image file name
        """
        return "im_c" + str(meta_row["channel_idx"]).zfill(self.int2str_len) + \
            "_z" + str(meta_row["slice_idx"]).zfill(self.int2str_len) + \
            "_t" + str(meta_row["time_idx"]).zfill(self.int2str_len) + \
            "_p" + str(meta_row["pos_idx"]).zfill(self.int2str_len) + \
            self.file_format

    def set_global_meta(self, nbr_frames):
        """
        Add values to global_meta given all of the metadata for all the frames.

        :param int nbr_frames: Total number of frames
        """
        assert not isinstance(self.frame_shape, type(None)),\
            "Frame shape is empty"

        self.global_meta = {
            "s3_dir": self.s3_dir,
            "nbr_frames": nbr_frames,
            "im_height": self.frame_shape[0],
            "im_width": self.frame_shape[1],
            "im_colors": self.im_colors,
            "bit_depth": self.bit_depth,
            "nbr_slices": len(np.unique(self.frames_meta["slice_idx"])),
            "nbr_channels": len(np.unique(self.frames_meta["channel_idx"])),
            "nbr_timepoints": len(np.unique(self.frames_meta["time_idx"])),
            "nbr_positions": len(np.unique(self.frames_meta["pos_idx"])),
        }
        meta_utils.validate_global_meta(self.global_meta)

    def upload_data(self, file_names):
        try:
            # Upload stack frames to S3
            self.data_uploader.upload_frames(
                file_names=file_names,
                im_stack=self.im_stack,
            )
        except AssertionError as e:
            print("Project already on S3, moving on to DB entry")
            print(e)

    @abstractmethod
    def set_frame_info(self):
        """
        Sets frame shape, im_colors and bit_depth for the class
        Must be called once before setting global metadata
        Sets the following attributes:

        :param list of ints frame_shape: Shape of frame (2D image)
        :param int im_colors: 1/3 if image is grayscale/RGB
        :param str bit_depth: Bit depth (uint8 and uint16 supported)
        """
        raise NotImplementedError

    @abstractmethod
    def get_frames_and_metadata(self):
        """
        Function that will extract all necessary image and meta- data
        for uploading a dataset as Frames.
        """
        raise NotImplementedError
