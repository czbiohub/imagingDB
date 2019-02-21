import nose.tools

import imaging_db.utils.cli_utils as cli_utils


def test_validate_id():
    id_str = "ISP-2018-06-08-15-45-00-0001"
    cli_utils.validate_id(id_str)


@nose.tools.raises(AssertionError)
def test_too_short():
    id_str = "ISP-2018-06-08-15-45-0001"
    cli_utils.validate_id(id_str)


@nose.tools.raises(AssertionError)
def test_invalid_month():
    id_str = "ISP-2018-50-08-15-45-00-0001"
    cli_utils.validate_id(id_str)


@nose.tools.raises(AssertionError)
def test_invalid_year():
    id_str = "ISP-666-12-08-15-45-00-0001"
    cli_utils.validate_id(id_str)


@nose.tools.raises(AssertionError)
def test_invalid_serial():
    id_str = "ISP-666-12-08-15-45-00-A"
    cli_utils.validate_id(id_str)


@nose.tools.raises(AssertionError)
def test_underscore():
    id_str = "ISP_666-12-08-15-45-00-0001"
    cli_utils.validate_id(id_str)