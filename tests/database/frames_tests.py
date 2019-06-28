import tests.database.db_basetest as db_basetest

import imaging_db.database.dataset as dataset
import imaging_db.database.frames as frames
import imaging_db.database.frames_global as frames_global


class TestFrames(db_basetest.DBBaseTest):
    def setUp(self):
        super().setUp()

        self.dataset = dataset.DataSet(
            dataset_serial='TEST-2010-01-01-10-00-00-0001',
            description="This is a test dataset",
            microscope='leica',
            frames=True,
            parent_id=None,
        )
        self.frames_global = frames_global.FramesGlobal(
            s3_dir='test_bucket/testdir',
            nbr_frames=1,
            im_width=100,
            im_height=150,
            nbr_slices=10,
            nbr_channels=2,
            im_colors=1,
            nbr_timepoints=20,
            nbr_positions=30,
            bit_depth='uint16',
            metadata_json={"data_description": 'great'},
            data_set=self.dataset,
        )
        self.frames = frames.Frames(
            channel_idx=5,
            slice_idx=6,
            time_idx=7,
            pos_idx=8,
            channel_name='brightfield',
            file_name='im_test.png',
            sha256='AAAXXXXZZZZZ',
            metadata_json={"foo": 'bar'},
            frames_global=self.frames_global,
        )
        self.session.add(self.frames)
        self.session.commit()

    def tearDown(self):
        super().tearDown()

    def test_frames(self):
        result = self.session.query(frames.Frames).all()
        self.assertEqual(result[0], self.frames)
