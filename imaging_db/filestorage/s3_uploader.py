import boto3
import cv2


class DataUploader:
    """Class for handling data uploads to S3"""

    def __init__(self, id_str, folder_name, file_format=".png"):
        """
        Initialize S3 client and check that ID doesn't exist already

        :param id_str:
        :param folder_name:
        :param file_format:
        """
        self.bucket_name = "czbiohub-imaging"
        self.s3_client = boto3.client('s3')
        self.id_str = id_str
        self.folder_name = folder_name
        # ID should be unique, make sure it doesn't already exist
        self.assert_unique_id()
        self.file_format = file_format

    def assert_unique_id(self):
        """
        Makes sure folder doesn't already exist on S3

        :raise AssertionError: if folder exists
        """
        key = "/".join([self.folder_name, self.id_str])
        response = self.s3_client.list_objects_v2(Bucket=self.bucket_name,
                                                  Prefix=key)
        assert response['KeyCount'] == 0, \
            "Key already exists on S3: {}".format(key)

    def serialize_im(self, im):
        """
        Convert image to bytes object for transfer to storage

        :param im:
        :return:
        """
        res, im_encoded = cv2.imencode(self.file_format, im)
        return im_encoded.tostring()

    def upload_slices(self, file_names, im_stack):
        """
        Upload all slices to S3

        :param list of str file_names: image file names
        :param np.array im_stack:

        """
        assert len(file_names) == im_stack.shape[2], \
            "Number of file names {} doesn't match slices {}".format(
                len(file_names), im_stack.shape[2])

        for i, file_name in enumerate(file_names):
            key = "/".join([self.folder_name, self.id_str, file_name])
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name,
                                                      Prefix=key)
            assert response['KeyCount'] == 0, \
                "Key already exists on S3: {}".format(key)
            # Serialize image
            im_bytes = self.serialize_im(im_stack[..., i])
            # Upload slice to S3
            print("Writing to S3", key)
            self.s3_client.put_object(Bucket=self.bucket_name,
                                      Key=key,
                                      Body=im_bytes)
