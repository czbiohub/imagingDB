import nose.tools
import os
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import imaging_db.database.db_operations as db_ops
import imaging_db.metadata.json_operations as json_ops
import imaging_db.utils.db_utils as db_utils

class TestDBTransactions(unittest.TestCase):
    """
    These tests require that you run a postgres Docker container
    which you can connect to and create a temporary database on.
    You can create such a database using the command:
    make start-local-db
    and stop it using:
    make stop-local-db
    """

    def setUp(self):
        # Credentials URI which can be used to connect
        # to postgres Docker container
        self.credentials_str = 'postgres://username:password@localhost:5433/test'
        # Create database connection
        self.Session = sessionmaker()
        self.engine = create_engine(self.credentials_str)
        # connect to the database
        self.connection = self.engine.connect()
        # begin a non-ORM transaction
        self.transaction = self.connection.begin()
        # bind an individual Session to the connection
        self.session = self.Session(bind=self.connection)
        # start the session in a SAVEPOINT
        self.session.begin_nested()

        db_ops.Base.metadata.create_all(self.connection)

        self.dataset_serial = 'TEST-2005-10-09-20-00-00-0001'
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
        self.s3_dir = 'testing/TEST-2005-10-09-20-00-00-0001'
        self.sha256 = 'aaabbbccc'

    def tearDown(self):
        # Roll back the top level transaction and disconnect from the database
        self.session.close()
        # rollback - everything that happened with the
        # Session above (including calls to commit())
        # is rolled back.
        self.transaction.rollback()
        # return connection to the Engine
        self.connection.close()

    def test_connection(self):
        db_ops.test_connection(self.session)

    def test_assert_unique_id(self):
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=self.dataset_serial,
        )
        db_inst.assert_unique_id(self.session)

    def test_insert(self):
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=self.dataset_serial,
        )
        db_inst.insert_file(
            session=self.session,
            description=self.description,
            s3_dir=self.s3_dir,
            global_json_meta=self.global_json_meta,
            microscope=self.microscope,
            sha256=self.sha256,
        )
        # Assert insert by query
        datasets = self.session.query(db_ops.DataSet)
        self.assertEqual(datasets.count(), 1)
        dataset = datasets[0]
        self.assertEqual(dataset.id, 1)
        self.assertEqual(dataset.dataset_serial, self.dataset_serial)
        self.assertEqual(dataset.description, self.description)
        date_time = dataset.date_time
        self.assertEqual(date_time.year, 2005)
        self.assertEqual(date_time.month, 10)
        self.assertEqual(date_time.day, 9)
        self.assertEqual(dataset.microscope, self.microscope)
        self.assertEqual(dataset.description, self.description)
