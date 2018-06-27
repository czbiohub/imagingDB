from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from imaging_db.database.base import Base
# from imaging_db.database.image_file import ImageFile
# from imaging_db.database.image_slices import ImageSlices
# from imaging_db.database.microscopy_file import MicroscopyFile
from imaging_db.database.project import Project
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
    # Try without port # str(credentials_json["port"]) + "/" + \
    return \
        credentials_json["drivername"] + "://" + \
        credentials_json["username"] + ":" + \
        credentials_json["password"] + "@" + \
        credentials_json["host"] + "/" + \
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
    # create a configured "Session" class
    Session = sessionmaker(bind=engine)
    # Generate database schema
    Base.metadata.create_all(engine)
    # return session handle
    return Session()


def insert_slices(credentials_filename,
                  project_serial,
                  file_format,
                  slice_meta,
                  slice_json_meta,
                  global_meta,
                  global_json_meta):
    # Create session
    session = start_session(credentials_filename, echo_sql=True)
    # First insert project ID in the main Project table with sliced=True
    project_temp = Project(project_serial, file_format, True)
    session.add(project_temp)
    session.commit()
    session.close()


