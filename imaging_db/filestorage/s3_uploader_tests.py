import boto3
import cv2
from moto import mock_s3
import nose.tools
import numpy as np
import numpy.testing
import os
from testfixtures import TempDirectory

import imaging_db.filestorage.s3_uploader as s3_uploader
import imaging_db.utils.image_utils as im_utils


@mock_s3
def test_upload_data():
    bucket_name = 'czbiohub-imaging'
    conn = boto3.resource('s3', region_name='us-west-2')
    # Create the bucket in Moto's 'virtual' AWS account
    conn.create_bucket(Bucket=bucket_name)

    id_str = "ISP-2018-06-08-15-45-00-0001"
    folder_name = "raw_slices"
    data_uploader = s3_uploader.DataUploader(id_str, folder_name)
    im_stack = np.ones((10, 15, 2), np.uint16) * 3000
    im_stack[0:5, 2:4, 0] = 42
    im_stack[3:7, 12:14, 1] = 10000
    file_names = ["im1.png", "im2.png"]
    data_uploader.upload_slices(file_names, im_stack)
    # Get images and validate that the contents are unchanged
    for im_nbr in range(len(file_names)):
        key = "/".join([folder_name, id_str, file_names[im_nbr]])
        byte_string = conn.Object(bucket_name, key).get()['Body'].read()
        # Construct an array from the bytes and decode image
        im = im_utils.deserialize_im(byte_string)
        # Assert that contents are the same
        nose.tools.assert_equal(im.dtype, np.uint16)
        numpy.testing.assert_array_equal(im, im_stack[..., im_nbr])


@mock_s3
def test_upload_color_data():
    bucket_name = 'czbiohub-imaging'
    conn = boto3.resource('s3', region_name='us-west-2')
    # Ceate the bucket in Moto's 'virtual' AWS account
    conn.create_bucket(Bucket=bucket_name)

    id_str = "ISP-2018-06-08-15-45-00-0001"
    folder_name = "raw_slices"
    data_uploader = s3_uploader.DataUploader(id_str, folder_name)
    im_stack = np.ones((10, 15, 3, 2), np.uint16) * 3000
    im_stack[0:5, 2:4, :, 0] = 42
    im_stack[3:7, 12:14, :, 1] = 10000
    # Expected color image shape
    expected_shape = im_stack[..., 0].shape

    file_names = ["im1.png", "im2.png"]
    data_uploader.upload_slices(file_names, im_stack)
    # Get images and validate that the contents are unchanged
    for im_nbr in range(len(file_names)):
        key = "/".join([folder_name, id_str, file_names[im_nbr]])
        byte_string = conn.Object(bucket_name, key).get()['Body'].read()
        # Construct an array from the bytes and decode image
        im = im_utils.deserialize_im(byte_string)
        # Assert that contents are the same
        nose.tools.assert_equal(im.shape, expected_shape)
        nose.tools.assert_equal(im.dtype, np.uint16)
        numpy.testing.assert_array_equal(im, im_stack[..., im_nbr])


@mock_s3
def test_upload_file():
    bucket_name = 'czbiohub-imaging'
    conn = boto3.resource('s3', region_name='us-west-2')
    # Create the bucket in Moto's 'virtual' AWS account
    conn.create_bucket(Bucket=bucket_name)

    id_str = "ML-2018-06-08-15-45-00-0001"
    folder_name = "raw_files"

    with TempDirectory() as tempdir:
        im = np.zeros((15, 12), dtype=np.uint16)
        im[0:5, 3:7] = 5000
        res, im_encoded = cv2.imencode('.png', im)
        im_encoded = im_encoded.tostring()
        im_name = 'im_0.png'
        tempdir.write(im_name, im_encoded)
        # Upload file
        file_path = os.path.join(tempdir.path, im_name)
        data_uploader = s3_uploader.DataUploader(id_str, folder_name)
        data_uploader.upload_file(file_name=file_path)
        key = "/".join([folder_name, id_str, im_name])
        body = conn.Object(bucket_name, key).get()['Body'].read()
        # Construct an array from the bytes and decode image
        im_encoded = np.fromstring(body, dtype='uint8')
        im_out = cv2.imdecode(im_encoded, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_ANYCOLOR)
        # Assert that contents are the same
        nose.tools.assert_equal(im_out.dtype, np.uint16)
        numpy.testing.assert_array_equal(im_out, im)


