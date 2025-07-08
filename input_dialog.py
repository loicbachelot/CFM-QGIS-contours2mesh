from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QCheckBox, QWidget, QDialogButtonBox
)
from qgis.PyQt.QtCore import Qt
import os


class ContourListItem(QWidget):
    def __init__(self, name, elev, checked=True):
        super().__init__()
        self.name = name
        self.elev = elev
        self.checkbox = QCheckBox(f"{name} (Elevation: {elev})")
        self.checkbox.setChecked(checked)

        layout = QHBoxLayout()
        layout.addWidget(self.checkbox)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def is_checked(self):
        return self.checkbox.isChecked()


class MeshInputDialog(QDialog):
    def __init__(self, contours, default_path=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate 3D Surface from Contours")
        self.resize(500, 500)
        self.min_spacing = 0.01
        self.max_spacing = 10.0
        self.contour_data = contours
        self.name_input = QLineEdit()

        self.spacing_input = QDoubleSpinBox()
        self.spacing_input.setDecimals(2)
        self.spacing_input.setMinimum(0.01)
        self.spacing_input.setMaximum(10.0)
        self.spacing_input.setSingleStep(0.01)
        self.spacing_input.setValue(0.5)
        self.spacing_input.setToolTip("Spacing between points (in km). Must be ≥ 0.01.")

        self.path_input = QLineEdit(default_path or os.path.expanduser("~/output_fault.geojson"))
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.choose_file)

        self.elevation_label = QLabel("Elevation Raster (optional):")
        self.elevation_path = QLineEdit()
        self.elevation_browse = QPushButton("Browse...")
        self.elevation_browse.clicked.connect(self.select_elevation_file)

        self.contour_list = QListWidget()
        self.contour_list.setDragDropMode(QListWidget.InternalMove)
        self.contour_list.setDefaultDropAction(Qt.MoveAction)

        # Try sort by depth initially
        #try:
        sorted_contours = sorted(self.contour_data, 
                key=lambda x: float('inf') if x['elev'] is None else -float(x['elev'])
        )
        #except:
        #    sorted_contours = self.contour_data
        for c in sorted_contours:
            item = QListWidgetItem()
            widget = ContourListItem(c['name'], c['elev'])
            item.setSizeHint(widget.sizeHint())
            self.contour_list.addItem(item)
            self.contour_list.setItemWidget(item, widget)

        form_layout = QVBoxLayout()

        # Fault name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Fault Name:"))
        name_layout.addWidget(self.name_input)
        form_layout.addLayout(name_layout)

        # Elevation file (optional)
        elevation_layout = QHBoxLayout()
        elevation_layout.addWidget(self.elevation_label)
        elevation_layout.addWidget(self.elevation_path)
        elevation_layout.addWidget(self.elevation_browse)
        form_layout.addLayout(elevation_layout)

        # Point spacing
        spacing_layout = QHBoxLayout()
        spacing_layout.addWidget(QLabel("Point Spacing (km):"))
        spacing_layout.addWidget(self.spacing_input)
        form_layout.addLayout(spacing_layout)

        # Output path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Output Path:"))
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)
        form_layout.addLayout(path_layout)

        # contours list controls
        form_layout.addWidget(QLabel("Contours to include (you can reorder them):"))
        form_layout.addWidget(self.contour_list)

        # OK/Cancel buttons
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        self.ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(cancel_btn)
        form_layout.addLayout(button_layout)

        self.setLayout(form_layout)


    def choose_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Mesh As", self.path_input.text(), "GeoJSON (*.geojson);;All Files (*)"
        )
        if path:
            self.path_input.setText(path)

    def select_elevation_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Elevation Raster", "", "GeoTIFF (*.tif *.tiff)")
        if path:
            self.elevation_path.setText(path)

    def get_values(self):
        return (
            self.name_input.text(),
            float(self.spacing_input.text()),
            self.path_input.text(),
            self.elevation_path.text().strip() or None
        )

    def get_selected_contours(self):
        selected = []
        for i in range(self.contour_list.count()):
            item = self.contour_list.item(i)
            widget = self.contour_list.itemWidget(item)
            if widget.is_checked():
                # Match original QgsFeature
                for c in self.contour_data:
                    if c['name'] == widget.name and c['elev'] == widget.elev:
                        selected.append(c['feature'])
                        break
        return selected