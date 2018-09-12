from contextlib import contextmanager
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from imaging_db.database.base import Base
from imaging_db.database.file_global import FileGlobal
from imaging_db.database.frames_global import FramesGlobal
from imaging_db.database.frames import Frames
from imaging_db.database.dataset import DataSet
import imaging_db.images.file_splitter as file_splitter
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


class DatabaseOperations:
    """Class handling standard input and output database operations"""

    def __init__(self,
                 credentials_filename,
                 dataset_serial):
        """
        :param str credentials_filename: full path to JSON file with
            login credentials
        :param dataset_serial:
        """
        self.credentials_filename = credentials_filename
        self.dataset_serial = dataset_serial
        self.test_connection()

    def test_connection(self):
        """
        Test that you can connect to the database

        :raise Exception: if you can't log in
        """
        try:
            with session_scope(self.credentials_filename) as session:
                session.execute('SELECT 1')
        except Exception as e:
            print("Can't connect to database", e)
            raise

    def assert_unique_id(self):
        """
        Make sure dataset is not already in database using assertion.

        :param dataset_serial: unique identifer for dataset
        """
        with session_scope(self.credentials_filename) as session:
            # Check if ID already exist
            datasets = session.query(DataSet) \
                .filter(DataSet.dataset_serial == self.dataset_serial).all()
            assert len(datasets) == 0, \
                "Dataset {} already exists in database".format(
                    self.dataset_serial,
                )

    def _get_parent(self, session, parent_dataset):
        """
        Find parent key if a parent dataset serial is given.

        :param session: database session
        :param parent_dataset: parent dataset serial
        :return int parent_key: primary key of parent dataset
        """
        parent_key = None
        if isinstance(parent_dataset, str):
            if parent_dataset.lower() == "none" or len(parent_dataset) == 0:
                parent_dataset = None
        else:
            if np.isnan(parent_dataset):
                parent_dataset = None
        if parent_dataset is not None:
            try:
                parent = session.query(DataSet) \
                    .filter(DataSet.dataset_serial == parent_dataset).one()
                parent_key = parent.id
            except Exception as e:
                print("Parent {} not found for data set {}".format(
                    parent_dataset,
                    self.dataset_serial,
                ))
                print(e)
                raise
        return parent_key

    def insert_frames(self,
                      description,
                      frames_meta,
                      frames_json_meta,
                      global_meta,
                      global_json_meta,
                      microscope,
                      parent_dataset=None):
        """
        Insert global and local information from file that has been
        converted to image slices with corresponding metadata

        :param str description: Short description of file
        :param dataframe frames_meta: Dataframe containing mandatory fields for
            each frame
        :param json frames_json_meta: json object with arbitrary local metadata
        :param dict global_meta: Required global metadata fields
        :param json global_json_meta: Arbitrary global metadata
        :param str microscope: microscope name
        :param str parent_dataset: Assign parent if not null
        """
        # Create session
        with session_scope(self.credentials_filename) as session:
            # Check if ID already exist
            datasets = session.query(DataSet) \
                .filter(DataSet.dataset_serial == self.dataset_serial).all()
            assert len(datasets) == 0, \
                "Dataset {} already exists in database".format(
                    self.dataset_serial,
                )
            # If parent dataset identifier is given, find its key and insert it
            parent_key = self._get_parent(session, parent_dataset)
            # Insert dataset ID in the main DataSet table with frames=True
            new_dataset = DataSet(
                dataset_serial=self.dataset_serial,
                description=description,
                frames=True,
                microscope=microscope,
                parent_id=parent_key,
            )
            # Add global frame information
            new_frames_global = FramesGlobal(
                folder_name=global_meta["folder_name"],
                nbr_frames=global_meta["nbr_frames"],
                im_width=global_meta["im_width"],
                im_height=global_meta["im_height"],
                nbr_slices=global_meta["nbr_slices"],
                nbr_channels=global_meta["nbr_channels"],
                nbr_timepoints=global_meta["nbr_timepoints"],
                nbr_positions=global_meta["nbr_positions"],
                im_colors=global_meta["im_colors"],
                bit_depth=global_meta["bit_depth"],

                metadata_json=global_json_meta,
                data_set=new_dataset,
            )
            for i in range(frames_meta.shape[0]):
                # Insert all frames here then add them to new frames global
                new_frame = Frames(
                    channel_idx=frames_meta.loc[i, "channel_idx"],
                    slice_idx=frames_meta.loc[i, "slice_idx"],
                    time_idx=frames_meta.loc[i, "time_idx"],
                    pos_idx=frames_meta.loc[i, "pos_idx"],
                    channel_name=frames_meta.loc[i, "channel_name"],
                    file_name=frames_meta.loc[i, "file_name"],
                    metadata_json=frames_json_meta[i],
                    frames_global=new_frames_global,
                )
                session.add(new_frame)

            session.add(new_dataset)
            session.add(new_frames_global)

    def insert_file(self,
                    description,
                    folder_name,
                    global_json_meta,
                    microscope,
                    parent_dataset=None):
        """
        Upload file as is without splitting it to frames or extracting metadata

        :param str description: Short description of file
        :param str folder_name: Folder in S3 bucket where data is stored
        :param global_json_meta: Arbitrary metadata fields for file
        :param str microscope: microscope name
        :param str parent_dataset: Assign parent if not null
        """
        # Create session
        with session_scope(self.credentials_filename) as session:
            # Check if ID already exist
            datasets = session.query(DataSet) \
                .filter(DataSet.dataset_serial == self.dataset_serial).all()
            assert len(datasets) == 0, \
                "Dataset {} already exists in database".format(
                    self.dataset_serial,
                )
            # If parent dataset identifier is given, find its key and insert it
            parent_key = self._get_parent(session, parent_dataset)
            # First insert project ID in the main Project table with frames=False
            new_dataset = DataSet(
                dataset_serial=self.dataset_serial,
                description=description,
                frames=False,
                microscope=microscope,
                parent_id=parent_key
            )
            # Add s3 location
            new_file_global = FileGlobal(
                folder_name=folder_name,
                metadata_json=global_json_meta,
                data_set=new_dataset,
            )
            session.add(new_dataset)
            session.add(new_file_global)

    def get_filenames(self):
        """
        Get S3 folder name and all file names associated with unique
        project identifier.

        :return str folder_name: Folder name containing file(s) on S3
        :return list of strs file_names: List of file names for given dataset
        """
        # Create session
        with session_scope(self.credentials_filename) as session:
            # Check if ID already exist
            dataset = session.query(DataSet) \
                   .filter(DataSet.dataset_serial == self.dataset_serial).one()

            if dataset.frames is False:
                # Get file
                file_global = session.query(FileGlobal) \
                    .join(DataSet) \
                    .filter(DataSet.dataset_serial == dataset.dataset_serial) \
                    .one()
                file_name = file_global.metadata_json["file_origin"]
                file_name = file_name.split("/")[-1]

                return file_global.folder_name, [file_name]
            else:
                # Get frames
                frames = session.query(Frames) \
                    .join(FramesGlobal) \
                    .join(DataSet) \
                    .filter(DataSet.dataset_serial == dataset.dataset_serial) \
                    .all()

                folder_name = frames[0].frames_global.folder_name
                file_names = []
                for f in frames:
                    file_names.append(f.file_name)

                return folder_name, file_names

    def _get_meta_from_frames(self, frames):
        """
        Extract global meta as well as info for each frame given
        a frames query.

        :param list of Frames frames: Frames obtained from dataset query
        :return dict global_meta: Global metadata for dataset
        :return dataframe frames_meta: Metadata for each frame
        """
        # Collect global metadata that can be used to instantiate im_stack
        global_meta = {
            "folder_name": frames[0].frames_global.folder_name,
            "nbr_frames": frames[0].frames_global.nbr_frames,
            "im_width": frames[0].frames_global.im_width,
            "im_height": frames[0].frames_global.im_height,
            "nbr_slices": frames[0].frames_global.nbr_slices,
            "nbr_channels": frames[0].frames_global.nbr_channels,
            "im_colors": frames[0].frames_global.im_colors,
            "nbr_timepoints": frames[0].frames_global.nbr_timepoints,
            "nbr_positions": frames[0].frames_global.nbr_positions,
            "bit_depth": frames[0].frames_global.bit_depth,
        }
        file_splitter.validate_global_meta(global_meta)

        # Metadata that will be returned from the DB for each frame
        frames_meta = file_splitter.make_dataframe(
            nbr_frames=global_meta["nbr_frames"],
        )
        for i, f in enumerate(frames):
            frames_meta.loc[i] = [
                f.channel_idx,
                f.slice_idx,
                f.time_idx,
                f.channel_name,
                f.file_name,
                f.pos_idx,
            ]
        return global_meta, frames_meta

    def get_frames_meta(self):
        """
        Get information for all frames in dataset associated with unique
        project identifier.
        TODO: Add support for only retrieving select channels
        (or whatever data subsets users are typically interested in)

        :return dict global_meta: Global metadata for dataset
        :return dataframe frames_meta: Metadata for each frame
        """
        # Create session
        with session_scope(self.credentials_filename) as session:
            # Check if ID already exist
            dataset = session.query(DataSet) \
                   .filter(DataSet.dataset_serial == self.dataset_serial).one()

            assert dataset.frames is True,\
                "This dataset has not been split into frames"

            # Get frames in datset
            frames = session.query(Frames) \
                .join(FramesGlobal) \
                .join(DataSet) \
                .filter(DataSet.dataset_serial == dataset.dataset_serial) \
                .all()
            # Get global and local metadata
            global_meta, frames_meta = self._get_meta_from_frames(frames)
            return global_meta, frames_meta
