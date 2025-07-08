from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QCheckBox, QWidget, QDialogButtonBox,
    QComboBox, QMessageBox
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes
import os


# Valid linestring geometry types for contour processing (2D and Z only)
VALID_LINESTRING_TYPES = [
    QgsWkbTypes.LineString,
    QgsWkbTypes.MultiLineString,
    QgsWkbTypes.LineStringZ,
    QgsWkbTypes.MultiLineStringZ
]


def is_valid_linestring_layer(layer):
    """Check if a layer has valid linestring geometry for contour processing."""
    if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
        return False
    return layer.wkbType() in VALID_LINESTRING_TYPES


def is_valid_linestring_feature(feature):
    """Check if a feature has valid linestring geometry for contour processing."""
    geom = feature.geometry()
    flat_type = QgsWkbTypes.flatType(geom.wkbType())
    return flat_type in [QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString]


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
    def __init__(self, contours, default_path=None, preselected_layer=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate 3D Surface from Contours")
        self.resize(500, 600)
        self.min_spacing = 0.01
        self.max_spacing = 10.0
        self.contour_data = contours
        self.selected_layer = preselected_layer
        self.name_input = QLineEdit()
        
        # Layer selection components - QGIS standard style
        self.layer_combo = QComboBox()
        self.layer_combo.setMinimumWidth(300)
        self.refresh_layers_button = QPushButton("🔄")
        self.refresh_layers_button.setMaximumWidth(30)
        self.refresh_layers_button.setToolTip("Refresh layer list")
        self.refresh_layers_button.clicked.connect(self.populate_layer_combo)
        self.load_file_button = QPushButton("📁")
        self.load_file_button.setMaximumWidth(30)
        self.load_file_button.setToolTip("Load layer from file")
        self.load_file_button.clicked.connect(self.load_layer_from_file)

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

        # Set up layer selection and connect signals
        self.layer_combo.currentTextChanged.connect(self.on_layer_changed)
        
        # Populate layer combo with suitable layers
        self.populate_layer_combo()
        
        # If a layer was preselected, update the contour list
        if self.selected_layer:
            self.update_contour_list()

        form_layout = QVBoxLayout()
        
        # Layer selection section - QGIS standard style
        form_layout.addWidget(QLabel("Input layer:"))
        layer_layout = QHBoxLayout()
        layer_layout.addWidget(self.layer_combo)
        layer_layout.addWidget(self.refresh_layers_button)
        layer_layout.addWidget(self.load_file_button)
        form_layout.addLayout(layer_layout)

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
    
    def load_layer_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Layer File", "", 
            "Vector Files (*.shp *.geojson *.gpkg *.kml);;All Files (*)"
        )
        if path:
            # Try to load the layer
            try:
                layer = QgsVectorLayer(path, "Loaded Layer", "ogr")
                if layer.isValid() and is_valid_linestring_layer(layer):
                    # Add to combo and select it
                    self.layer_combo.addItem(f"{layer.name()} (from file)", layer)
                    self.layer_combo.setCurrentIndex(self.layer_combo.count() - 1)
                else:
                    QMessageBox.warning(self, "Invalid Layer", "Could not load the selected layer file or it doesn't contain valid linestring features.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error loading layer: {str(e)}")
    
    def populate_layer_combo(self):
        self.layer_combo.clear()
        self.layer_combo.addItem("-- Select a layer --")
        
        # Get all vector layers from the project
        project = QgsProject.instance()
        preselected_index = 0
        
        for layer in project.mapLayers().values():
            if is_valid_linestring_layer(layer):
                self.layer_combo.addItem(layer.name(), layer)
                # Check if this is the preselected layer
                if self.selected_layer and layer.id() == self.selected_layer.id():
                    preselected_index = self.layer_combo.count() - 1
        
        # Set the preselected layer in the combo box
        if preselected_index > 0:
            self.layer_combo.setCurrentIndex(preselected_index)
    
    def on_layer_changed(self, layer_name):
        if layer_name == "-- Select a layer --":
            self.selected_layer = None
            self.update_contour_list()
            return
            
        # Find the selected layer
        for i in range(self.layer_combo.count()):
            if self.layer_combo.itemText(i) == layer_name:
                self.selected_layer = self.layer_combo.itemData(i)
                self.update_contour_list()
                break
    
    def update_contour_list(self):
        self.contour_list.clear()
        
        if not self.selected_layer:
            return
            
        # Validate layer geometry
        features = list(self.selected_layer.getFeatures())
        if not features:
            QMessageBox.warning(self, "Empty Layer", "Selected layer contains no features.")
            return
            
        # Check geometry types
        for f in features:
            if not is_valid_linestring_feature(f):
                QMessageBox.warning(self, "Invalid Geometry", 
                                  f"Invalid geometry type: {QgsWkbTypes.displayString(f.geometry().wkbType())}. "
                                  f"All features must be LineStrings or MultiLineStrings.")
                return
        
        if len(features) < 2:
            QMessageBox.warning(self, "Insufficient Features", "Selected layer must contain at least 2 contours.")
            return
            
        # Create contour data
        contours = []
        for f in features:
            name = f["name"] if "name" in f.fields().names() else "Unnamed"
            elev = self._qvariant_to_float(f["elev"]) if "elev" in f.fields().names() else None
            contours.append({'name': name, 'elev': elev, 'feature': f})
        
        # Sort by elevation
        try:
            sorted_contours = sorted(contours, 
                    key=lambda x: float('inf') if x['elev'] is None else -float(x['elev'])
            )
        except:
            sorted_contours = contours
            
        # Populate the list
        for c in sorted_contours:
            item = QListWidgetItem()
            widget = ContourListItem(c['name'], c['elev'])
            item.setSizeHint(widget.sizeHint())
            self.contour_list.addItem(item)
            self.contour_list.setItemWidget(item, widget)
            
        self.contour_data = contours
    
    def _qvariant_to_float(self, qvar, return_none=False):
        try:
            val = float(qvar)
        except:
            if qvar is None or hasattr(qvar, 'isNull') and qvar.isNull():
                val = None
            elif hasattr(qvar, 'value'):
                val = float(qvar.value())
            elif hasattr(qvar, 'toDouble'):
                val = qvar.toDouble()[0]
            else:
                if return_none:
                    val = None
                else:
                    raise ValueError(f"Cannot turn {qvar} to float")
        return val

    def get_values(self):
        return (
            self.name_input.text(),
            float(self.spacing_input.text()),
            self.path_input.text(),
            self.elevation_path.text().strip() or None
        )

    def get_selected_layer(self):
        return self.selected_layer

    def get_selected_contours(self):
        selected = []
        if not self.contour_data:
            return selected
            
        for i in range(self.contour_list.count()):
            item = self.contour_list.item(i)
            widget = self.contour_list.itemWidget(item)
            if widget.is_checked():
                # Match original contour dictionary
                for c in self.contour_data:
                    if c['name'] == widget.name and c['elev'] == widget.elev:
                        selected.append(c)
                        break
        return selected