import boto3
import cv2
from moto import mock_s3
import nose.tools
import numpy as np
import numpy.testing

import imaging_db.filestorage.s3_uploader as s3_uploader


@mock_s3
def test_upload_data():
    bucket_name = 'czbiohub-imaging'
    conn = boto3.resource('s3', region_name='us-west-2')
    # Ceate the bucket in Moto's 'virtual' AWS account
    conn.create_bucket(Bucket=bucket_name)

    id_str = "ISP-2018-06-08-15-45-00-0001"
    folder_name = "raw_slices"
    data_uploader = s3_uploader.DataUploader(id_str, folder_name)
    im_stack = np.ones((10, 15, 2), np.uint16) * 3000
    im_stack[0:5, 2:4, 0] = 42
    im_stack[3:7, 12:14, 1] = 10000
    file_names = ["im1.png", "im2.png"]
    data_uploader.upload_slices(file_names, im_stack)
    # Get images and validate that the contents arfe unchanged
    for im_nbr in range(len(file_names)):
        key = "/".join([folder_name, id_str, file_names[im_nbr]])
        body = conn.Object(bucket_name, key).get()['Body'].read()
        # Construct an array from the bytes and decode image
        im_encoded = np.fromstring(body, dtype='uint8')
        im = cv2.imdecode(im_encoded, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_ANYCOLOR)
        # Assert that contents are the same
        nose.tools.assert_equal(im.dtype, np.uint16)
        numpy.testing.assert_array_equal(im, im_stack[..., im_nbr])


