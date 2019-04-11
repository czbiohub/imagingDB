from PyQt5.QtWidgets import QWidget, QSplitter, QLineEdit, QHBoxLayout, QTableWidget, QTableWidgetItem

from .dataset_table import QtDatasetTable
from .dataset_inspector import QtInspector

class QtBrowser(QWidget):

    def __init__(self, browser):
        super().__init__()

        self.browser = browser

        # Create the layout
        layout = QHBoxLayout()

        splitter = QSplitter()

        self.table = QtDatasetTable(self.browser)
        self.inspector = QtInspector(self.browser)

        splitter.addWidget(self.table)
        splitter.addWidget(self.inspector)

        layout.addWidget(splitter)
        
        # Add the layout
        self.setLayout(layout)

    def set_table_item(self, row, col, item):
        self.table.set_item(row, col, item)

    def set_table_row_count(self, row_count):
        self.table.set_row_count(row_count)

    def set_table_col_count(self, col_count):
        self.table.set_col_count(col_count)

    def set_table_col_labels(self, labels):
        self.table.set_col_labels(labels)

    def get_table_selection(self):

        selected_row ,selected_id = self.table.get_selection()

        return selected_row ,selected_id

    def update_inspector(self, serial=None, microscope=None, parent_key=None,
        frames_files=None, description=None, nbr_timepoints=None, nbr_positions=None,
        nbr_channels=None, nbr_zslices=None):

        self.inspector.update_dataset_box(serial=serial, microscope=microscope, parent_key=parent_key,
            frames_files=frames_files, description=description)

        self.inspector.update_slicing_box(nbr_timepoints=nbr_timepoints, nbr_positions=nbr_positions,
            nbr_channels=nbr_channels, nbr_zslices=nbr_zslices)
