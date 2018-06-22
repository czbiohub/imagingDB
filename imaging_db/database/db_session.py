from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import imaging_db.metadata.json_validator as json_validator


def json_to_uri(credentials_json):
    """
    Convert JSON object containing database credentials into a string
    formatted for SQLAlchemy's create_engine, e.g.:
    drivername://user:password@host:port/dbname
    It is assumed that the json has already been validated against
    json_validator.CREDENTIALS_SCHEMA

    :param json credentials_json: JSON object containing database credentials
    :return str credentials_str: URI for connecting to the database
    """
    return \
        credentials_json["drivername"] + "://" + \
        credentials_json["username"] + ":" + \
        credentials_json["password"] + "@" + \
        credentials_json["host"] + ":" + \
        str(credentials_json["port"]) + "/" + \
        credentials_json["dbname"]


def start_session(credentials_filename, echo_sql=False):
    """
    Given a json file name containing database login credentials,
    start a SQLAlchemy session for database queries

    :param str credentials_filename: json file containing login credentials
    :param bool echo_sql: if True, sends all generated SQL to stout
    :return Session: SQLAlchemy session
    """
    # Read and validate json
    credentials_json = json_validator.read_json_file(
        json_filename=credentials_filename,
        schema_name="CREDENTIALS_SCHEMA")
    # Convert json to string compatible with engine
    credentials_str = json_to_uri(credentials_json)
    # Create SQLAlchemy engine, connect and return session
    engine = create_engine(credentials_str, echo=echo_sql)
    # Declarative base
    Base = declarative_base(engine)
    metadata = Base.metadata
    # create a configured "Session" class
    Session = sessionmaker(bind=engine)
    # return session handle
    return Session()
