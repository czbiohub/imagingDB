from PyQt5.QtWidgets import QWidget, QLineEdit, QVBoxLayout, QTableWidget, QTableWidgetItem

class QtDatasetTable(QWidget):

    def __init__(self, browser):
        super().__init__()

        self.browser = browser
        # Create the layout
        layout = QVBoxLayout()

        # Add the search box
        self.search_box = QLineEdit()
        self.search_box.textChanged.connect(self.browser._new_search_string)

        layout.addWidget(self.search_box)

        # Add the dataset list
        self._table_widget = QTableWidget()
        layout.addWidget(self._table_widget)

        self._table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self._table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self._table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table_widget.horizontalHeader().setStretchLastSection(True)
        self._table_widget.itemSelectionChanged.connect(self.browser._table_selection_changed)

        # Add the layout
        self.setLayout(layout)

    def set_item(self, row, col, item):
        self._table_widget.setItem(row, col, item)

    def set_row_count(self, row_count):
        self._table_widget.setRowCount(row_count)

    def set_col_count(self, col_count):
        self._table_widget.setColumnCount(col_count)

    def set_col_labels(self, labels):
        self._table_widget.setHorizontalHeaderLabels(labels)

    def get_selection(self):
        selected_row = self._table_widget.selectedItems()[0].row()
        selected_id = self._table_widget.item(selected_row, 0).text()

        return selected_row ,selected_id
