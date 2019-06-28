import argparse
import boto3
import itertools
import json
from moto import mock_s3
import nose.tools
import numpy as np
import numpy.testing
import os
import pandas as pd
from testfixtures import TempDirectory
import tifffile
from unittest.mock import patch

import imaging_db.database.db_operations as db_ops
import imaging_db.cli.data_uploader as data_uploader
import tests.database.db_basetest as db_basetest
import imaging_db.utils.image_utils as im_utils
import imaging_db.utils.meta_utils as meta_utils


class TestDataUploader(db_basetest.DBBaseTest):
    """
    Test the data uploader
    """

    def setUp(self):
        super().setUp()
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
        self.s3_dir = "raw_frames/TEST-2005-06-09-20-00-00-1000"
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
        self.dataset_serial = 'TEST-2005-06-09-20-00-00-1000'
        upload_csv = pd.DataFrame(
            columns=['dataset_id',
                     'file_name',
                     'description',
                     'parent_dataset_id'],
        )
        upload_csv = upload_csv.append(
            {'dataset_id': self.dataset_serial,
             'file_name': self.file_path,
             'description': 'Testing',
             'parent_dataset_id': None,
             },
            ignore_index=True,
        )
        self.csv_path = os.path.join(self.temp_path, "test_upload.csv")
        upload_csv.to_csv(self.csv_path)
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
                    '--csv', self.csv_path,
                    '--login', 'test_login.json',
                    '--config', 'test_config.json',
                    '--nbr_workers', '5']):
            parsed_args = data_uploader.parse_args()
            self.assertEqual(parsed_args.csv, self.csv_path)
            self.assertEqual(parsed_args.login, 'test_login.json')
            self.assertEqual(parsed_args.config, 'test_config.json')
            self.assertFalse(parsed_args.override)
            self.assertEqual(parsed_args.nbr_workers, 5)

    @patch('imaging_db.database.db_operations.session_scope')
    def test_upload_frames(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        args = argparse.Namespace(
            csv=self.csv_path,
            login=self.credentials_path,
            config=self.config_path,
            nbr_workers=None,
            override=False,
        )
        data_uploader.upload_data_and_update_db(args)
        # Query database to find data_set and frames
        datasets = self.session.query(db_ops.DataSet) \
            .filter(db_ops.DataSet.dataset_serial == self.dataset_serial)
        self.assertEqual(datasets.count(), 1)
        dataset = datasets[0]
        self.assertEqual(dataset.id, 1)
        self.assertTrue(dataset.frames)
        self.assertEqual(dataset.dataset_serial, self.dataset_serial)
        date_time = dataset.date_time
        self.assertEqual(date_time.year, 2005)
        self.assertEqual(date_time.month, 6)
        self.assertEqual(date_time.day, 9)
        self.assertEqual(dataset.microscope,
                         "Leica microscope CAN bus adapter")
        self.assertEqual(dataset.description, 'Testing')
        # query frames_global
        global_query = self.session.query(db_ops.FramesGlobal) \
            .join(db_ops.DataSet) \
            .filter(db_ops.DataSet.dataset_serial == self.dataset_serial)
        self.assertEqual(
            global_query[0].s3_dir,
            self.s3_dir,
        )
        self.assertEqual(
            global_query[0].nbr_frames,
            self.nbr_channels * self.nbr_slices,
        )
        im_shape = self.im.shape
        self.assertEqual(
            global_query[0].im_width,
            im_shape[2],
        )
        self.assertEqual(
            global_query[0].im_height,
            im_shape[1],
        )
        self.assertEqual(
            global_query[0].nbr_slices,
            self.nbr_slices)
        self.assertEqual(
            global_query[0].nbr_channels,
            self.nbr_channels,
        )
        self.assertEqual(
            global_query[0].nbr_positions,
            1,
        )
        self.assertEqual(
            global_query[0].nbr_timepoints,
            1,
        )
        self.assertEqual(
            global_query[0].im_colors,
            1,
        )
        self.assertEqual(
            global_query[0].bit_depth,
            'uint16',
        )
        # query frames
        frames = self.session.query(db_ops.Frames) \
            .join(db_ops.FramesGlobal) \
            .join(db_ops.DataSet) \
            .filter(db_ops.DataSet.dataset_serial == self.dataset_serial) \
            .order_by(db_ops.Frames.file_name)
        # Images are separated by slice first then channel
        im_order = [0, 2, 4, 1, 3, 5]
        it = itertools.product(range(self.nbr_channels), range(self.nbr_slices))
        for i, (c, z) in enumerate(it):
            im_name = 'im_c00{}_z00{}_t000_p000.png'.format(c, z)
            self.assertEqual(frames[i].file_name, im_name)
            self.assertEqual(frames[i].channel_idx, c)
            self.assertEqual(frames[i].slice_idx, z)
            self.assertEqual(frames[i].time_idx, 0)
            self.assertEqual(frames[i].pos_idx, 0)
            sha256 = meta_utils.gen_sha256(self.im[im_order[i], ...])
            self.assertEqual(frames[i].sha256, sha256)
        # Download frames from storage and compare to originals
        it = itertools.product(range(self.nbr_channels), range(self.nbr_slices))
        for i, (c, z) in enumerate(it):
            im_name = 'im_c00{}_z00{}_t000_p000.png'.format(c, z)
            key = "/".join([self.s3_dir, im_name])
            byte_string = self.conn.Object(
                self.bucket_name, key).get()['Body'].read()
            # Construct an array from the bytes and decode image
            im = im_utils.deserialize_im(byte_string)
            # Assert that contents are the same
            nose.tools.assert_equal(im.dtype, np.uint16)
            numpy.testing.assert_array_equal(im, self.im[im_order[i], ...])

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_invalid_id(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        # Create csv with invalid ID
        upload_csv = pd.DataFrame(
            columns=['dataset_id', 'file_name', 'description'],
        )
        upload_csv = upload_csv.append(
            {'dataset_id': 'BAD_ID',
             'file_name': self.file_path,
             'description': 'Testing'},
            ignore_index=True,
        )
        invalid_csv_path = os.path.join(self.temp_path, "invalid_upload.csv")
        upload_csv.to_csv(invalid_csv_path)

        args = argparse.Namespace(
            csv=invalid_csv_path,
            login=self.credentials_path,
            config=self.config_path,
            nbr_workers=None,
            override=False,
        )
        data_uploader.upload_data_and_update_db(args)

    @patch('imaging_db.database.db_operations.session_scope')
    def test_upload_frames_already_in_db(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session
        args = argparse.Namespace(
            csv=self.csv_path,
            login=self.credentials_path,
            config=self.config_path,
            nbr_workers=None,
            override=True,
        )
        data_uploader.upload_data_and_update_db(args)
        # Try uploading a second time
        data_uploader.upload_data_and_update_db(args)

    @patch('imaging_db.database.db_operations.session_scope')
    def test_upload_file(self, mock_session):
        # Upload the same file but as file instead of frames
        mock_session.return_value.__enter__.return_value = self.session

        config_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'config_file.json',
        )
        args = argparse.Namespace(
            csv=self.csv_path,
            login=self.credentials_path,
            config=config_path,
            nbr_workers=None,
            override=False,
        )
        data_uploader.upload_data_and_update_db(args)
        # Query database to find data_set and file_global
        datasets = self.session.query(db_ops.DataSet) \
            .filter(db_ops.DataSet.dataset_serial == self.dataset_serial)
        self.assertEqual(datasets.count(), 1)
        dataset = datasets[0]
        self.assertEqual(dataset.id, 1)
        self.assertFalse(dataset.frames)
        self.assertEqual(dataset.dataset_serial, self.dataset_serial)
        date_time = dataset.date_time
        self.assertEqual(date_time.year, 2005)
        self.assertEqual(date_time.month, 6)
        self.assertEqual(date_time.day, 9)
        self.assertEqual(dataset.microscope, "Mass Spectrometry")
        self.assertEqual(dataset.description, 'Testing')
        # query file_global
        file_global = self.session.query(db_ops.FileGlobal) \
            .join(db_ops.DataSet) \
            .filter(db_ops.DataSet.dataset_serial == self.dataset_serial) \
            .one()
        expected_s3 = "raw_files/TEST-2005-06-09-20-00-00-1000"
        self.assertEqual(
            file_global.s3_dir,
            expected_s3,
        )
        expected_meta = {'file_origin': self.file_path}
        self.assertDictEqual(file_global.metadata_json, expected_meta)
        self.assertEqual(file_global.data_set, dataset)
        sha256 = meta_utils.gen_sha256(self.file_path)
        self.assertEqual(file_global.sha256, sha256)
        # Check that file has been uploaded
        s3_client = boto3.client('s3')
        key = "/".join([expected_s3, "A1_2_PROTEIN_test.tif"])
        # Just check that the file is there, we've dissected it before
        response = s3_client.list_objects_v2(Bucket=self.bucket_name,
                                             Prefix=key)
        self.assertEqual(response['KeyCount'], 1)

    @patch('imaging_db.database.db_operations.session_scope')
    def test_upload_file_already_in_db(self, mock_session):
        # Upload the same file but as file instead of frames
        mock_session.return_value.__enter__.return_value = self.session

        config_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'config_file.json',
        )
        args = argparse.Namespace(
            csv=self.csv_path,
            login=self.credentials_path,
            config=config_path,
            nbr_workers=None,
            override=True,
        )
        data_uploader.upload_data_and_update_db(args)
        # Try uploading a second time
        data_uploader.upload_data_and_update_db(args)

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_no_csv(self, mock_session):
        # Upload the same file but as file instead of frames
        mock_session.return_value.__enter__.return_value = self.session

        args = argparse.Namespace(
            csv='no-csv-path',
            login=self.credentials_path,
            config=self.config_path,
            nbr_workers=None,
            override=False,
        )
        data_uploader.upload_data_and_update_db(args)

    @nose.tools.raises(AssertionError)
    @patch('imaging_db.database.db_operations.session_scope')
    def test_negative_workers(self, mock_session):
        # Upload the same file but as file instead of frames
        mock_session.return_value.__enter__.return_value = self.session

        args = argparse.Namespace(
            csv=self.csv_path,
            login=self.credentials_path,
            config=self.config_path,
            nbr_workers=-1,
            override=False,
        )
        data_uploader.upload_data_and_update_db(args)

    @patch('imaging_db.database.db_operations.session_scope')
    def test_upload_ometif(self, mock_session):
        mock_session.return_value.__enter__.return_value = self.session

        dataset_serial = 'ISP-2005-01-01-01-00-00-0001'
        # Temporary frame
        im = np.ones((10, 15), dtype=np.uint16)
        # Metadata
        mmmetadata = json.dumps({
            "ChannelIndex": 1,
            "Slice": 2,
            "FrameIndex": 3,
            "PositionIndex": 4,
            "Channel": 'channel_name',
        })
        extra_tags = [('MicroManagerMetadata', 's', 0, mmmetadata, True)]
        ijmeta = {
            "Info": json.dumps({"InitialPositionList":
                                [{"Label": "Pos1"}, {"Label": "Pos3"}]}),
        }
        # Save test ome tif file
        file_path = os.path.join(self.temp_path, "test_Pos1.ome.tif")
        tifffile.imsave(file_path,
                        im,
                        ijmetadata=ijmeta,
                        extratags=extra_tags,
                        )
        upload_csv = pd.DataFrame(
            columns=['dataset_id',
                     'file_name',
                     'description',
                     'positions',
                     'schema_filename',
                     ],
        )
        # Get path to json schema file
        dir_name = os.path.dirname(__file__)
        schema_file_path = os.path.realpath(
            os.path.join(dir_name, '..', '..', 'metadata_schema.json'),
        )
        upload_csv = upload_csv.append(
            {'dataset_id': dataset_serial,
             'file_name': file_path,
             'description': 'Testing',
             'positions': 1,
             'schema_filename': schema_file_path,
             },
            ignore_index=True,
        )
        csv_path = os.path.join(self.temp_path, "test_ometif_upload.csv")
        upload_csv.to_csv(csv_path)
        config_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'config_ome_tiff.json',
        )
        # Upload data
        args = argparse.Namespace(
            csv=csv_path,
            login=self.credentials_path,
            config=config_path,
            nbr_workers=None,
            override=False,
        )
        data_uploader.upload_data_and_update_db(args)
