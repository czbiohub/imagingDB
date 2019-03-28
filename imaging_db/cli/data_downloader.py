#!/usr/bin/python

import argparse
import os

import imaging_db.database.db_operations as db_ops
import imaging_db.filestorage.s3_storage as s3_storage
import imaging_db.metadata.json_operations as json_ops
import imaging_db.utils.cli_utils as cli_utils
import imaging_db.utils.db_utils as db_utils


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
        '-p', '--positions',
        type=int,
        nargs='+',
        help="Tuple containing position indices to download",
    )
    parser.add_argument(
        '-t', '--times',
        type=int,
        nargs='+',
        help="Tuple containing time indices to download",
    )
    parser.add_argument(
        '-c', '--channels',
        type=str,
        nargs='+',
        help="Tuple containing the channel names or indices to download",
    )
    parser.add_argument(
        '-z', '--slices',
        type=int,
        nargs='+',
        help="Tuple containing the z slices to download",
    )
    parser.add_argument(
        '--dest',
        type=str,
        help="Main destination directory, in which a subdir named args.id "
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
    parser.add_argument(
        '--nbr_workers',
        type=int,
        default=None,
        help="Number of treads to increase download speed"
    )

    return parser.parse_args()


def download_data(args):
    """
    Find all files associated with unique project identifier and
    download them to local folder

    :param args: Command line arguments:
        str id: Unique dataset identifier
        str dest: Local destination directory name
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
        raise AssertionError("Invalid ID:", e)

    # Create output directory as a subdirectory in args.dest named
    # dataset_serial. It stops if the subdirectory already exists to avoid
    # the risk of overwriting existing data
    dest_dir = os.path.join(args.dest, dataset_serial)
    try:
        os.makedirs(dest_dir, exist_ok=False)
    except FileExistsError as e:
        raise FileExistsError(
            "Folder {} already exists, {}".format(dest_dir, e))

    # Get database connection URI
    db_connection = db_utils.get_connection_str()
    # Instantiate database class
    try:
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=dataset_serial,
        )
        with db_ops.session_scope(db_connection) as session:
            db_inst.test_connection(session)
    except Exception as e:
        raise IOError("Can't instantiate DB: {}".format(e))

    if args.metadata is False:
        # Just download file(s)
        assert args.download,\
            "You set metadata *and* download to False. You get nothing."
        s3_dir, file_names = db_inst.get_filenames()
    else:
        # Get all the slicing args and recast as tuples
        if args.positions is None:
            pos = 'all'
        else:
            pos = tuple(args.positions)

        if args.times is None:
            times = 'all'
        else:
            times = tuple(args.times)

        if args.channels is None:
            channels = 'all'
        else:
            # If channels can be converted to ints, they're indices
            try:
                channels = [int(c) for c in args.channels]
            except ValueError:
                # Channels are names, not indices
                channels = args.channels
            channels = tuple(channels)

        if args.slices is None:
            slices = 'all'
        else:
            slices = tuple(args.slices)

        # Get the metadata from the requested frames
        with db_ops.session_scope(db_connection) as session:
            global_meta, frames_meta = db_inst.get_frames_meta(
                session=session,
                pos=pos,
                times=times,
                channels=channels,
                slices=slices,
            )
        # Write global metadata to destination directory
        global_meta_filename = os.path.join(
            dest_dir,
            "global_metadata.json",
        )
        json_ops.write_json_file(
            meta_dict=global_meta,
            json_filename=global_meta_filename,
        )
        # Write info for each frame to destination directory
        local_meta_filename = os.path.join(
            dest_dir,
            "frames_meta.csv",
        )
        frames_meta.to_csv(local_meta_filename, sep=",")
        # Extract folder and file names if we want to download
        s3_dir = global_meta["s3_dir"]
        file_names = frames_meta["file_name"]

    if args.download:
        if args.nbr_workers is not None:
            assert args.nbr_workers > 0,\
                "Nbr of worker must be >0, not {}".format(args.nbr_workers)
        data_loader = s3_storage.DataStorage(
            s3_dir=s3_dir,
            nbr_workers=args.nbr_workers,
        )
        data_loader.download_files(file_names, dest_dir)


if __name__ == '__main__':
    args = parse_args()
    download_data(args)

