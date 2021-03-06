#!/usr/bin/python

import argparse
import os
import pandas as pd

import imaging_db.utils.cli_utils as cli_utils
import imaging_db.database.db_operations as db_ops
import imaging_db.metadata.json_operations as json_ops
import imaging_db.utils.aux_utils as aux_utils
import imaging_db.utils.db_utils as db_utils
import imaging_db.utils.meta_utils as meta_utils

FILE_FOLDER_NAME = "raw_files"
FRAME_FOLDER_NAME = "raw_frames"
FRAME_FILE_FORMAT = ".png"


def parse_args():
    """
    Parse command line arguments for CLI

    :return: namespace containing the arguments passed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--csv',
        type=str,
        required=True,
        help="Full path to csv file",
    )
    parser.add_argument(
        '--login',
        type=str,
        required=True,
        help="Full path to file containing JSON with DB login credentials",
    )
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help="Full path to file containing JSON with upload configurations",
    )
    parser.add_argument(
        '--overwrite',
        dest="overwrite",
        action="store_true",
        help="In case of interruption, you can raise this flag and imageDB"
             "will continue upload where it stopped. Use with caution.",
    )
    parser.set_defaults(overwrite=False)
    parser.add_argument(
        '--nbr_workers',
        type=int,
        default=None,
        help="Number of treads to increase download speed"
    )
    return parser.parse_args()


def upload_data_and_update_db(csv,
                              login,
                              config,
                              nbr_workers=None,
                              overwrite=False):
    """
    Takes a csv file in which each row represents a dataset, uploads the data
    to storage and metadata to database. If 'frames' is selected as upload
    type, each dataset will be split into individual 2D frames before moving
    to storage.
    TODO: Add logging instead of printing

    :param str login: Full path to json file containing login credentials
    :param str csv: Full path to csv file containing the following fields
        for each file to be uploaded:
            str dataset_id: Unique dataset ID <ID>-YYYY-MM-DD-HH-MM-SS-<SSSS>
            str file_name: Full path to file to be uploaded
            str description: Short description of file
            str parent_dataset_id: Parent dataset unique ID if there is one
                list positions: Which position files in folder to upload.
                Uploads all if left empty and file_name is a folder.
                Only valid for ome-tiff uploads.
    :param  str config: Full path to json config file containing the fields:
            str upload_type: Specify if the file should be split prior to upload
                Valid options: 'frames' or 'file'
            str frames_format: Which file splitter class to use.
                Valid options:
                'ome_tiff' needs MicroManagerMetadata tag for each frame for metadata
                'tif_folder' when each file is already an individual frame
                and relies on MicroManager metadata
                'tif_id' needs ImageDescription tag in first frame page for metadata
            str storage: 'local' (default) - data will be stored locally and
                synced to S3 the same day. Or 'S3' - data will be uploaded
                directly to S3 then synced with local storage daily.
            str storage_access: If not using predefined storage locations,
                this parameter refers to mount_point for local storage and
                bucket_name for S3 storage. (optional)
            str json_meta: If splitting to frames, give full path to json
                metadata schema for reading metadata (optional)
    :param int, None nbr_workers: Number of workers for parallel uploads
    :param bool overwrite: Use with caution if your upload if your upload was
            interrupted and you want to overwrite existing data in database
            and storage
    """
    # Assert that csv file exists and load it
    assert os.path.isfile(csv), \
        "File doesn't exist: {}".format(csv)
    files_data = pd.read_csv(csv)

    # Get database connection URI
    db_connection = db_utils.get_connection_str(login)
    db_utils.check_connection(db_connection)
    # Read and validate config json
    config_json = json_ops.read_json_file(
        json_filename=config,
        schema_name="CONFIG_SCHEMA",
    )
    # Assert that upload type is valid
    upload_type = config_json['upload_type'].lower()
    assert upload_type in {"file", "frames"}, \
        "upload_type should be 'file' or 'frames', not {}".format(
            upload_type,
        )
    if nbr_workers is not None:
        assert nbr_workers > 0, \
            "Nbr of worker must be >0, not {}".format(nbr_workers)
    # Import local or S3 storage class
    storage = 'local'
    if 'storage' in config_json:
        storage = config_json['storage']
    storage_class = aux_utils.get_storage_class(storage_type=storage)
    storage_access = None
    if 'storage_access' in config_json:
        storage_access = config_json['storage_access']

    # Make sure microscope is a string
    microscope = None
    if 'microscope' in config_json:
        if isinstance(config_json['microscope'], str):
            microscope = config_json['microscope']

    if upload_type == 'frames':
        # If upload type is frames, check from frames format
        assert 'frames_format' in config_json, \
            'You must specify the type of file(s)'
        splitter_class = aux_utils.get_splitter_class(
            config_json['frames_format'],
        )
    # Upload all files
    for file_nbr, row in files_data.iterrows():
        # Assert that ID is correctly formatted
        dataset_serial = row.dataset_id
        try:
            cli_utils.validate_id(dataset_serial)
        except AssertionError as e:
            raise AssertionError("Invalid ID:", e)

        # Get S3 directory based on upload type
        if upload_type == "frames":
            storage_dir = "/".join([FRAME_FOLDER_NAME, dataset_serial])
        else:
            storage_dir = "/".join([FILE_FOLDER_NAME, dataset_serial])
        # Instantiate database operations class
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=dataset_serial,
        )
        # Make sure dataset is not already in database
        if not overwrite:
            with db_ops.session_scope(db_connection) as session:
                db_inst.assert_unique_id(session)
        # Check for parent dataset
        parent_dataset_id = 'None'
        if 'parent_dataset_id' in row:
            parent_dataset_id = row.parent_dataset_id
        # Check for dataset description
        description = None
        if 'description' in row:
            if row.description == row.description:
                description = row.description

        if upload_type == "frames":
            # Instantiate splitter class
            frames_inst = splitter_class(
                data_path=row.file_name,
                storage_dir=storage_dir,
                storage_class=storage_class,
                storage_access=storage_access,
                overwrite=overwrite,
                file_format=FRAME_FILE_FORMAT,
                nbr_workers=nbr_workers,
            )
            # Get kwargs if any
            kwargs = {}
            if 'positions' in row:
                positions = row['positions']
                if not pd.isna(positions):
                    kwargs['positions'] = positions
            if 'schema_filename' in config_json:
                kwargs['schema_filename'] = config_json['schema_filename']
            if 'filename_parser' in config_json:
                filename_parser = config_json['filename_parser']
                kwargs['filename_parser'] = filename_parser
            # Extract metadata and split file into frames
            frames_inst.get_frames_and_metadata(**kwargs)

            # Add frames metadata to database
            try:
                with db_ops.session_scope(db_connection) as session:
                    db_inst.insert_frames(
                        session=session,
                        description=description,
                        frames_meta=frames_inst.get_frames_meta(),
                        frames_json_meta=frames_inst.get_frames_json(),
                        global_meta=frames_inst.get_global_meta(),
                        global_json_meta=frames_inst.get_global_json(),
                        microscope=microscope,
                        parent_dataset=parent_dataset_id,
                    )
            except AssertionError as e:
                print("Data set {} already in DB".format(dataset_serial), e)
        # File upload
        else:
            # Just upload file without opening it
            assert os.path.isfile(row.file_name), \
                "File doesn't exist: {}".format(row.file_name)
            data_uploader = storage_class(
                storage_dir=storage_dir,
                access_point=storage_access,
            )
            if not overwrite:
                data_uploader.assert_unique_id()
            try:
                data_uploader.upload_file(file_path=row.file_name)
                print("File {} uploaded to S3".format(row.file_name))
            except AssertionError as e:
                print("File already on S3, moving on to DB entry. {}".format(e))

            sha = meta_utils.gen_sha256(row.file_name)
            # Add file entry to DB once I can get it tested
            global_json = {"file_origin": row.file_name}
            file_name = row.file_name.split("/")[-1]
            try:
                with db_ops.session_scope(db_connection) as session:
                    db_inst.insert_file(
                        session=session,
                        description=description,
                        storage_dir=storage_dir,
                        file_name=file_name,
                        global_json_meta=global_json,
                        microscope=microscope,
                        parent_dataset=parent_dataset_id,
                        sha256=sha,
                    )
                print("File info for {} inserted in DB".format(dataset_serial))
            except AssertionError as e:
                print("File {} already in database".format(dataset_serial))


if __name__ == '__main__':
    args = parse_args()
    upload_data_and_update_db(
        csv=args.csv,
        login=args.login,
        config=args.config,
        nbr_workers=args.nbr_workers,
        overwrite=args.overwrite,
    )
