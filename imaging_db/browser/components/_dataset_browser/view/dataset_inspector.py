from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QTextEdit

class QtInspector(QWidget):

    def __init__(self, browser):
        super().__init__()

        self.browser = browser

        # Create the layout
        layout = QVBoxLayout()

        dataset_box = self._make_dataset_box()
        description_box = self._make_description_box()
        slicing_box = self._make_slicing_box()

        layout.addWidget(dataset_box)
        layout.addWidget(description_box)
        layout.addWidget(slicing_box)
        
        # Add the layout
        self.setLayout(layout)

    def _make_dataset_box(self):
        dataset_box = QGroupBox()

        id_layout = QGridLayout()
        
        id_layout.addWidget(QLabel("Dataset serial:"), 0, 0)
        self.dataset_serial = QLabel()
        id_layout.addWidget(self.dataset_serial, 0, 1)

        id_layout.addWidget(QLabel("Microscope:"), 1, 0)
        self.microscope = QLabel()
        id_layout.addWidget(self.microscope, 1, 1)

        id_layout.addWidget(QLabel("Parent key:"), 2, 0)
        self.parent_key = QLabel()
        id_layout.addWidget(self.parent_key, 2, 1)

        id_layout.addWidget(QLabel("Frames or file:"), 3, 0)
        self.frames_files = QLabel()
        id_layout.addWidget(self.frames_files, 3, 1)

        dataset_box.setLayout(id_layout)

        return dataset_box
    def _make_description_box(self):

        description_box = QGroupBox()
        description_layout = QVBoxLayout()

        description_layout.addWidget(QLabel("Description"))

        #text = QString("test stufflsdjfalsdjflasjdflasd")

        self.description = QTextEdit()
        self.description.setReadOnly(True)
        description_layout.addWidget(self.description)

        description_box.setLayout(description_layout)

        return description_box


    def _make_slicing_box(self):
        slicing_box = QGroupBox()

        slice_layout = QGridLayout()

        slice_layout.addWidget(QLabel("Number of timepoints:"), 0, 0)
        self.nbr_timepoints = QLabel()
        slice_layout.addWidget(self.nbr_timepoints, 0, 1)

        slice_layout.addWidget(QLabel("Number of positions:"), 1, 0)
        self.nbr_positions = QLabel()
        slice_layout.addWidget(self.nbr_positions, 1, 1)

        slice_layout.addWidget(QLabel("Number of channels:"), 2, 0)
        self.nbr_channels = QLabel()
        slice_layout.addWidget(self.nbr_channels, 2, 1)

        slice_layout.addWidget(QLabel("Number of z slices:"), 3, 0)
        self.nbr_zslices = QLabel()
        slice_layout.addWidget(self.nbr_zslices, 3, 1)

        slicing_box.setLayout(slice_layout)

        return slicing_box

    def update_slicing_box(self, nbr_timepoints=None, nbr_positions=None,
        nbr_channels=None, nbr_zslices=None):

        if nbr_timepoints is not None:
            self.nbr_timepoints.setText(nbr_timepoints)

        if nbr_positions is not None:
            self.nbr_positions.setText(nbr_positions)

        if nbr_channels is not None:
            self.nbr_channels.setText(nbr_channels)

        if nbr_zslices is not None:
            self.nbr_zslices.setText(nbr_zslices)

    def update_dataset_box(self, serial=None, microscope=None, parent_key=None,
        frames_files=None, description=None):

        if serial is not None:
            self.dataset_serial.setText(serial)

        if microscope is not None:
            self.microscope.setText(microscope)

        if parent_key is not None:
            self.parent_key.setText(parent_key)

        if frames_files is not None:
            self.frames_files.setText(frames_files)

        if description is not None:
            self.description.setText(description)
