from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from imaging_db.database.base import Base
from imaging_db.database.file_global import FileGlobal
from imaging_db.database.sliced_global import SlicedGlobal
from imaging_db.database.slices import slices
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
    # create a configured "Session" class
    Session = sessionmaker(bind=engine)
    # Generate database schema
    Base.metadata.create_all(engine)
    # return session handle
    return Session()


def test_connection(credentials_filename):
    try:
        session = start_session(credentials_filename)
        session.execute('SELECT 1')
    except Exception as e:
        print("Can't connect to database", e)
        raise


def insert_slices(credentials_filename,
                  project_serial,
                  description,
                  slice_meta,
                  slice_json_meta,
                  global_meta,
                  global_json_meta):
    # Create session
    session = start_session(credentials_filename, echo_sql=False)
    # First insert project ID in the main Project table with sliced=True
    new_project = Project(project_serial, description, True)
    new_sliced_global = SlicedGlobal(
        global_meta["nbr_frames"],
        global_meta["im_width"],
        global_meta["im_height"],
        global_meta["bit_depth"],
        slice_json_meta,
        new_project,
    )
    all_slices = []
    for i in range(slice_meta.shape[0]):
        # Insert all slices here then add them to new sliced global

    session.add(new_project)
    session.commit()
    session.close()


