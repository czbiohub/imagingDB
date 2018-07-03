#!/usr/bin/python

import argparse
import os
import pandas as pd

import imaging_db.cli.cli_utils as cli_utils
import imaging_db.database.db_session as db_session
import imaging_db.filestorage.s3_uploader as s3_uploader

FILE_FOLDER_NAME = "raw_files"
SLICE_FOLDER_NAME = "raw_slices"
SLICE_FILE_FORMAT = ".png"


def parse_args():
    """
    Parse command line arguments for CLI

    :return: namespace containing the arguments passed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=str, help="Unique project identifier")
    parser.add_argument('--dest', type=str, help="Destination folder")
    parser.add_argument('--login', type=str, help="Full path to file" \
                        "containing JSON with DB login credentials")

    return parser.parse_args()


def download_data(args):
    """
    Find all files associated with unique project identifier and
    download them to local folder

    :param args: Command line arguments:
        str id: Unique project identifier
        str dest: Local destination folder
        str login: Full path to json file containing database login credentials
    """
    raise NotImplementedError


if __name__ == '__main__':
    args = parse_args()
    download_data(args)
