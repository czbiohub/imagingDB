import tests.database.db_basetest as db_basetest

import imaging_db.database.dataset as dataset
import imaging_db.database.file_global as file_global


class TestFileGlobal(db_basetest.DBBaseTest):
    def setUp(self):
        super().setUp()

        self.dataset = dataset.DataSet(
            dataset_serial='TEST-2010-01-01-10-00-00-0001',
            description="This is a test dataset",
            microscope='leica',
            frames=True,
            parent_id=None,
        )
        self.file_global = file_global.FileGlobal(
            s3_dir='test_bucket/testdir',
            file_name='test_file.lif',
            metadata_json={"data_description": 'great'},
            data_set=self.dataset,
            sha256='aaabbbccc'
        )
        self.session.add(self.file_global)
        self.session.commit()

    def tearDown(self):
        super().tearDown()

    def test_file_global(self):
        result = self.session.query(file_global.FileGlobal).all()
        self.assertEqual(result[0], self.file_global)
