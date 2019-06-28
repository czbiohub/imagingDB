import nose.tools
import os

import imaging_db.utils.db_utils as db_utils


def test_json_to_uri():
    credentials_json = {
        "drivername": "postgres",
        "username": "user",
        "password": "pwd",
        "host": "db_host",
        "port": 666,
        "dbname": "db_name"
    }
    expected_str = "postgres://user:pwd@db_host:666/db_name"
    credentials_str = db_utils.json_to_uri(credentials_json)
    nose.tools.assert_equal(credentials_str, expected_str)


def test_get_connection_str():
    credentials_filename = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'db_credentials.json',
        ),
    )
    credentials_str = db_utils.get_connection_str(credentials_filename)
    expected_str = "postgres://imaging_user:imaging_passwd@localhost:5433/imaging_test"
    nose.tools.assert_equal(credentials_str, expected_str)
