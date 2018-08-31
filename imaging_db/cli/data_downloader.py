#!/usr/bin/python

import argparse
import os

import imaging_db.cli.cli_utils as cli_utils
import imaging_db.database.db_session as db_session
import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.metadata.json_validator as json_validator


def parse_args():
    """
    Parse command line arguments for CLI

    :return: namespace containing the arguments passed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--id',
        type=str,
        help="Unique dataset identifier",
    )
    parser.add_argument(
        '--dest',
        type=str,
        help="Destination folder",
    )
    parser.add_argument(
        '--metadata',
        dest='metadata',
        action='store_true',
        help="Write csvs with metadata (for datasets split into frames only)",
    )
    parser.add_argument(
        '--no-metadata',
        dest='metadata',
        action='store_false',
    )
    parser.set_defaults(metadata=True)
    parser.add_argument(
        '--download',
        dest='download',
        action='store_true',
        help="Download all files (for datasets split into frames only)",
    )
    parser.add_argument(
        '--no-download',
        dest='download',
        action='store_false',
    )
    parser.set_defaults(download=True)
    parser.add_argument(
        '--login',
        type=str,
        help="Full path to file containing JSON with DB login credentials",
    )

    return parser.parse_args()


def download_data(args):
    """
    Find all files associated with unique project identifier and
    download them to local folder

    :param args: Command line arguments:
        str id: Unique dataset identifier
        str dest: Local destination folder
        bool metadata: Writes metadata (default True)
            global metadata in json, local for each frame in csv
        bool download: Downloads all files associated with dataset (default)
            If False, will only write csvs with metadata. Only for
            datasets split into frames
        str login: Full path to json file containing database login
            credentials
    """
    dataset_serial = args.id
    try:
        cli_utils.validate_id(dataset_serial)
    except AssertionError as e:
        print("Invalid ID:", e)

    # Create output directory if it doesn't exist already
    dest_folder = args.dest
    os.makedirs(dest_folder, exist_ok=True)

    if args.metadata == False:
        # Just download file(s)
        assert args.download is True,\
            "You set metadata *and* download to False. You get nothing."
        folder_name, file_names = db_session.get_filenames(
            credentials_filename=args.login,
            dataset_serial=dataset_serial,
        )
    else:
        # Dataset should be split into frames, get metadata
        global_meta, frames_info = db_session.get_frames_info(
            credentials_filename=args.login,
            dataset_serial=dataset_serial,
        )
        # Write global metadata to dest folder
        global_meta_filename = os.path.join(
            dest_folder,
            "global_metadata.json",
        )
        json_validator.write_json_file(
            meta_dict=global_meta,
            json_filename=global_meta_filename,
        )
        # Write info for each frame to dest folder
        local_meta_filename = os.path.join(
            dest_folder,
            "frames_info.json",
        )
        frames_info.to_csv(local_meta_filename, sep=",")
        # Extract folder and file names if we want to download
        folder_name = global_meta["folder_name"]
        file_names = frames_info["file_name"]

    if args.download:
        data_loader = s3_storage.DataStorage(
            folder_name=folder_name,
        )
        for f in file_names:
            dest_path = os.path.join(dest_folder, f)
            data_loader.download_file(file_name=f, dest_path=dest_path)


if __name__ == '__main__':
    args = parse_args()
    download_data(args)
