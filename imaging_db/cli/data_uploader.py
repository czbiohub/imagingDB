#!/usr/bin/python

import argparse

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
    parser.add_argument('--config', type=str,
                        help="Full path to JSON config file with login info")
    parser.add_argument('--id', type=str,
                        help="Unique file ID: <ID>-YYYY-MM-DD-HH-MM-SS-<SSSS>")
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
        str id: Unique file ID <ID>-YYYY-MM-DD-HH-<SSSS>
    """
    # Assert that ID is correctly formatted
    project_serial = args.id
    try:
        cli_utils.validate_id(project_serial)
    except AssertionError as e:
        print("Invalid ID:", e)
    # Should maybe test db session and check unique ID first?
    # Assert that upload type is valid
    assert args.upload_type in {"file", "slice"}, \
        "upload_type should be file or slice, not {}".format(args.upload_type)

    if args.upload_type == "slice":
        # Get image stack and metadata
        im_stack, \
        slice_meta, \
        slice_json, \
        global_meta, \
        global_json = file_slicer.read_ome_tiff(
            file_name=args.file,
            file_format=SLICE_FILE_FORMAT)
        # Upload images to S3 bucket
        data_uploader = s3_uploader.DataUploader(
            id_str=project_serial,
            folder_name=SLICE_FOLDER_NAME,
        )
        data_uploader.upload_slices(file_names=list(slice_meta["FileName"]),
                                    im_stack=im_stack)
        # Add slice entries to DB once I can get it tested!!!
        # NOTE: What to do if db connection times out before commit?
    else:
        # Just upload file without any processing
        data_uploader = s3_uploader.DataUploader(
            id_str=project_serial,
            folder_name=FILE_FOLDER_NAME,
        )
        data_uploader.upload_file(file_name=args.file)
        global_json = {
            "file_origin": args.file,
        }
        # Add file entry to DB once I can get it tested


if __name__ == '__main__':
    args = parse_args()
    upload_data_and_update_db(args)
