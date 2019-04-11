import os
import sys

from PyQt5.QtWidgets import QTableWidgetItem

module_path = os.path.abspath(os.path.join('../../'))
if module_path not in sys.path:
    sys.path.append(module_path)

import imaging_db.database.db_session as db_session

from .view import QtBrowser

class DatasetBrowser:
    """Viewer containing the rendered scene, layers, and controlling elements
    including dimension sliders, and control bars for color limits.

    Attributes
    ----------
    window : Window
        Parent window.
    layers : LayersList
        List of contained layers.
    dims : Dimensions
        Contains axes, indices, dimensions and sliders.
    camera : vispy.scene.Camera
        Viewer camera.
    """
    def __init__(self, credentials):

        self.credentials = credentials

        self._qt = QtBrowser(self)
        
        self._get_datasets()
        self._filter_datasets(search_string='*')
        self._make_table()

    def _make_table(self):
        self._qt.set_table_row_count(self.num_datasets)
        self._qt.set_table_col_count(4)
        self._qt.set_table_col_labels(["ID", "Date", "Time", "Description"])

        for row, d in enumerate(self.current_datasets):
            self._qt.set_table_item(row, 0, QTableWidgetItem(d.dataset_serial))
            self._qt.set_table_item(row, 1, QTableWidgetItem(d.date_time.strftime("%Y/%m/%d")))
            self._qt.set_table_item(row, 2, QTableWidgetItem(d.date_time.strftime("%H:%M:%S")))
            self._qt.set_table_item(row, 3, QTableWidgetItem(d.description))
            
    def _get_datasets(self):
        with db_session.session_scope(self.credentials) as session:
            self.datasets = session.query(db_session.DataSet)
            self.frames_global = session.query(db_session.FramesGlobal).join(db_session.DataSet)

    def _filter_datasets(self, search_string='*'):

        if '*' in search_string or '_' in search_string: 
            formatted_string = search_string.replace('_', '__')\
                                .replace('*', '%')\
                                .replace('?', '_')
        else:
            formatted_string = '%{0}%'.format(search_string)

        self.current_datasets = self.datasets.filter(db_session.DataSet.dataset_serial.ilike(formatted_string))

        self.num_datasets = self.current_datasets.count()

    def _new_search_string(self):
        search_string = self._qt.table.search_box.text()

        if not search_string:
            search_string = "*"

        self._filter_datasets(search_string)
        self._make_table()

    def _table_selection_changed(self):
        _, serial = self._qt.get_table_selection()

        self.current_frame = self.frames_global.filter(db_session.DataSet.dataset_serial == serial).first()
        selected_dataset = self.datasets.filter(db_session.DataSet.dataset_serial == serial).first()

        microscope = selected_dataset.microscope
        parent_key = str(selected_dataset.parent_id)
        is_frames = selected_dataset.frames
        description = selected_dataset.description
        
        if is_frames:
            nbr_positions = str(self.current_frame.nbr_positions)
            nbr_timepoints = str(self.current_frame.nbr_timepoints)
            nbr_channels = str(self.current_frame.nbr_channels)
            nbr_zslices = str(self.current_frame.nbr_slices)

            frames_files = 'Frames'

        else:
            nbr_positions = ''
            nbr_timepoints = '' 
            nbr_channels = ''
            nbr_zslices = ''

            frames_files = 'File'

        self._qt.update_inspector(serial=serial, microscope=microscope, parent_key=parent_key,
        frames_files=frames_files, description=description, nbr_timepoints=nbr_timepoints, nbr_positions=nbr_positions,
            nbr_channels=nbr_channels, nbr_zslices=nbr_zslices)
        
