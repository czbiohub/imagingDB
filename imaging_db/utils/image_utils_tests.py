import nose.tools
import numpy as np
import numpy.testing

import imaging_db.utils.image_utils as im_utils


def test_serialize_deserialize():
    im = np.random.rand(10, 15) * 255
    im = im.astype(np.uint16)
    im_serial = im_utils.serialize_im(im)
    im_deserial = im_utils.deserialize_im(im_serial)
    numpy.testing.assert_array_equal(im, im_deserial)


@nose.tools.raises(TypeError)
def test_serialize_wrong_format():
    im = np.random.rand(10, 15) * 255
    im_utils.serialize_im(im, '.npy')