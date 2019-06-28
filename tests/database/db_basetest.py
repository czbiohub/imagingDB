import os
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import imaging_db.database.db_operations as db_ops
import imaging_db.utils.db_utils as db_utils


class DBBaseTest(unittest.TestCase):
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
        credentials_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'db_credentials.json',
        )
        self.credentials_str = db_utils.get_connection_str(credentials_path)
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

    def tearDown(self):
        # Roll back the top level transaction and disconnect from the database
        self.session.close()
        # rollback - everything that happened with the
        # Session above (including calls to commit())
        # is rolled back.
        self.transaction.rollback()
        # return connection to the Engine
        self.connection.close()
