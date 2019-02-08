import cv2
import numpy as np


def serialize_im(im, file_format='.png'):
    """
    Convert image to bytes object for transfer to storage

    :param np.array im: 2D image
    :param str file_format: Must be OpenCV file format, e.g. '.png' or '.tif'
    :return: str im_encoded: serialized image
    """
    # Get rid of any singleton dimensions
    im = np.squeeze(im)
    res, im_encoded = cv2.imencode(file_format, im)
    return im_encoded.tostring()


def deserialize_im(byte_string):
    """
    Deserializes image

    :param str byte_string: E.g. from getting an S3 object
    :return np.array im: 2D image
    """
    im_encoded = np.fromstring(byte_string, dtype='uint8')
    return cv2.imdecode(im_encoded, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_ANYCOLOR)
