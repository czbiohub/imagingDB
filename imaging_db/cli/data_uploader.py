#!/usr/bin/python

import argparse
import os

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
    parser.add_argument('-f', '--file', type=str, help="Full path to file")
    parser.add_argument('--login', type=str,
                        help="Full path to JSON config file with login info")
    parser.add_argument('--schema', type=str,
                        help="Full path to JSON file with metadata schema")
    parser.add_argument('--id', type=str,
                        help="Unique file ID: <ID>-YYYY-MM-DD-HH-MM-SS-<SSSS>")
    parser.add_argument('--description', type=str,
                        help="Short text file containing file description")
    parser.add_argument('--upload_type', type=str,
                        help="Type of upload, 'file' for just uploading a file"
                        "or 'slice' for reading file and splitting stack into"
                        "slices with associated metadata prior to upload")

    return parser.parse_args()


def upload_data_and_update_db(args):
    """
    Split, crop volumes and flatfield correct images in input and target
    directories. Writes output as npy files for faster reading while training.

    :param list args:    parsed args containing
        str file:  Full path to input file that also has metadata
        str id: Unique file ID <ID>-YYYY-MM-DD-HH-MM-SS-<SSSS>
    """
    # Assert that ID is correctly formatted
    project_serial = args.id
    try:
        cli_utils.validate_id(project_serial)
    except AssertionError as e:
        print("Invalid ID:", e)

    # Assert that upload type is valid
    assert args.upload_type in {"file", "slice"}, \
        "upload_type should be file or slice, not {}".format(args.upload_type)

    # First, make sure we can connect to the database
    try:
        db_session.test_connection(args.login)
    except Exception as e:
        print(e)

    # Get file description
    # TODO: Is a text file the best way to go here?
    assert os.path.isfile(args.description), \
        "File description doesn't exist: {}".format(args.description)
    with open(args.description, "r") as read_file:
        description = read_file.read()

    # Make sure file exists
    file_name = args.file
    assert os.path.isfile(file_name), \
        "File doesn't exist: {}".format(file_name)
    # Global json contains file origin and a description string
    # Read description from file?
    if args.upload_type == "slice":
        # Get image stack and metadata

        im_stack, \
        slice_meta, \
        slice_json, \
        global_meta, \
        global_json = file_slicer.read_ome_tiff(
            file_name=file_name,
            schema_filename=args.schema,
            file_format=SLICE_FILE_FORMAT)
        # Upload images to S3 bucket
        data_uploader = s3_uploader.DataUploader(
            project_serial=project_serial,
            folder_name=SLICE_FOLDER_NAME,
        )
        data_uploader.upload_slices(file_names=list(slice_meta["FileName"]),
                                    im_stack=im_stack)
        global_json["folder_name"] = "/".join([SLICE_FOLDER_NAME, project_serial])
        global_meta["description"] = description
        # Add slice entries to DB
        db_session.insert_slices(args.login, project_serial, file_format=)

    else:
        # Just upload file without any processing
        data_uploader = s3_uploader.DataUploader(
            project_serial=project_serial,
            folder_name=FILE_FOLDER_NAME,
        )
        data_uploader.upload_file(file_name=file_name)
        # Add file entry to DB once I can get it tested
        global_json = {
            "file_origin": file_name,
            "folder_name": "/".join([FILE_FOLDER_NAME, project_serial]),
        }
        global_meta = {"description": description}


if __name__ == '__main__':
    args = parse_args()
    upload_data_and_update_db(args)
