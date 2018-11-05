#!/usr/bin/python

import argparse
import os

import imaging_db.cli.cli_utils as cli_utils
import imaging_db.database.db_session as db_session
import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.metadata.json_validator as json_validator

from tqdm import tqdm

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
        '--p',
        type=int,
        nargs='+',
        help="Tuple containing position indices to download",
    )
    parser.add_argument(
        '--t',
        type=int,
        nargs='+',
        help="Tuple containing time indices to download",
    )
    parser.add_argument(
        '--c',
        type=str,
        nargs='+',
        help="Tuple containing the channels to download",
    )
    parser.add_argument(
        '--z',
        type=int,
        nargs='+',
        help="Tuple containing the z slices to download",
    )
    parser.add_argument(
        '--dest',
        type=str,
        help="Main destination folder, in which a subfolder named args.id "
             "\will be created",
        required=True
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

    # Create output directory as a subdirectory in args.dest named
    # dataset_serial. It stops if the subdirectory already exists to avoid
    # the risk of overwriting existing data


    dest_folder = os.path.join(args.dest, dataset_serial)
    try:
        os.makedirs(dest_folder, exist_ok=False)
    except FileExistsError as e:
        print("Folder {} already exists".format(dest_folder))
        return

    # Instantiate database class
    try:
        db_inst = db_session.DatabaseOperations(
            credentials_filename=args.login,
            dataset_serial=dataset_serial,
        )
    except Exception as e:
        print(e)
        raise

    if args.metadata is False:
        # Just download file(s)
        assert args.download,\
            "You set metadata *and* download to False. You get nothing."
        s3_dir, file_names = db_inst.get_filenames()
    else:
        # Get all the slicing args and recast as tuples
        if args.p is None:
            pos = 'all'
        
        else:
            pos = tuple(args.p)

        if args.t is None:
            times = 'all'
        
        else:
            times = tuple(args.t)

        if args.c is None:
            channels = 'all'
        
        else:
            channels = tuple(args.c)

        if args.z is None:
            slices = 'all'
        
        else:
            slices = tuple(args.z)

        # Get the metadata from the requested frames
        global_meta, frames_meta = db_inst.get_frames_meta(pos=pos, times=times, channels=channels, slices=slices)

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
            "frames_meta.csv",
        )
        frames_meta.to_csv(local_meta_filename, sep=",")
        # Extract folder and file names if we want to download
        s3_dir = global_meta["s3_dir"]
        file_names = frames_meta["file_name"]

    if args.download:
        data_loader = s3_storage.DataStorage(
            s3_dir=s3_dir,
        )
        for f in tqdm(file_names):
            dest_path = os.path.join(dest_folder, f)
            data_loader.download_file(file_name=f, dest_path=dest_path)


if __name__ == '__main__':
    args = parse_args()
    download_data(args)
