import boto3

import imaging_db.utils.image_utils as im_utils


class DataUploader:
    """Class for handling data uploads to S3"""

    def __init__(self, project_serial, folder_name, file_format=".png"):
        """
        Initialize S3 client and check that ID doesn't exist already

        :param project_serial: project serial ID
        :param folder_name: folder name in S3 bucket, raw_files or raw_slices
        """
        self.bucket_name = "czbiohub-imaging"
        self.s3_client = boto3.client('s3')
        self.project_serial = project_serial
        self.folder_name = folder_name
        self.file_format = file_format
        # ID should be unique, make sure it doesn't already exist
        self.assert_unique_id()

    def assert_unique_id(self):
        """
        Makes sure folder doesn't already exist on S3

        :raise AssertionError: if folder exists
        """
        key = "/".join([self.folder_name, self.project_serial])
        response = self.s3_client.list_objects_v2(Bucket=self.bucket_name,
                                                  Prefix=key)
        assert response['KeyCount'] == 0, \
            "Key already exists on S3: {}".format(key)


    def upload_slices(self, file_names, im_stack):
        """
        Upload all slices to S3

        :param list of str file_names: image file names
        :param np.array im_stack: all 2D frames from file converted to stack
        """
        assert len(file_names) == im_stack.shape[-1], \
            "Number of file names {} doesn't match slices {}".format(
                len(file_names), im_stack.shape[-1])

        for i, file_name in enumerate(file_names):
            key = "/".join([self.folder_name, self.project_serial, file_name])
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=key,
            )
            assert response['KeyCount'] == 0, \
                "Key already exists on S3: {}".format(key)
            # Serialize image
            im_bytes = im_utils.serialize_im(
                im=im_stack[..., i],
                file_format=self.file_format
            )
            # Upload slice to S3
            print("Writing to S3", key)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=im_bytes,
            )

    def upload_file(self, file_name):
        """
        Upload a single file to S3 without reading its contents

        :param str file_name: full path to file
        """
        file_no_path = file_name.split("/")[-1]
        key = "/".join([self.folder_name, self.project_serial, file_no_path])
        self.s3_client.upload_file(
            file_name,
            self.bucket_name,
            key,
        )
