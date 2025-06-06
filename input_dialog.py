from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QPushButton, QFileDialog
)
import os

class MeshInputDialog(QDialog):
    def __init__(self, default_path=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate 3D Surface from Contours")
        self.resize(500, 150)  # Make the dialog wider

        self.name_input = QLineEdit()
        self.spacing_input = QDoubleSpinBox()
        self.spacing_input.setDecimals(3)
        self.spacing_input.setMinimum(0.01)
        self.spacing_input.setValue(0.5)

        self.path_input = QLineEdit(default_path or os.path.expanduser("~/output_fault.geojson"))
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.choose_file)

        form_layout = QVBoxLayout()

        # Fault name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Fault Name:"))
        name_layout.addWidget(self.name_input)
        form_layout.addLayout(name_layout)

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

        # OK/Cancel buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        form_layout.addLayout(button_layout)

        self.setLayout(form_layout)

    def choose_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Mesh As", self.path_input.text(), "GeoJSON (*.geojson);;All Files (*)"
        )
        if path:
            self.path_input.setText(path)

    def get_values(self):
        return self.name_input.text(), self.spacing_input.value(), self.path_input.text()
