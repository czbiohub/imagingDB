import nose.tools
import os
import unittest

import imaging_db.database.db_session as db_session


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

    credentials_str = db_session.json_to_uri(credentials_json)
    nose.tools.assert_equal(credentials_str, expected_str)


class DBSession(unittest.TestCase):
    """
    These tests require that you run a postgres Docker container
    which you can connect to and create a temporary database on.
    You can create such a database using the command:
    docker run --name testdb
    -p 5432:5432
    -e POSTGRES_USER='username'
    -e POSTGRES_PASSWORD='password'
    -d postgres:9.6.10-alpine
    """

    def setUp(self):

        # Get path to example DB credentials file which can be used to connect
        # to postgres Docker container
        dir_name = os.path.dirname(__file__)
        self.cred_path = os.path.realpath(
            os.path.join(dir_name, '../../db_credentials.json'),
        )
        self.dataset_serial = 'TEST-2005-10-09-20-00-00-0001'
        db_inst = db_session.DatabaseOperations(
            credentials_filename=self.cred_path,
            dataset_serial=self.dataset_serial,
        )
        self.global_meta = {
            "s3_dir": "dir_name",
            "nbr_frames": 5,
            "im_height": 256,
            "im_width": 512,
            "im_colors": 1,
            "bit_depth": "uint16",
            "nbr_slices": 6,
            "nbr_channels": 7,
            "nbr_timepoints": 8,
            "nbr_positions": 9,
        }
        self.global_json_meta = {'status': 'test'}
        self.microscope = 'test_microscope'
        self.description = 'This is a test'
        db_inst.insert_file(
            description=self.description,
            s3_dir='dir_name',
            global_json_meta=self.global_json_meta,
            microscope=self.microscope,
        )
        print('after insert')

    @nose.tools.raises(AssertionError)
    def test_assert_not_unique_id(self):
        test_inst = db_session.DatabaseOperations(
            credentials_filename=self.cred_path,
            dataset_serial='TEST-2005-10-09-20-00-00-0001',
        )
        # test_inst.assert_unique_id()
