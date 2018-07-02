#!/usr/bin/python

import argparse
import os
import pandas as pd

import imaging_db.cli.cli_utils as cli_utils
import imaging_db.database.db_session as db_session
import imaging_db.filestorage.s3_uploader as s3_uploader
import imaging_db.images.file_slicer as file_slicer

FILE_FOLDER_NAME = "raw_files"
SLICE_FOLDER_NAME = "raw_slices"
SLICE_FILE_FORMAT = ".png"


def parse_args():
    """
    Parse command line arguments for CLI

    :return: namespace containing the arguments passed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=str, help="Full path to csv file")
    parser.add_argument('--login', type=str, help="Full path to file" \
                        "containing JSON with DB login credentials")

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

        str file_id: Unique file ID <ID>-YYYY-MM-DD-HH-MM-SS-<SSSS>
        str file_name: Full path to file to be uploaded
        str description: Short description of file
        bool slice: Specify if the file should be sliced prior to upload
        str json_meta: If slice, give full path to json metadata schema
    """
    # Assert that csv file exists and load it
    assert os.path.isfile(args.csv), \
        "File doesn't exist: {}".format(args.csv)
    files_data = pd.read_csv(args.csv)

    # Upload all files
    for im_nbr in range(files_data.shape[0]):
        # Assert that ID is correctly formatted
        project_serial = files_data.loc[im_nbr, "file_id"]
        try:
            cli_utils.validate_id(project_serial)
        except AssertionError as e:
            print("Invalid ID:", e)

        # Assert that upload type is valid
        upload_type = files_data.loc[im_nbr, "upload_type"].lower()
        assert upload_type in {"file", "slice"}, \
            "upload_type should be 'file' or 'slice', not {}".format(
                upload_type)

        # First, make sure we can connect to the database
        try:
            db_session.test_connection(args.login)
        except Exception as e:
            print(e)

        # Make sure image file exists
        file_name = files_data.loc[im_nbr, "file_name"]
        assert os.path.isfile(file_name), \
            "File doesn't exist: {}".format(file_name)

        # Get file description
        description = files_data.loc[im_nbr, "description"]

        if upload_type == "slice":
            meta_schema = files_data.loc[im_nbr, "description"]

            # Get image stack and metadata
            im_stack, slice_meta, slice_json, global_meta, global_json = \
                file_slicer.read_ome_tiff(
                    file_name=file_name,
                    schema_filename=meta_schema,
                    file_format=SLICE_FILE_FORMAT)
            # Upload image slices to S3 bucket
            data_uploader = s3_uploader.DataUploader(
                project_serial=project_serial,
                folder_name=SLICE_FOLDER_NAME,
            )
            data_uploader.upload_slices(
                file_names=list(slice_meta["FileName"]),
                im_stack=im_stack,
            )
            print("Slices in {} uploaded to S3".format(file_name))
            global_json["folder_name"] = "/".join([SLICE_FOLDER_NAME,
                                                   project_serial])
            # Add sliced metadata to DB
            db_session.insert_slices(
                credentials_filename=args.login,
                project_serial=project_serial,
                description=description,
                slice_meta=slice_meta,
                slice_json_meta=slice_json,
                global_meta=global_meta,
                global_json_meta=global_json)
            print("Slice info for {} inserted in DB".format(project_serial))

        else:
            # Just upload file without opening it
            data_uploader = s3_uploader.DataUploader(
                project_serial=project_serial,
                folder_name=FILE_FOLDER_NAME,
            )
            data_uploader.upload_file(file_name=file_name)
            print("File {} uploaded to S3".format(file_name))
            # Add file entry to DB once I can get it tested
            global_json = {
                "file_origin": file_name,
                "folder_name": "/".join([FILE_FOLDER_NAME,
                                         project_serial]),
            }
            db_session.insert_file(
                credentials_filename=args.login,
                project_serial=project_serial,
                description=description,
                global_json_meta=global_json)
            print("File info for {} inserted in DB".format(project_serial))

        print("Successfully entered {} to S3 storage and database".format(
            project_serial)
        )


if __name__ == '__main__':
    args = parse_args()
    upload_data_and_update_db(args)
