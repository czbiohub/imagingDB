from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from imaging_db.database.base import Base
from imaging_db.database.file_global import FileGlobal
from imaging_db.database.sliced_global import SlicedGlobal
from imaging_db.database.slices import Slices
from imaging_db.database.project import Project
import imaging_db.metadata.json_validator as json_validator


@contextmanager
def session_scope(credentials_filename, echo_sql=False):
    """
    Provide a transactional scope around a series of
    database operations.

    :param str credentials_filename: JSON file containing database credentials
    :return SQLAlchemy session
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
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        print(e)
        session.rollback()
        raise
    finally:
        session.close()


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


def test_connection(credentials_filename):
    try:
        with session_scope(credentials_filename) as session:
            session.execute('SELECT 1')
    except Exception as e:
        print("Can't connect to database", e)
        raise


def insert_slices(credentials_filename,
                  project_serial,
                  description,
                  folder_name,
                  slice_meta,
                  slice_json_meta,
                  global_meta,
                  global_json_meta):
    """
    Insert global and local information from file that has been
    converted to image slices with corresponding metadata
    :param str credentials_filename: JSON file containing DB credentials
    :param str project_serial: Unique identifier for file
    :param str description: Short description of file
    :param str folder_name: Folder in S3 bucket where data is stored
    :param dataframe slice_meta: Dataframe containing mandatory slice fields
    :param json slice_json_meta: json object with arbitrary local metadata
    :param dict global_meta: Required global metadata fields
    :param json global_json_meta: Arbitrary global metadata
    """
    # Create session
    with session_scope(credentials_filename) as session:
        # Check if ID already exist
        projs = session.query(Project) \
            .filter(Project.project_serial == project_serial).all()
        assert len(projs) == 0, \
            "Project {} already exists in database".format(project_serial)
        # Insert project ID in the main Project table with sliced=True
        new_project = Project(
            project_serial=project_serial,
            description=description,
            sliced=True)
        # Add global slice information
        new_sliced_global = SlicedGlobal(
            nbr_frames=global_meta["nbr_frames"],
            im_width=global_meta["im_width"],
            im_height=global_meta["im_height"],
            bit_depth=global_meta["bit_depth"],
            folder_name = folder_name,
            metadata_json=global_json_meta,
            project=new_project,
        )
        for i in range(slice_meta.shape[0]):
            # Insert all slices here then add them to new sliced global
            temp_slice = Slices(
                channel_idx=slice_meta.loc[i, "ChannelIndex"],
                slice_idx=slice_meta.loc[i, "Slice"],
                frame_idx=slice_meta.loc[i, "FrameIndex"],
                exposure_ms=slice_meta.loc[i, "Exposure-ms"],
                channel_name=slice_meta.loc[i, "ChannelName"],
                file_name=slice_meta.loc[i, "FileName"],
                metadata_json=slice_json_meta[i],
                sliced_global=new_sliced_global,
            )
            session.add(temp_slice)

        session.add(new_project)
        session.add(new_sliced_global)


def insert_file(credentials_filename,
                project_serial,
                description,
                folder_name,
                global_json_meta):
    """
    Upload file as is without slicing it or extracting metadata
    :param str credentials_filename: JSON file containing DB credentials
    :param str project_serial: Unique identifier for file
    :param str description: Short description of file
    :param str folder_name: Folder in S3 bucket where data is stored
    :param global_json_meta: Arbitrary metadata fields for file
    """
    # Create session
    with session_scope(credentials_filename) as session:
        # Check if ID already exist
        projs = session.query(Project) \
            .filter(Project.project_serial == project_serial).all()
        assert len(projs) == 0, \
            "Project {} already exists in database".format(project_serial)
        # First insert project ID in the main Project table with sliced=True
        new_project = Project(
            project_serial=project_serial,
            description=description,
            sliced=False)
        # Add s3 location
        new_file_global = FileGlobal(
            folder_name=folder_name,
            metadata_json=global_json_meta,
            project=new_project,
        )
        session.add(new_project)
        session.add(new_file_global)
