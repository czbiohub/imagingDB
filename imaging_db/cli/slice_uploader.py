#!/usr/bin/python

import argparse
import os

import imaging_db.cli.cli_utils as cli_utils
import imaging_db.database.db_session as db_session
import imaging_db.filestorage.s3_uploader as s3_uploader
import imaging_db.images.file_slicer as file_slicer

SLICE_FOLDER_NAME = "raw_slices"
FILE_FORMAT = ".png"


def parse_args():
    """
    Parse command line arguments for CLI

    :return: namespace containing the arguments passed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', type=str, help="Full path to file")
    parser.add_argument('--config', type=str,
                        help="Full path to JSON config file with login info")
    parser.add_argument('--id', type=str, help="Unique file ID, " \
                        "<ID>-YYYY-MM-DD-HH-MM-SS-<SSSS>")
    parser.add_argument('--meta', type=str, default="None",
                        help="Pass in metadata. Currently not supported")

    return parser.parse_args()


def slice_and_upload(args):
    """
    Split, crop volumes and flatfield correct images in input and target
    directories. Writes output as npy files for faster reading while training.

    :param list args:    parsed args containing
        str file:  Full path to input file that also has metadata
        str id: Unique file ID <ID>-YYYY-MM-DD-HH-<SSSS>
    """
    # Assert that ID is correctly formatted
    try:
        cli_utils.validate_id(args.id)
    except AssertionError as e:
        print("Invalid ID:", e)
    # Should maybe test db session and check unique ID first?
    # Get image stack and metadata
    im_stack,\
    metadata,\
    micromanager_meta,\
    global_metadata = file_slicer.read_ome_tiff(args.file)
    # Upload images to S3 bucket
    data_uploader = s3_uploader.DataUploader(
        id_str=args.id,
        folder_name=SLICE_FOLDER_NAME,
        file_format=FILE_FORMAT,
    )
    data_uploader.upload_slices(file_names=list(metadata["FileName"]),
                                im_stack=im_stack)

    # Start DB session
    with db_session.start_session(args.config, echo_sql=True) as session:
        # Enter metadata into database


if __name__ == '__main__':
    args = parse_args()
    slice_and_upload(args)
