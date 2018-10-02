import boto3
import numpy as np

import imaging_db.utils.image_utils as im_utils
from tqdm import tqdm
from tqdm._utils import _term_move_up


class DataStorage:
    """Class for handling data uploads to S3"""

    def __init__(self, s3_dir):
        """
        Initialize S3 client and check that ID doesn't exist already

        :param str s3_dir: folder name in S3 bucket
        """
        self.bucket_name = "czbiohub-imaging"
        self.s3_client = boto3.client('s3')
        self.s3_dir = s3_dir

    def assert_unique_id(self):
        """
        Makes sure folder doesn't already exist on S3

        :raise AssertionError: if folder exists
        """
        response = self.s3_client.list_objects_v2(Bucket=self.bucket_name,
                                                  Prefix=self.s3_dir)
        assert response['KeyCount'] == 0, \
            "Key already exists on S3: {}".format(self.s3_dir)

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

        # Create the progress bar for the file_names
        slice_prog_bar = tqdm(enumerate(file_names), total=len(file_names), desc='Slice')
        prefix = _term_move_up() + '\r'

        for i, file_name in slice_prog_bar:
            # Clear the terminal message
            slice_prog_bar.write(prefix+'')

            key = "/".join([self.s3_dir, file_name])

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
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=im_bytes,
                )
            except Exception as e:
                slice_prog_bar.write(prefix+"Key already exists, continuing")

    def upload_file(self, file_name):
        """
        Upload a single file to S3 without reading its contents

        :param str file_name: full path to file
        """
        # ID should be unique, make sure it doesn't already exist
        self.assert_unique_id()

        file_no_path = file_name.split("/")[-1]
        key = "/".join([self.s3_dir, file_no_path])
        self.s3_client.upload_file(
            file_name,
            self.bucket_name,
            key,
        )

    def get_im(self, file_name):
        """
        Given file name, fetch 2D image (frame)

        :param str file_name: slice file name
        :return np.array im: 2D image
        """

        key = "/".join([self.s3_dir, file_name])
        byte_str = self.s3_client.get_object(
            Bucket=self.bucket_name,
            Key=key,
        )['Body'].read()
        # Construct an array from the bytes and decode image
        return im_utils.deserialize_im(byte_str)

    def get_stack(self, file_names, stack_shape, bit_depth, verbose=False):
        """
        Given file names, fetch images and return image stack.
        This function assumes that the frames in the list are contiguous,
        i.e. the length of the file name is will be the last dimension of
        the image stack.

        :param list of str file_names: Frame file names
        :param tuple stack_shape: Shape of image stack
        :param dtype bit_depth: Bit depth
        :return np.array im_stack: Stack of 2D images
        """
        im_stack = np.zeros(stack_shape, dtype=bit_depth)

        if verbose:
            for im_nbr in tqdm(range(len(file_names))):
                im = self.get_im(file_names[im_nbr])
                im_stack[..., im_nbr] = np.atleast_3d(im)
        else:
            for im_nbr in range(len(file_names)):
                im = self.get_im(file_names[im_nbr])
                im_stack[..., im_nbr] = np.atleast_3d(im)
        return im_stack

    def get_stack_from_meta(self, global_meta, frames_meta):
        """
        Given global metadata, instantiate an image stack. The default order
        of frames is:
         X Y [gray/RGB] Z C T
         Image height, width, colors (1 or 3), the z depth, channel, timepoint

        Retrieve all frames from local metadata and return image stack.
        Ones in stack shape indicates singleton dimensions.
        The stack is then squeezed to remove singleton dimensions, and a string
        is returned to indicate which dimensions are kept and in what order.
        TODO: Add option to customize image order

        :param dict global_meta: Global metadata for dataset
        :param dataframe frames_meta: Local metadata and paths for each file
        :return np.array im_stack: Stack of 2D images
        :return str dim_str: String indicating order of stack dimensions
            Possible values: XYGZCTP
            X=im_height, Y=im_width, G=[gray/RGB] (1 or 3),
            Z=slice_idx, C=channel_idx, T=time_idx, P=pos_idx
        """
        stack_shape = (
            global_meta["im_height"],
            global_meta["im_width"],
            global_meta["im_colors"],
            global_meta["nbr_slices"],
            global_meta["nbr_channels"],
            global_meta["nbr_timepoints"],
            global_meta["nbr_positions"],
        )
        im_stack = np.zeros(stack_shape, global_meta["bit_depth"])
        # Metadata don't have to be indexed starting at 0 or continuous
        unique_slice = np.unique(frames_meta["slice_idx"])
        unique_channel = np.unique(frames_meta["channel_idx"])
        unique_time = np.unique(frames_meta["time_idx"])
        unique_pos = np.unique(frames_meta["pos_idx"])

        # Fill the image stack given dimensions
        for im_nbr, row in frames_meta.iterrows():
            im = self.get_im(row.file_name)
            im_stack[:, :, :,
                     np.where(unique_slice == row.slice_idx)[0][0],
                     np.where(unique_channel == row.channel_idx)[0][0],
                     np.where(unique_time == row.time_idx)[0][0],
                     np.where(unique_pos == row.pos_idx)[0][0],
            ] = np.atleast_3d(im)
        # Return squeezed stack and string that indicates dimension order
        dim_order = "XYGZCTP"
        single_dims = np.where(np.asarray(stack_shape) == 1)[0]
        dim_str = ''.join(x for x in dim_order
                          if dim_order.index(x) not in single_dims)
        return np.squeeze(im_stack), dim_str

    def download_file(self, file_name, dest_path):
        """
        Download a single file to S3 without reading its contents

        :param str file_name: full path to file
        :param str dest_path: full path to destination
        """
        key = "/".join([self.s3_dir, file_name])
        self.s3_client.download_file(
            self.bucket_name,
            key,
            dest_path,
        )
