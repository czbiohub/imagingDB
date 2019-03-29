#!/usr/bin/python

import argparse
import os
import pandas as pd
from tqdm import tqdm

import imaging_db.utils.cli_utils as cli_utils
import imaging_db.database.db_operations as db_ops
import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.metadata.json_ops as json_ops
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
        help="Full path to csv file",
    )
    parser.add_argument(
        '--login',
        type=str,
        help="Full path to file containing JSON with DB login credentials",
    )
    parser.add_argument(
        '--config',
        type=str,
        help="Full path to file containing JSON with upload configurations",
    )
    parser.add_argument(
        '--override',
        dest="override",
        action="store_true",
        help="In case of interruption, you can raise this flag and imageDB"
             "will continue upload where it stopped. Use with caution.",
    )
    parser.set_defaults(override=False)
    parser.add_argument(
        '--nbr_workers',
        type=int,
        default=None,
        help="Number of treads to increase download speed"
    )

    return parser.parse_args()


def upload_data_and_update_db(args):
    """
    Split, crop volumes and flatfield correct images in input and target
    directories. Writes output as npy files for faster reading while training.
    TODO: Add logging instead of printing

    :param list args:    parsed args containing
        login: Full path to json file containing login credentials
        csv: Full path to csv file containing the following fields
        for each file to be uploaded:
            str dataset_id: Unique dataset ID <ID>-YYYY-MM-DD-HH-MM-SS-<SSSS>
            str file_name: Full path to file to be uploaded
            str description: Short description of file
            str parent_dataset_id: Parent dataset unique ID if there is one
                list positions: Which position files in folder to upload.
                Uploads all if left empty and file_name is a folder.
                Only valid for ome-tiff uploads.
        config: Full path co json config file containing the fields:
            str upload_type: Specify if the file should be split prior to upload
                Valid options: 'frames' or 'file'
            str frames_format: Which file splitter class to use.
                Valid options: 'ome_tiff', 'tiffolder', 'tifvideo'
            str json_meta: If slice, give full path to json metadata schema
    """
    # Assert that csv file exists and load it
    assert os.path.isfile(args.csv), \
        "File doesn't exist: {}".format(args.csv)
    files_data = pd.read_csv(args.csv)

    # Get database connection URI
    db_connection = db_utils.get_connection_str()
    # Make sure we can connect to the database
    with db_ops.session_scope(db_connection) as session:
        db_ops.test_connection(session)

    # Read and validate config json
    config_json = json_ops.read_json_file(
        json_filename=args.config,
        schema_name="CONFIG_SCHEMA",
    )

    # Assert that upload type is valid
    upload_type = config_json['upload_type'].lower()
    assert upload_type in {"file", "frames"}, \
        "upload_type should be 'file' or 'frames', not {}".format(
            upload_type)

    if args.nbr_workers is not None:
        assert args.nbr_workers > 0, \
            "Nbr of worker must be >0, not {}".format(args.nbr_workers)

    # Make sure microscope is a string
    microscope = None
    if isinstance(config_json['microscope'], str):
        microscope = config_json['microscope']

    if upload_type == 'frames':
        # If upload type is frames, check from frames format
        assert 'frames_format' in config_json, \
            'You must specify the type of file(s)'
        splitter_class = aux_utils.get_splitter_class(
            config_json['frames_format'],
        )

    # Create the progress bar object
    file_prog = tqdm(files_data.iterrows(),
                     total=files_data.shape[0],
                     desc='Dataset')

    # Upload all files
    for file_nbr, row in file_prog:
        # Assert that ID is correctly formatted
        dataset_serial = row.dataset_id
        try:
            cli_utils.validate_id(dataset_serial)
        except AssertionError as e:
            print("Invalid ID:", e)

        # Get S3 directory based on upload type
        if upload_type == "frames":
            s3_dir = "/".join([FRAME_FOLDER_NAME, dataset_serial])
        else:
            s3_dir = "/".join([FILE_FOLDER_NAME, dataset_serial])
        # Instantiate database operations class
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=dataset_serial,
        )
        # Make sure dataset is not already in database
        if not args.override:
            db_inst.assert_unique_id()
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
            if not args.override:
                with db_ops.session_scope(db_connection) as session:
                    db_inst.assert_unique_id(session)
            # Instantiate splitter class
            frames_inst = splitter_class(
                data_path=row.file_name,
                s3_dir=s3_dir,
                override=args.override,
                file_format=FRAME_FILE_FORMAT,
                nbr_workers=args.nbr_workers,
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
            data_uploader = s3_storage.DataStorage(
                s3_dir=s3_dir,
            )
            if not args.override:
                data_uploader.assert_unique_id()
                with db_ops.session_scope(db_connection) as session:
                    db_inst.assert_unique_id(session)
            try:
                data_uploader.upload_file(file_name=row.file_name)
                print("File {} uploaded to S3".format(row.file_name))
            except AssertionError as e:
                print("File already on S3, moving on to DB entry. {}".format(e))

            sha = meta_utils.gen_sha256(row.file_name)
            # Add file entry to DB once I can get it tested
            global_json = {"file_origin": row.file_name}
            try:
                with db_ops.session_scope(db_connection) as session:
                    db_inst.insert_file(
                        session=session,
                        description=description,
                        s3_dir=s3_dir,
                        global_json_meta=global_json,
                        microscope=microscope,
                        parent_dataset=row.parent_dataset_id,
                        sha256=sha,
                    )
                print("File info for {} inserted in DB".format(dataset_serial))
            except AssertionError as e:
                print("File {} already in database".format(dataset_serial))


if __name__ == '__main__':
    args = parse_args()
    upload_data_and_update_db(args)
