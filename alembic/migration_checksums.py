#!/usr/bin/python

import argparse
import os

import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.database.db_operations as db_ops
import imaging_db.utils.db_utils as db_utils
import imaging_db.utils.meta_utils as meta_utils


def parse_args():
    """
    Parse command line arguments for CLI

    :return: namespace containing the arguments passed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--login',
        type=str,
        help="Full path to file containing JSON with DB login credentials",
    )
    return parser.parse_args()


def migrate_db(credentials_filename):
    """
    Updates sha256 checksums for all files and frames

    :param credentials_filename: Full path to DB credentials file
    """
    # Edit this depending on where your database credential file is stored
    # This assumes it's stored in dir above imagingDB
    dir_name = os.path.abspath(os.path.join('..'))
    dest_dir = os.path.join(dir_name, 'temp_downloads')
    os.makedirs(dest_dir, exist_ok=True)
    credentials_str = db_utils.get_connection_str(
        credentials_filename=credentials_filename,
    )
    # Get files and compute checksums
    with db_ops.session_scope(credentials_str) as session:
        files = session.query(db_ops.FileGlobal)
        for file in files:
            if file.sha256 is None:
                data_loader = s3_storage.DataStorage(
                    s3_dir=file.s3_dir,
                )
                file_name = file.metadata_json["file_origin"]
                file_name = file_name.split("/")[-1]
                dest_path = os.path.join(dest_dir, file_name)
                data_loader.download_file(
                    file_name=file_name,
                    dest_path=dest_path,
                )
                checksum = meta_utils.gen_sha256(dest_path)
                file.sha256 = checksum

    # Get frames and compute checksums
    with db_ops.session_scope(credentials_filename) as session:
        frames = session.query(db_ops.Frames)
        for frame in frames:
            if frame.sha256 is None:
                data_loader = s3_storage.DataStorage(
                    s3_dir=frame.frames_global.s3_dir,
                )
                im = data_loader.get_im(frame.file_name)
                checksum = meta_utils.gen_sha256(im)
                frame.sha256 = checksum


if __name__ == '__main__':
    args = parse_args()
    migrate_db(args.login)
