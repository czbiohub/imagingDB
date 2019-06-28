import tests.database.db_basetest as db_basetest
import imaging_db.database.dataset as dataset


class TestDataset(db_basetest.DBBaseTest):
    def setUp(self):
        super().setUp()

        self.dataset = dataset.DataSet(
            dataset_serial='TEST-2010-01-01-10-00-00-0001',
            description="This is a test dataset",
            microscope='leica',
            frames=True,
            parent_id=None,
        )
        self.session.add(self.dataset)
        self.session.commit()

    def tearDown(self):
        super().tearDown()

    def test_dataset(self):
        result = self.session.query(dataset.DataSet).all()
        self.assertEqual(result[0], self.dataset)

    def test_parent_id(self):
        parent_query = self.session.query(dataset.DataSet).all()
        child = dataset.DataSet(
            dataset_serial='TEST-2010-01-01-10-00-00-0002',
            description="This is a child test dataset",
            microscope='leica',
            frames=True,
            parent_id=parent_query[0].id,
        )
        self.session.add(child)
        self.session.commit()
        # query again
        datasets = self.session.query(dataset.DataSet) \
            .filter(dataset.DataSet.dataset_serial == child.dataset_serial) \
            .all()

        self.assertEqual(datasets[0], child)
        self.assertEqual(datasets[0].parent_id, parent_query[0].id)
