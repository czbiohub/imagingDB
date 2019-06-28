import argparse
import boto3
import cv2
import glob
import itertools
from moto import mock_s3
import nose.tools
import numpy as np
import numpy.testing
import os
import pandas as pd
from testfixtures import TempDirectory
import tifffile
from unittest.mock import patch

import imaging_db.cli.data_downloader as data_downloader
import imaging_db.cli.data_uploader as data_uploader
import tests.database.db_basetest as db_basetest
import imaging_db.metadata.json_operations as json_ops
import imaging_db.utils.meta_utils as meta_utils


class TestDataDownloader(db_basetest.DBBaseTest):
    """
    Test the data downloader
    """

    @patch('imaging_db.database.db_operations.session_scope')
    def setUp(self, mock_session):
        super().setUp()
        mock_session.return_value.__enter__.return_value = self.session
        # Setup mock S3 bucket
        self.mock = mock_s3()
        self.mock.start()
        self.conn = boto3.resource('s3', region_name='us-east-1')
        self.bucket_name = 'czbiohub-imaging'
        self.conn.create_bucket(Bucket=self.bucket_name)
        # Test metadata parameters
        self.nbr_channels = 2
        self.nbr_slices = 3
        # Mock S3 dir
        self.frames_s3_dir = "raw_frames/FRAMES-2005-06-09-20-00-00-1000"
        # Create temporary directory and write temp image
        self.tempdir = TempDirectory()
        self.temp_path = self.tempdir.path
        # Temporary file with 6 frames, tifffile stores channels first
        self.im = 50 * np.ones((6, 10, 15), dtype=np.uint16)
        self.im[0, :5, 3:12] = 50000
        self.im[2, :5, 3:12] = 40000
        self.im[4, :5, 3:12] = 30000
        # Metadata
        self.description = 'ImageJ=1.52e\nimages=6\nchannels=2\nslices=3\nmax=10411.0'
        # Save test tif file
        self.file_path = os.path.join(self.temp_path, "A1_2_PROTEIN_test.tif")
        tifffile.imsave(
            self.file_path,
            self.im,
            description=self.description,
        )
        self.dataset_serial = 'FRAMES-2005-06-09-20-00-00-1000'
        upload_csv = pd.DataFrame(
            columns=['dataset_id', 'file_name', 'description'],
        )
        upload_csv = upload_csv.append(
            {'dataset_id': self.dataset_serial,
             'file_name': self.file_path,
             'description': 'Testing'},
            ignore_index=True,
        )
        self.csv_path_frames = os.path.join(
            self.temp_path,
            "test_upload_frames.csv",
        )
        upload_csv.to_csv(self.csv_path_frames)
        self.credentials_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'db_credentials.json',
        )
        self.config_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'config_tif_id.json',
        )
        # Upload frames
        args = argparse.Namespace(
            csv=self.csv_path_frames,
            login=self.credentials_path,
            config=self.config_path,
            nbr_workers=None,
            override=False,
        )
        data_uploader.upload_data_and_update_db(args)
        # Upload file
        self.dataset_serial_file = 'FILE-2005-06-09-20-00-00-1000'
        self.file_s3_dir = "raw_files/FILE-2005-06-09-20-00-00-1000"
        self.csv_path_file = os.path.join(
            self.temp_path,
            "test_upload_file.csv",
        )
        # Change to unique serial
        upload_csv['dataset_id'] = self.dataset_serial_file
        upload_csv.to_csv(self.csv_path_file)
        config_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'config_file.json',
        )
        args = argparse.Namespace(
            csv=self.csv_path_file,
            login=self.credentials_path,
            config=config_path,
            nbr_workers=None,
            override=False,
        )
        data_uploader.upload_data_and_update_db(args)

    def tearDown(self):
        """
        Rollback database session.
        Tear down temporary folder and file structure, stop moto mock
        """
        super().tearDown()
        TempDirectory.cleanup_all()
        self.assertFalse(os.path.isdir(self.temp_path))
        self.mock.stop()

    def test_parse_args(self):
        with patch('argparse._sys.argv',
                   ['python',
                    '--id', self.dataset_serial,
                    '-p', '5',
                    '-t', '0',
                    '-c', '1', '2', '3',
                    '-z', '4', '5',
                    '--dest', 'dest_path',
                    '--login', 'test_login.json',
                    '--nbr_workers', '5']):
            parsed_args = data_downloader.parse_args()
            self.assertEqual(parsed_args.id, self.dataset_serial)
            self.assertListEqual(parsed_args.positions, [5])
            self.assertListEqual(parsed_args.times, [0])
            self.assertListEqual(parsed_args.channels, ['1', '2', '3'])
            self.assertListEqual(parsed_args.slices, [4, 5])
            self.assertEqual(parsed_args.dest, 'dest_path')
            self.assertEqual(parsed_args.login, 'test_login.json')
            self.assertEqual(parsed_args.nbr_workers, 5)

    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_frames(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        args = argparse.Namespace(
            id=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            nbr_workers=None,
            metadata=True,
            download=True,
            positions=None,
            channels=None,
            times=None,
            slices=None,
        )
        data_downloader.download_data(args)
        # Images are separated by slice first then channel
        im_order = [0, 2, 4, 1, 3, 5]
        it = itertools.product(range(self.nbr_channels), range(self.nbr_slices))
        for i, (c, z) in enumerate(it):
            im_name = 'im_c00{}_z00{}_t000_p000.png'.format(c, z)
            im_path = os.path.join(
                dest_dir,
                self.dataset_serial,
                im_name,
            )
            im = cv2.imread(im_path, cv2.IMREAD_ANYDEPTH)
            numpy.testing.assert_array_equal(im, self.im[im_order[i], ...])
        # Read and validate frames meta
        meta_path = os.path.join(
            dest_dir,
            self.dataset_serial,
            'frames_meta.csv',
        )
        frames_meta = pd.read_csv(meta_path)
        for i, row in frames_meta.iterrows():
            c = i // self.nbr_slices
            z = i % self.nbr_slices
            self.assertEqual(row.channel_idx, c)
            self.assertEqual(row.slice_idx, z)
            self.assertEqual(row.time_idx, 0)
            self.assertEqual(row.pos_idx, 0)
            im_name = 'im_c00{}_z00{}_t000_p000.png'.format(c, z)
            self.assertEqual(row.file_name, im_name)
            sha256 = meta_utils.gen_sha256(self.im[im_order[i], ...])
            self.assertEqual(row.sha256, sha256)
        # Read and validate global meta
        meta_path = os.path.join(
            dest_dir,
            self.dataset_serial,
            'global_metadata.json',
        )
        meta_json = json_ops.read_json_file(meta_path)
        self.assertEqual(meta_json['s3_dir'], self.frames_s3_dir)
        self.assertEqual(meta_json['nbr_frames'], 6)
        self.assertEqual(meta_json['im_width'], 15)
        self.assertEqual(meta_json['im_height'], 10)
        self.assertEqual(meta_json['nbr_slices'], self.nbr_slices)
        self.assertEqual(meta_json['nbr_channels'], self.nbr_channels)
        self.assertEqual(meta_json['im_colors'], 1)
        self.assertEqual(meta_json['nbr_timepoints'], 1)
        self.assertEqual(meta_json['nbr_positions'], 1)
        self.assertEqual(meta_json['bit_depth'], 'uint16')

    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_channel(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        args = argparse.Namespace(
            id=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            nbr_workers=None,
            metadata=True,
            download=True,
            positions=None,
            channels='1',
            times=None,
            slices=None,
        )
        data_downloader.download_data(args)
        meta_path = os.path.join(
            dest_dir,
            self.dataset_serial,
            'global_metadata.json',
        )
        frames_meta = pd.read_csv(meta_path)
        for i, row in frames_meta.iterrows():
            self.assertEqual(row.channel_idx, 1)

    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_pts(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        args = argparse.Namespace(
            id=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            nbr_workers=None,
            metadata=True,
            download=True,
            positions='0',
            channels=None,
            times='0',
            slices='1',
        )
        data_downloader.download_data(args)
        meta_path = os.path.join(
            dest_dir,
            self.dataset_serial,
            'global_metadata.json',
        )
        frames_meta = pd.read_csv(meta_path)
        for i, row in frames_meta.iterrows():
            self.assertEqual(row.pos_idx, 0)
            self.assertEqual(row.time_idx, 0)
            self.assertEqual(row.slice_idx, 1)

    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_file(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        args = argparse.Namespace(
            id=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            nbr_workers=2,
            metadata=False,
            download=True,
            positions=None,
            channels=None,
            times=None,
            slices=None,
        )
        data_downloader.download_data(args)
        # See if file has been downloaded
        file_path = os.path.join(
            dest_dir,
            self.dataset_serial_file,
            '*',
        )
        found_file = os.path.basename(glob.glob(file_path)[0])
        self.assertEqual("A1_2_PROTEIN_test.tif", found_file)

    @nose.tools.raises(FileExistsError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_folder_exists(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        self.tempdir.makedir(
            os.path.join('dest_dir', self.dataset_serial_file),
        )
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        args = argparse.Namespace(
            id=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            nbr_workers=2,
            metadata=False,
            download=True,
            positions=None,
            channels=None,
            times=None,
            slices=None,
        )
        data_downloader.download_data(args)

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_no_download_or_meta(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        args = argparse.Namespace(
            id=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            nbr_workers=2,
            metadata=False,
            download=False,
            positions=None,
            channels=None,
            times=None,
            slices=None,
        )
        data_downloader.download_data(args)

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_invalid_dataset(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        self.tempdir.makedir(
            os.path.join('dest_dir', self.dataset_serial_file),
        )
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        args = argparse.Namespace(
            id='Not-a-serial',
            login=self.credentials_path,
            dest=dest_dir,
            nbr_workers=2,
            metadata=False,
            download=True,
            positions=None,
            channels=None,
            times=None,
            slices=None,
        )
        data_downloader.download_data(args)

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_negative_workers(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        args = argparse.Namespace(
            id=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            nbr_workers=-2,
            metadata=False,
            download=False,
            positions=None,
            channels=None,
            times=None,
            slices=None,
        )
        data_downloader.download_data(args)
