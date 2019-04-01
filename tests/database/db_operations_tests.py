import tests.database.db_basetest as db_basetest
import imaging_db.database.db_operations as db_ops


class TestDBOperations(db_basetest.DBBaseTest):
    """
    Test the database operations
    """

    def setUp(self):
        super().setUp()

        self.dataset_serial = 'TEST-2005-10-09-20-00-00-0001'
        self.global_meta = {
            "s3_dir": "dir_name",
            "nbr_frames": 5,
            "im_height": 256,
            "im_width": 512,
            "im_colors": 1,
            "bit_depth": "uint16",
            "nbr_slices": 6,
            "nbr_channels": 7,
            "nbr_timepoints": 8,
            "nbr_positions": 9,
        }
        self.global_json_meta = {'status': 'test'}
        self.microscope = 'test_microscope'
        self.description = 'This is a test'
        self.s3_dir = 'testing/TEST-2005-10-09-20-00-00-0001'
        self.sha256 = 'aaabbbccc'

    def tearDown(self):
        super().tearDown()

    def test_connection(self):
        db_ops.test_connection(self.session)

    def test_assert_unique_id(self):
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=self.dataset_serial,
        )
        db_inst.assert_unique_id(self.session)

    def test_insert(self):
        db_inst = db_ops.DatabaseOperations(
            dataset_serial=self.dataset_serial,
        )
        db_inst.insert_file(
            session=self.session,
            description=self.description,
            s3_dir=self.s3_dir,
            global_json_meta=self.global_json_meta,
            microscope=self.microscope,
            sha256=self.sha256,
        )
        # Assert insert by query
        datasets = self.session.query(db_ops.DataSet)
        self.assertEqual(datasets.count(), 1)
        dataset = datasets[0]
        self.assertEqual(dataset.id, 1)
        self.assertEqual(dataset.dataset_serial, self.dataset_serial)
        self.assertEqual(dataset.description, self.description)
        date_time = dataset.date_time
        self.assertEqual(date_time.year, 2005)
        self.assertEqual(date_time.month, 10)
        self.assertEqual(date_time.day, 9)
        self.assertEqual(dataset.microscope, self.microscope)
        self.assertEqual(dataset.description, self.description)
