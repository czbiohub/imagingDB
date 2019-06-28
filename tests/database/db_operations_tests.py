import itertools
import nose.tools

import tests.database.db_basetest as db_basetest
import imaging_db.database.db_operations as db_ops
import imaging_db.utils.meta_utils as meta_utils


class TestDBOperations(db_basetest.DBBaseTest):
    """
    Test the database operations
    """

    def setUp(self):
        super().setUp()

        self.dataset_serial = 'TEST-2005-10-09-20-00-00-0001'
        self.global_meta = {
            "s3_dir": "dir_name",
            "nbr_frames": 6,
            "im_height": 256,
            "im_width": 512,
            "im_colors": 1,
            "bit_depth": "uint16",
            "nbr_slices": 2,
            "nbr_channels": 3,
            "nbr_timepoints": 1,
            "nbr_positions": 1,
        }
        self.global_json_meta = {'status': 'test'}
        self.microscope = 'test_microscope'
        self.description = 'This is a test'
        self.s3_dir = 'testing/TEST-2005-10-09-20-00-00-0001'
        self.sha256 = 'aaabbbccc'

        self.frames_meta = meta_utils.make_dataframe(6)
        self.frames_json_meta = []
        self.meta_dict = {'local_key': 'local_value'}
        self.channel_names = ['brightfield', 'phase', '405']
        for i, (c, z) in enumerate(itertools.product(range(3), range(2))):
            im_name = 'im_c00{}_z00{}_t005_p050.png'.format(c, z)
            self.frames_meta.loc[i, 'file_name'] = im_name
            self.frames_meta.loc[i, 'channel_idx'] = c
            self.frames_meta.loc[i, 'channel_name'] = self.channel_names[c]
            self.frames_meta.loc[i, 'slice_idx'] = z
            self.frames_meta.loc[i, 'pos_idx'] = 50
            self.frames_meta.loc[i, 'time_idx'] = 5
            self.frames_meta.loc[i, 'sha256'] = self.sha256
            self.frames_json_meta.append(self.meta_dict)
        # Insert frames
        self.db_inst = db_ops.DatabaseOperations(
            dataset_serial=self.dataset_serial,
        )
        self.db_inst.insert_frames(
            session=self.session,
            description='test frames',
            frames_meta=self.frames_meta,
            frames_json_meta=self.frames_json_meta,
            global_meta=self.global_meta,
            global_json_meta=self.global_json_meta,
            microscope=self.microscope,
            parent_dataset=None,
        )
        # query frames
        self.frames = self.session.query(db_ops.Frames) \
            .join(db_ops.FramesGlobal) \
            .join(db_ops.DataSet) \
            .filter(db_ops.DataSet.dataset_serial == self.dataset_serial) \
            .order_by(db_ops.Frames.file_name)

    def tearDown(self):
        super().tearDown()

    def test_connection(self):
        db_ops.test_connection(self.session)

    @nose.tools.raises(ConnectionError)
    def test_connection_no_session(self):
        db_ops.test_connection('session')

    @nose.tools.raises(AssertionError)
    def test_assert_unique_id(self):
        self.db_inst.assert_unique_id(self.session)

    def test_get_parent(self):
        dataset_serial = 'TEST-2005-10-09-20-00-00-0002'
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=dataset_serial,
        )
        # This is the first dataset inserted in setUp
        parent_key = db_inst._get_parent(self.session, self.dataset_serial)
        self.assertEqual(parent_key, 1)

    @nose.tools.raises(ValueError)
    def test_get_nonexisting_parent(self):
        dataset_serial = 'TEST-2005-10-09-20-00-00-0002'
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=dataset_serial,
        )
        # This is the first dataset inserted in setUp
        db_inst._get_parent(
            self.session,
            'TEST-2005-01-01-01-00-00-0002',
        )

    def test_get_non_parent(self):
        dataset_serial = 'TEST-2005-10-09-20-00-00-0002'
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=dataset_serial,
        )
        # This is the first dataset inserted in setUp
        parent_key = db_inst._get_parent(self.session, None)
        self.assertIsNone(parent_key)

    def test_insert_frames(self):
        for i, (c, z) in enumerate(itertools.product(range(3), range(2))):
            im_name = 'im_c00{}_z00{}_t005_p050.png'.format(c, z)
            self.assertEqual(self.frames[i].file_name, im_name)
            self.assertEqual(self.frames[i].channel_idx, c)
            self.assertEqual(self.frames[i].channel_name, self.channel_names[c])
            self.assertEqual(self.frames[i].slice_idx, z)
            self.assertEqual(self.frames[i].time_idx, 5)
            self.assertEqual(self.frames[i].pos_idx, 50)
            self.assertEqual(self.frames[i].sha256, self.sha256)
            self.assertDictEqual(self.frames[i].metadata_json, self.meta_dict)
        # query frames_global
        global_query = self.session.query(db_ops.FramesGlobal) \
            .join(db_ops.DataSet) \
            .filter(db_ops.DataSet.dataset_serial == self.dataset_serial)
        self.assertEqual(
            global_query[0].s3_dir,
            self.global_meta['s3_dir'],
        )
        self.assertEqual(
            global_query[0].nbr_frames,
            self.global_meta['nbr_frames'],
        )
        self.assertEqual(
            global_query[0].im_width,
            self.global_meta['im_width'],
        )
        self.assertEqual(
            global_query[0].im_height,
            self.global_meta['im_height'],
        )
        self.assertEqual(
            global_query[0].nbr_slices,
            self.global_meta['nbr_slices'],
        )
        self.assertEqual(
            global_query[0].nbr_channels,
            self.global_meta['nbr_channels'],
        )
        self.assertEqual(
            global_query[0].nbr_positions,
            self.global_meta['nbr_positions'],
        )
        self.assertEqual(
            global_query[0].nbr_timepoints,
            self.global_meta['nbr_timepoints'],
        )
        self.assertEqual(
            global_query[0].im_colors,
            self.global_meta['im_colors'],
        )
        self.assertEqual(
            global_query[0].bit_depth,
            self.global_meta['bit_depth'],
        )

    def test_insert_file(self):
        dataset_serial = 'TEST-2005-10-12-20-00-00-0001'
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=dataset_serial,
        )
        file_name = 'test_file.lif'
        db_inst.insert_file(
            session=self.session,
            description=self.description,
            s3_dir=self.s3_dir,
            file_name=file_name,
            global_json_meta=self.global_json_meta,
            microscope=self.microscope,
            sha256=self.sha256,
        )
        # Assert insert by query
        datasets = self.session.query(db_ops.DataSet) \
            .filter(db_ops.DataSet.dataset_serial == dataset_serial)
        self.assertEqual(datasets.count(), 1)
        dataset = datasets[0]
        # This is the second dataset inserted
        self.assertEqual(dataset.id, 2)
        self.assertEqual(dataset.dataset_serial, dataset_serial)
        date_time = dataset.date_time
        self.assertEqual(date_time.year, 2005)
        self.assertEqual(date_time.month, 10)
        self.assertEqual(date_time.day, 12)
        self.assertEqual(dataset.microscope, self.microscope)
        self.assertEqual(dataset.description, self.description)
        # Get file_global and validate
        file_global = self.session.query(db_ops.FileGlobal) \
            .join(db_ops.DataSet) \
            .filter(db_ops.DataSet.dataset_serial == dataset_serial) \
            .one()
        self.assertEqual(file_global.s3_dir, self.s3_dir)
        self.assertEqual(file_global.file_name, file_name)
        self.assertDictEqual(file_global.metadata_json, self.global_json_meta)
        self.assertEqual(file_global.sha256, self.sha256)

    def test_get_filenames(self):
        s3_dir, file_names = self.db_inst.get_filenames(
            session=self.session,
        )
        self.assertEqual(s3_dir, self.global_meta['s3_dir'])
        for i, (c, z) in enumerate(itertools.product(range(3), range(2))):
            im_name = 'im_c00{}_z00{}_t005_p050.png'.format(c, z)
            self.assertEqual(file_names[i], im_name)

    def test_slice_frames(self):
        sliced_frames = self.db_inst._slice_frames(
            frames=self.frames,
        )
        for i, (c, z) in enumerate(itertools.product(range(3), range(2))):
            im_name = 'im_c00{}_z00{}_t005_p050.png'.format(c, z)
            self.assertEqual(sliced_frames[i].file_name, im_name)

    def test_slice_frames_select(self):
        sliced_frames = self.db_inst._slice_frames(
            frames=self.frames,
            pos=(50,),
            times=(5,),
            channels=(1, 2),
            slices=(1,),
        )
        for i, c in enumerate(range(1, 3)):
            im_name = 'im_c00{}_z001_t005_p050.png'.format(c)
            self.assertEqual(sliced_frames[i].file_name, im_name)

    @nose.tools.raises(AssertionError)
    def test_slice_frames_no_matching_channels(self):
        self.db_inst._slice_frames(
            frames=self.frames,
            channels=('1', '2'),
        )

    @nose.tools.raises(ValueError)
    def test_slice_frames_invalid_channel(self):
        self.db_inst._slice_frames(
            frames=self.frames,
            channels=[1],
        )

    @nose.tools.raises(ValueError)
    def test_slice_frames_invalid_channel_tuple(self):
        self.db_inst._slice_frames(
            frames=self.frames,
            pos=(50,),
            times=(5,),
            channels=(1, '2'),
            slices=(1,),
        )

    @nose.tools.raises(ValueError)
    def test_slice_frames_invalid_time(self):
        self.db_inst._slice_frames(
            frames=self.frames,
            times='2',
        )

    @nose.tools.raises(ValueError)
    def test_slice_frames_invalid_pos(self):
        self.db_inst._slice_frames(
            frames=self.frames,
            pos=3,
        )

    def test_get_meta_from_frames(self):
        global_meta, frames_meta = self.db_inst._get_meta_from_frames(
            self.frames,
        )
        expected_meta = self.global_meta
        expected_meta['metadata_json'] = self.global_json_meta
        self.assertDictEqual(global_meta, self.global_meta)
        self.assertTrue(frames_meta.equals(self.frames_meta))

    def test_get_frames_meta(self):
        global_meta, frames_meta = self.db_inst.get_frames_meta(
            session=self.session,
        )
        expected_meta = self.global_meta
        expected_meta['metadata_json'] = self.global_json_meta
        self.assertDictEqual(global_meta, self.global_meta)
        self.assertTrue(frames_meta.equals(self.frames_meta))
