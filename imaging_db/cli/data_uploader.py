#!/usr/bin/python

import argparse
import os
import pandas as pd

import imaging_db.cli.cli_utils as cli_utils
import imaging_db.database.db_session as db_session
import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.images.file_splitter as file_splitter

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
        '--override',
        dest="override",
        action="store_true",
        help="In case of interruption, you can raise this flag and imageDB"
             "will continue upload where it stopped. Use with caution.",
    )
    parser.set_defaults(override=False)

    return parser.parse_args()


def upload_data_and_update_db(args):
    """
    Split, crop volumes and flatfield correct images in input and target
    directories. Writes output as npy files for faster reading while training.
    TODO: Add logging instead of printing

    :param list args:    parsed args containing
        str login: Full path to json file containing login credentials
        str csv: Full path to csv file containing the following fields
        for each file to be uploaded:

        str dataset_id: Unique dataset ID <ID>-YYYY-MM-DD-HH-MM-SS-<SSSS>
        str file_name: Full path to file to be uploaded
        str description: Short description of file
        bool frames: Specify if the file should be split prior to upload
        str json_meta: If slice, give full path to json metadata schema
        str parent_dataset_id: Parent dataset unique ID if there is one
        list positions: Which position files in folder to upload. Uploads all
         if left empty and file_name is a folder. Only valid for ome-tiff uploads.
    """
    # Assert that csv file exists and load it
    assert os.path.isfile(args.csv), \
        "File doesn't exist: {}".format(args.csv)
    files_data = pd.read_csv(args.csv)

    # Upload all files
    for file_nbr, row in files_data.iterrows():
        # Assert that ID is correctly formatted
        dataset_serial = row.dataset_id
        try:
            cli_utils.validate_id(dataset_serial)
        except AssertionError as e:
            print("Invalid ID:", e)

        # Assert that upload type is valid
        upload_type = row.upload_type.lower()
        assert upload_type in {"file", "frames"}, \
            "upload_type should be 'file' or 'frames', not {}".format(
                upload_type)
        # Instantiate S3 uploader
        if upload_type == "frames":
            s3_dir = "/".join([FRAME_FOLDER_NAME, dataset_serial])
        else:
            s3_dir = "/".join([FILE_FOLDER_NAME, dataset_serial])

        # First, make sure we can instantiate and connect to the database
        try:
            db_inst = db_session.DatabaseOperations(
                credentials_filename=args.login,
                dataset_serial=dataset_serial,
            )
        except Exception as e:
            print(e)
            raise
        # Make sure dataset is not already in database
        if not args.override:
            db_inst.assert_unique_id()

        # Make sure microscope is a string
        microscope = row.microscope
        if not isinstance(microscope, str):
            microscope = None

        if upload_type == "frames":
            # Find get + metadata extraction class for this data type
            # TODO: Refactor this to dynamically instantiate class
            if row.frames_format == "ome_tiff":
                positions = None
                if hasattr(row, 'positions'):
                    positions = row.positions

                frames_inst = file_splitter.OmeTiffSplitter(
                    data_path=row.file_name,
                    s3_dir=s3_dir,
                    override=args.override,
                    file_format=FRAME_FILE_FORMAT,
                )
                frames_inst.get_frames_and_metadata(
                    schema_filename=row.meta_schema,
                    positions=positions,
                )
            elif row.frames_format == "tif_folder":
                frames_inst = file_splitter.TifFolderSplitter(
                    data_path=row.file_name,
                    s3_dir=s3_dir,
                    file_format=FRAME_FILE_FORMAT,
                )
                frames_inst.get_frames_and_metadata()
            elif row.frames_format == "tif_video":
                frames_inst = file_splitter.TifVideoSplitter(
                    data_path=row.file_name,
                    s3_dir=s3_dir,
                    file_format=FRAME_FILE_FORMAT,
                )
                frames_inst.get_frames_and_metadata()
            else:
                "Only 'ome_tiff', 'tif_folder' and tif_video are supported "\
                    "formats for reading frames, not {}".format(row.frames_format)
                raise NotImplementedError

            # Add sliced metadata to database
            try:
                db_inst.insert_frames(
                    description=row.description,
                    frames_meta=frames_inst.get_frames_meta(),
                    frames_json_meta=frames_inst.get_frames_json(),
                    global_meta=frames_inst.get_global_meta(),
                    global_json_meta=frames_inst.get_global_json(),
                    microscope=microscope,
                    parent_dataset=row.parent_dataset_id,
                )
                print("Frame info for {} inserted in DB"
                      .format(dataset_serial))
            except AssertionError as e:
                print("Data set {} already in DB".format(dataset_serial))
                print(e)
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
            try:
                data_uploader.upload_file(file_name=row.file_name)
                print("File {} uploaded to S3".format(row.file_name))
            except AssertionError as e:
                print("File {} already on S3, moving on to DB entry")
                print(e)
            # Add file entry to DB once I can get it tested
            global_json = {"file_origin": row.file_name}
            try:
                db_inst.insert_file(
                    description=row.description,
                    s3_dir=s3_dir,
                    global_json_meta=global_json,
                    microscope=microscope,
                    parent_dataset=row.parent_dataset_id,
                )
                print("File info for {} inserted in DB".format(dataset_serial))
            except AssertionError as e:
                print("File {} already in database".format(dataset_serial))

        print("Successfully entered {} to S3 storage and database".format(
            dataset_serial)
        )


if __name__ == '__main__':
    args = parse_args()
    upload_data_and_update_db(args)
