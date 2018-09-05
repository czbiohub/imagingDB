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
    parser.add_argument('--csv', type=str, help="Full path to csv file")
    parser.add_argument('--login', type=str, help="Full path to file"
                        "containing JSON with DB login credentials")
    parser.add_argument('--override', type=int, default=0,
                        help="In case of interruption, set to 1 and this"
                             "t will continue upload where it stopped. Use"
                             "with caution.")

    return parser.parse_args()


def upload_data_and_update_db(args):
    """
    Split, crop volumes and flatfield correct images in input and target
    directories. Writes output as npy files for faster reading while training.
    TODO: Add logging instead of printing
    TODO: This ONLY supports ome.tif at the moment, fix when I have more data!

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
    """
    # Assert that csv file exists and load it
    assert os.path.isfile(args.csv), \
        "File doesn't exist: {}".format(args.csv)
    files_data = pd.read_csv(args.csv)

    # Upload all files
    for im_nbr, row in files_data.iterrows():
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

        # First, make sure we can connect to the database
        try:
            db_session.test_connection(args.login)
        except Exception as e:
            print(e)
        # Make sure dataset is not already in database
        if args.override == 0:
            db_session.assert_unique_id(args.login, dataset_serial)

        # Make sure image file exists
        file_name = row.file_name
        assert os.path.isfile(file_name), \
            "File doesn't exist: {}".format(file_name)

        if upload_type == "frames":
            meta_schema = row.meta_schema

            # Get image stack and metadata
            # ome.tif is the only file format tested at this point
            assert file_name[-8:] == ".ome.tif", \
                "Only supporting .ome.tif files for now"
            # Folder name in S3 bucket
            folder_name = "/".join([FRAME_FOLDER_NAME,
                                    dataset_serial])
            # Extract frames and metadata from file
            im_stack, frames_meta, frames_json, global_meta, global_json = \
                file_splitter.read_ome_tiff(
                    file_name=file_name,
                    schema_filename=meta_schema,
                    folder_name=folder_name,
                    file_format=FRAME_FILE_FORMAT)
            try:
                data_uploader = s3_storage.DataStorage(
                    folder_name=folder_name,
                )
                if args.override == 0:
                    data_uploader.assert_unique_id()
                # Upload stack frames to S3
                data_uploader.upload_frames(
                    file_names=list(frames_meta["file_name"]),
                    im_stack=im_stack,
                )
                print("Frames in {} uploaded to S3".format(file_name))
            except AssertionError as e:
                print("Project already on S3, moving on to DB entry")
                print(e)

            # Add sliced metadata to database
            try:
                db_session.insert_frames(
                    credentials_filename=args.login,
                    dataset_serial=dataset_serial,
                    description=row.description,
                    frames_meta=frames_meta,
                    frames_json_meta=frames_json,
                    global_meta=global_meta,
                    global_json_meta=global_json,
                    microscope=row.microscope,
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
            folder_name = "/".join([FILE_FOLDER_NAME,
                                    dataset_serial])
            try:
                data_uploader = s3_storage.DataStorage(
                    folder_name=folder_name,
                )
                data_uploader.upload_file(file_name=file_name)
                print("File {} uploaded to S3".format(file_name))
            except AssertionError as e:
                print("File {} already on S3".format(dataset_serial))
                print(e)
            # Add file entry to DB once I can get it tested
            global_json = {
                "file_origin": file_name,
            }
            try:
                db_session.insert_file(
                    credentials_filename=args.login,
                    dataset_serial=dataset_serial,
                    description=row.description,
                    folder_name=folder_name,
                    global_json_meta=global_json,
                    microscope=row.microscope,
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
