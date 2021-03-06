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
import runpy
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
    Test the data downloader with S3 storage
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
        self.dataset_serial = 'FRAMES-2005-06-09-20-00-00-1000'
        self.frames_storage_dir = os.path.join('raw_frames', self.dataset_serial)
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
            self.main_dir,
            'db_credentials.json',
        )
        # Write a config file
        self.config_path = os.path.join(
            self.temp_path,
            'config_tif_id.json',
        )
        config = {
            "upload_type": "frames",
            "frames_format": "tif_id",
            "microscope": "Leica microscope CAN bus adapter",
            "filename_parser": "parse_ml_name",
            "storage": "s3"
        }
        json_ops.write_json_file(config, self.config_path)
        # Upload frames
        data_uploader.upload_data_and_update_db(
            csv=self.csv_path_frames,
            login=self.credentials_path,
            config=self.config_path,
        )
        # Create inputs for file upload
        self.dataset_serial_file = 'FILE-2005-06-01-01-00-00-1000'
        self.file_storage_dir = os.path.join('raw_files', self.dataset_serial_file)
        self.csv_path_file = os.path.join(
            self.temp_path,
            "test_upload_file.csv",
        )
        # Change to unique serial
        upload_csv['dataset_id'] = self.dataset_serial_file
        upload_csv.to_csv(self.csv_path_file)
        config_path = os.path.join(
            self.temp_path,
            'config_file.json',
        )
        config = {
            "upload_type": "file",
            "microscope": "Mass Spectrometry",
            "storage": "s3",
        }
        json_ops.write_json_file(config, config_path)
        # Upload file
        data_uploader.upload_data_and_update_db(
            csv=self.csv_path_file,
            login=self.credentials_path,
            config=config_path,
        )

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

    def test_parse_args_defaults(self):
        with patch('argparse._sys.argv',
                   ['python',
                    '--id', self.dataset_serial,
                    '--dest', 'dest_path',
                    '--login', 'test_login.json']):
            parsed_args = data_downloader.parse_args()
            self.assertIsNone(parsed_args.positions)
            self.assertIsNone(parsed_args.times)
            self.assertIsNone(parsed_args.channels)
            self.assertIsNone(parsed_args.slices)
            self.assertTrue(parsed_args.metadata)
            self.assertTrue(parsed_args.download)
            self.assertIsNone(parsed_args.nbr_workers)

    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_frames(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
        )
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
        self.assertEqual(meta_json['storage_dir'], self.frames_storage_dir)
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
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
            channels=1,
        )
        download_dir = os.path.join(dest_dir, self.dataset_serial)
        # Check frames_meta content
        frames_meta = pd.read_csv(os.path.join(download_dir, 'frames_meta.csv'))
        for i, row in frames_meta.iterrows():
            self.assertEqual(row.channel_idx, 1)
            im_name = 'im_c001_z00{}_t000_p000.png'.format(i)
            self.assertEqual(row.file_name, im_name)
        # Check downloaded images
        im_order = [1, 3, 5]
        for z in range(3):
            im_name = 'im_c001_z00{}_t000_p000.png'.format(z)
            im_path = os.path.join(download_dir, im_name)
            im = cv2.imread(im_path, cv2.IMREAD_ANYDEPTH)
            numpy.testing.assert_array_equal(im, self.im[im_order[i], ...])

    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_channel_convert_str(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
            channels='1',
        )
        download_dir = os.path.join(dest_dir, self.dataset_serial)
        # Check frames_meta content
        frames_meta = pd.read_csv(os.path.join(download_dir, 'frames_meta.csv'))
        for i, row in frames_meta.iterrows():
            self.assertEqual(row.channel_idx, 1)
            im_name = 'im_c001_z00{}_t000_p000.png'.format(i)
            self.assertEqual(row.file_name, im_name)
        # Check downloaded images
        im_order = [1, 3, 5]
        for z in range(3):
            im_name = 'im_c001_z00{}_t000_p000.png'.format(z)
            im_path = os.path.join(download_dir, im_name)
            im = cv2.imread(im_path, cv2.IMREAD_ANYDEPTH)
            numpy.testing.assert_array_equal(im, self.im[im_order[i], ...])

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_channel_name(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
            channels='channel1',
        )

    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_pts(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
            positions=0,
            times=[0],
            slices=1,
        )
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
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
            metadata=False,
            nbr_workers=2,
        )
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
        data_downloader.download_data(
            dataset_serial=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
            nbr_workers=2,
            metadata=False,
        )

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_no_download_or_meta(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        data_downloader.download_data(
            dataset_serial=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
            metadata=False,
            download=False,
            nbr_workers=2,
        )

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
        data_downloader.download_data(
            dataset_serial='Not-a-serial',
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
            metadata=False,
            nbr_workers=2,
        )

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_negative_workers(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        data_downloader.download_data(
            dataset_serial=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            storage='s3',
            metadata=False,
            download=False,
            nbr_workers=-2,
        )

    @patch('imaging_db.database.db_operations.session_scope')
    def test__main__(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        with patch('argparse._sys.argv',
                   ['python',
                    '--id', self.dataset_serial,
                    '--dest', dest_dir,
                    '--storage', 's3',
                    '--login', self.credentials_path]):
            runpy.run_path(
                'imaging_db/cli/data_downloader.py',
                run_name='__main__',
            )
            # Check that files are there
            dest_files = os.listdir(os.path.join(
                dest_dir,
                self.dataset_serial,
            ))
            self.assertTrue('frames_meta.csv' in dest_files)
            self.assertTrue('global_metadata.json' in dest_files)
            for c in range(self.nbr_channels):
                for z in range(self.nbr_slices):
                    im_name = 'im_c00{}_z00{}_t000_p000.png'.format(c, z)
                    self.assertTrue(im_name in dest_files)


class TestDataDownloaderLocalStorage(db_basetest.DBBaseTest):
    """
    Test the data downloader with local storage
    """

    @patch('imaging_db.database.db_operations.session_scope')
    def setUp(self, mock_session):
        super().setUp()
        mock_session.return_value.__enter__.return_value = self.session
        # Create temporary directory and write temp image
        self.tempdir = TempDirectory()
        self.temp_path = self.tempdir.path
        # Mock file storage
        self.tempdir.makedir('storage_mount_point')
        self.mount_point = os.path.join(self.temp_path, 'storage_mount_point')
        self.tempdir.makedir('storage_mount_point/raw_files')
        self.tempdir.makedir('storage_mount_point/raw_frames')
        # Test metadata parameters
        self.nbr_channels = 2
        self.nbr_slices = 3
        # Mock storage dir
        self.dataset_serial = 'FRAMES-2005-06-09-20-00-00-1000'
        self.frames_storage_dir = os.path.join('raw_frames', self.dataset_serial)
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
        # Create input arguments for data upload
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
            self.main_dir,
            'db_credentials.json',
        )
        self.config_path = os.path.join(
            self.temp_path,
            'config_tif_id.json',
        )
        config = {
            "upload_type": "frames",
            "frames_format": "tif_id",
            "microscope": "Leica microscope CAN bus adapter",
            "filename_parser": "parse_ml_name",
            "storage": "local",
            "storage_access": self.mount_point
        }
        json_ops.write_json_file(config, self.config_path)
        # Upload frames
        data_uploader.upload_data_and_update_db(
            csv=self.csv_path_frames,
            login=self.credentials_path,
            config=self.config_path,
        )
        # Create input args for file upload
        self.dataset_serial_file = 'FILE-2005-06-09-20-00-00-1000'
        self.file_storage_dir = os.path.join('raw_files', self.dataset_serial_file)
        self.csv_path_file = os.path.join(
            self.temp_path,
            "test_upload_file.csv",
        )
        # Change to unique serial
        upload_csv['dataset_id'] = self.dataset_serial_file
        upload_csv.to_csv(self.csv_path_file)
        config_path = os.path.join(
            self.temp_path,
            'config_file.json',
        )
        config = {
            "upload_type": "file",
            "microscope": "Mass Spectrometry",
            "storage": "local",
            "storage_access": self.mount_point
        }
        json_ops.write_json_file(config, config_path)
        # Upload file
        data_uploader.upload_data_and_update_db(
            csv=self.csv_path_file,
            login=self.credentials_path,
            config=config_path,
        )

    def tearDown(self):
        """
        Rollback database session.
        Tear down temporary folder and file structure, stop moto mock
        """
        super().tearDown()
        TempDirectory.cleanup_all()
        self.assertFalse(os.path.isdir(self.temp_path))

    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_frames(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            storage_access=self.mount_point,
        )
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
        self.assertEqual(meta_json['storage_dir'], self.frames_storage_dir)
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
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            storage_access=self.mount_point,
            channels=1,
        )
        download_dir = os.path.join(dest_dir, self.dataset_serial)
        # Check frames_meta content
        frames_meta = pd.read_csv(os.path.join(download_dir, 'frames_meta.csv'))
        for i, row in frames_meta.iterrows():
            self.assertEqual(row.channel_idx, 1)
            im_name = 'im_c001_z00{}_t000_p000.png'.format(i)
            self.assertEqual(row.file_name, im_name)
        # Check downloaded images
        im_order = [1, 3, 5]
        for z in range(3):
            im_name = 'im_c001_z00{}_t000_p000.png'.format(z)
            im_path = os.path.join(download_dir, im_name)
            im = cv2.imread(im_path, cv2.IMREAD_ANYDEPTH)
            numpy.testing.assert_array_equal(im, self.im[im_order[i], ...])

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_channel_name(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            storage_access=self.mount_point,
            channels='channel1',
        )

    @patch('imaging_db.database.db_operations.session_scope')
    def test_download_pts(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create dest dir
        self.tempdir.makedir('dest_dir')
        dest_dir = os.path.join(self.temp_path, 'dest_dir')
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial,
            login=self.credentials_path,
            dest=dest_dir,
            storage_access=self.mount_point,
            positions=0,
            times=0,
            slices=1,
        )
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
        # Download data
        data_downloader.download_data(
            dataset_serial=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            storage_access=self.mount_point,
            metadata=False,
            nbr_workers=2,
        )
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
        data_downloader.download_data(
            dataset_serial=self.dataset_serial_file,
            login=self.credentials_path,
            dest=dest_dir,
            storage_access=self.mount_point,
            nbr_workers=2,
            metadata=False,
        )
