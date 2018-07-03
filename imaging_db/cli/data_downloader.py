#!/usr/bin/python

import argparse
import os

import imaging_db.cli.cli_utils as cli_utils
import imaging_db.database.db_session as db_session
import imaging_db.filestorage.s3_storage as s3_storage


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
        str id: Unique dataset identifier
        str dest: Local destination folder
        str login: Full path to json file containing database login credentials
    """
    dataset_serial = args.id
    try:
        cli_utils.validate_id(dataset_serial)
    except AssertionError as e:
        print("Invalid ID:", e)

    # Create output directory if it doesn't exist already
    dest_folder = args.dest
    os.makedirs(dest_folder, exist_ok=True)

    folder_name, file_names = db_session.get_filenames(
        credentials_filename=args.login,
        dataset_serial=dataset_serial)

    data_loader = s3_storage.DataStorage(
        folder_name=folder_name,
    )
    for f in file_names:
        dest_path = os.path.join(dest_folder, f)
        data_loader.download_file(file_name=f, dest_path=dest_path)


if __name__ == '__main__':
    args = parse_args()
    download_data(args)
