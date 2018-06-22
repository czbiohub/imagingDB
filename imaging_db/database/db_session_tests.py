import nose.tools
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


# TODO: Test session by some type of mocking perhaps
