#!/usr/bin/python

import argparse
import os

import imaging_db.images.file_slicer as file_slicer


def parse_args():
    """
    Parse command line arguments for CLI

    :return: namespace containing the arguments passed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', type=str, help="Full path to file")
    parser.add_argument('--id', type=str, help="Unique file ID, " \
                        "<ID>-YYYY-MM-DD-HH-<SSSS>")
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
    # Get image stack and metadata
    im_stack, metadata = file_slicer.read_ome_tiff(args.file)


if __name__ == '__main__':
    args = parse_args()
    slice_and_upload(args)