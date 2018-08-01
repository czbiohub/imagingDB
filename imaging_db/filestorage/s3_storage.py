import boto3
import numpy as np

import imaging_db.utils.image_utils as im_utils
from tqdm import tqdm


class DataStorage:
    """Class for handling data uploads to S3"""

    def __init__(self, folder_name):
        """
        Initialize S3 client and check that ID doesn't exist already

        :param str folder_name: folder name in S3 bucket
        """
        self.bucket_name = "czbiohub-imaging"
        self.s3_client = boto3.client('s3')
        self.folder_name = folder_name

    def assert_unique_id(self):
        """
        Makes sure folder doesn't already exist on S3

        :raise AssertionError: if folder exists
        """
        response = self.s3_client.list_objects_v2(Bucket=self.bucket_name,
                                                  Prefix=self.folder_name)
        assert response['KeyCount'] == 0, \
            "Key already exists on S3: {}".format(self.folder_name)

    def upload_frames(self, file_names, im_stack, file_format=".png"):
        """
        Upload all frames to S3

        :param list of str file_names: image file names
        :param np.array im_stack: all 2D frames from file converted to stack
        :param str file_format: file format for slices on S3
        """
        # Make sure number of file names matches stack shape
        assert len(file_names) == im_stack.shape[-1], \
            "Number of file names {} doesn't match slices {}".format(
                len(file_names), im_stack.shape[-1])

        for i, file_name in enumerate(file_names):
            key = "/".join([self.folder_name, file_name])
            # Make sure image doesn't already exist
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=key,
            )
            try:
                assert response['KeyCount'] == 0, \
                    "Key already exists on S3: {}".format(key)
                # Serialize image
                im_bytes = im_utils.serialize_im(
                    im=im_stack[..., i],
                    file_format=file_format,
                )
                # Upload slice to S3
                print("Writing to S3", key)
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=im_bytes,
                )
            except Exception as e:
                print("Key already exists, continuing", e)

    def upload_file(self, file_name):
        """
        Upload a single file to S3 without reading its contents

        :param str file_name: full path to file
        """
        # ID should be unique, make sure it doesn't already exist
        self.assert_unique_id()

        file_no_path = file_name.split("/")[-1]
        key = "/".join([self.folder_name, file_no_path])
        self.s3_client.upload_file(
            file_name,
            self.bucket_name,
            key,
        )

    def fetch_im(self, file_name):
        """
        Given file name, fetch image

        :param str file_name: slice file name
        :return np.array im: 2D image
        """

        key = "/".join([self.folder_name, file_name])
        byte_str = self.s3_client.get_object(
            Bucket=self.bucket_name,
            Key=key,
        )['Body'].read()
        # Construct an array from the bytes and decode image
        im = im_utils.deserialize_im(byte_str)
        return im

    def fetch_im_stack(self, file_names, stack_shape, bit_depth, verbose=False):
        """
        Given file names, fetch images and return image stack

        :param list of str file_names: slice file names
        :param tuple stack_shape: shape of image stack
        :return np.array im_stack: stack of 2D images
        """
        im_stack = np.zeros(stack_shape, dtype=bit_depth)

        if verbose:
            for im_nbr in tqdm(range(len(file_names))):
                key = "/".join([self.folder_name, file_names[im_nbr]])
                byte_str = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )['Body'].read()
                # Construct an array from the bytes and decode image
                im = im_utils.deserialize_im(byte_str)
                im_stack[..., im_nbr] = np.atleast_3d(im)

        else:
            for im_nbr in range(len(file_names)):
                key = "/".join([self.folder_name, file_names[im_nbr]])
                byte_str = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )['Body'].read()
                # Construct an array from the bytes and decode image
                im = im_utils.deserialize_im(byte_str)
                im_stack[..., im_nbr] = np.atleast_3d(im)

        return im_stack

    def download_file(self, file_name, dest_path):
        """
        Download a single file to S3 without reading its contents

        :param str file_name: full path to file
        :param str dest_path: full path to destination
        """
        key = "/".join([self.folder_name, file_name])
        self.s3_client.download_file(
            self.bucket_name,
            key,
            dest_path,
        )
