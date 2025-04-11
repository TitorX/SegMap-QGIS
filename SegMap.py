import os
import random
from qgis.PyQt.QtWidgets import (
    QAction,
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QDockWidget,
    QWidget,
)
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    Qgis,
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsRasterLayer,
    QgsField,
    QgsFields,
    QgsSymbol,
    QgsMapLayer,
    QgsRendererCategory,
    QgsCategorizedSymbolRenderer
)
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtGui import QIcon, QColor
from PyQt5.QtCore import QMetaType
from iscontroller import ISController


HELP_MSG = """
1. The result is limited to the current view. Please zoom in to the area of interest.
2. Click left button to add points on foreground and right button for background.
3. Press the mouse middle button to drag the map.
4. 'Done' to accept the result and save it to the selected layer.
5. 'Terminate' to exit the tool.
"""


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


class DockWidget(QDockWidget):
    def __init__(self, map_controller, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_controller = map_controller

    def closeEvent(self, event):
        self.map_controller.cleanup()
        super().closeEvent(event)


class SegMap:
    PLUGIN_NAME = "SegMap"

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.api_endpoint = "https://segmap.nodes.studio"
        self.api_token = "1234"
        self.input_layer = None  # Raster layer for segmentation
        self.output_layer = None  # Vector layer (polygon) to store segmentation results
        self.controller = None

        self.model_id = None
        self.classes = "cls1, cls2, cls3"  # Default classes

        self.map_tool = None
        self.panel = None

    def initGui(self):
        """Create the GUI elements."""
        self.settings_action = QAction("Settings", self.iface.mainWindow())
        self.start_action = QAction("Start", self.iface.mainWindow())

        # Set icons for the actions
        self.settings_action.setIcon(
            QIcon(get_resource_path("icons/settings_icon.png"))
        )
        self.start_action.setIcon(QIcon(get_resource_path("icons/start_icon.png")))

        self.settings_action.triggered.connect(self.show_settings_dialog)
        self.start_action.triggered.connect(self.activate_tool)

        # Add buttons to the toolbar
        self.toolbar = self.iface.addToolBar(f"{self.PLUGIN_NAME} Toolbar")
        self.toolbar.addAction(self.start_action)
        self.toolbar.addAction(self.settings_action)

    def unload(self):
        """Remove the plugin from QGIS."""
        self.cleanup()
        self.toolbar.clear()
        self.iface.mainWindow().removeToolBar(self.toolbar)
        self.toolbar = None

    def cleanup(self):
        """Cleanup temporary layers."""
        if self.controller:
            self.controller.teardown()
            self.controller = None

        if self.panel:
            self.panel.close()
            self.panel = None

        # Stop the map tool
        if self.map_tool:
            self.map_tool.deactivate()
            self.map_tool = None
        self.iface.actionPan().trigger()  # Switch back to pan tool
        self.settings_action.setEnabled(True)  # Enable "Settings" button
        self.start_action.setEnabled(True)  # Enable "Start" button

    def show_settings_dialog(self):
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.PLUGIN_NAME} Settings")
        layout = QVBoxLayout()

        api_label = QLabel("API Endpoint:")
        self.api_input = QLineEdit()
        token_label = QLabel("API Token:")
        self.token_input = QLineEdit()
        class_label = QLabel("Classes (comma-separated):")
        self.class_input = QLineEdit()

        self.api_input.setText(self.api_endpoint)
        self.token_input.setText(self.api_token)
        self.class_input.setText(self.classes)

        save_button = QPushButton("Save")
        save_button.clicked.connect(lambda: self.save_settings(dialog))

        layout.addWidget(api_label)
        layout.addWidget(self.api_input)
        layout.addWidget(token_label)
        layout.addWidget(self.token_input)
        layout.addWidget(class_label)
        layout.addWidget(self.class_input)
        layout.addWidget(save_button)

        dialog.setLayout(layout)
        dialog.exec_()

    def save_settings(self, dialog):
        self.api_endpoint = self.api_input.text()
        self.api_token = self.token_input.text()
        self.classes = self.class_input.text()
        dialog.accept()

    def init_controller(self):
        if self.input_layer and self.output_layer:
            if self.controller:
                self.controller.teardown()  # Cleanup any existing controller

            self.controller = ISController(
                self.api_endpoint, self.api_token,
                self.canvas, self.input_layer
            )
            # Append layers to the project
            QgsProject.instance().addMapLayer(self.output_layer)
            QgsProject.instance().addMapLayer(self.controller.segm_layer)
            QgsProject.instance().addMapLayer(self.controller.click_layer)

            self.controller.segm_layer.setFlags(QgsMapLayer.Private)
            self.controller.click_layer.setFlags(QgsMapLayer.Private)

        else:
            self.iface.messageBar().pushMessage(
                "Error", "Please select layers first.", level=Qgis.Critical
            )

    def select_layers(self):
        """Popup dialog to select a raster layer and a storage layer."""
        dialog = QDialog()
        dialog.setWindowTitle("Select Layers")
        layout = QVBoxLayout()

        # Raster layer selection
        raster_layers = [
            layer
            for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsRasterLayer)
        ]
        if not raster_layers:
            self.iface.messageBar().pushMessage(
                "Error",
                "No raster layers loaded. You need to at least load one raster layer.",
                level=Qgis.Critical
            )
            return None, None

        raster_layer_dropdown = QComboBox()
        for layer in raster_layers:
            raster_layer_dropdown.addItem(layer.name(), layer)

        # Storage layer selection
        vector_layers = [
            layer
            for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsVectorLayer)
        ]
        output_layer_dropdown = QComboBox()
        for layer in vector_layers:
            output_layer_dropdown.addItem(layer.name(), layer)
        output_layer_dropdown.addItem("Create New Layer", None)  # Special option

        select_button = QPushButton("Select")
        select_button.clicked.connect(dialog.accept)

        # Add widgets to layout
        layout.addWidget(QLabel("Choose a raster layer:"))
        layout.addWidget(raster_layer_dropdown)
        layout.addWidget(QLabel("Choose an output layer:"))
        layout.addWidget(output_layer_dropdown)
        layout.addWidget(select_button)
        dialog.setLayout(layout)

        if dialog.exec_() == QDialog.Accepted:
            selected_raster_layer = raster_layer_dropdown.currentData()
            selected_output_layer = output_layer_dropdown.currentData()

            # If "Create New Layer" is selected, create a new vector layer
            if selected_output_layer is None:
                # Create a new vector layer with the same CRS as the canvas
                crs = self.canvas.mapSettings().destinationCrs()
                selected_output_layer = QgsVectorLayer(
                    f"Polygon?crs={crs.authid()}", "Segmentation Results", "memory"
                )

            # if the selected_output_layer has no field called "class",
            # add a new field called "class" of type string
            if selected_output_layer.fields().indexOf("class") == -1:
                selected_output_layer.dataProvider().addAttributes(
                    [QgsField("class", QMetaType.Type.QString)]
                )
                selected_output_layer.updateFields()

            # if the selected_output_layer is not using categorized symbology,
            # set it to categorized symbology
            if not isinstance(selected_output_layer.renderer(), QgsCategorizedSymbolRenderer):
                # Alter the symbology of the selected_output_layer
                categories = []
                for cls in self.classes.split(','):
                    cls = cls.strip()
                    symbol = QgsSymbol.defaultSymbol(selected_output_layer.geometryType())
                    # Generate random colors with 50% transparency
                    random_color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 128)
                    symbol.setColor(random_color)
                    category = QgsRendererCategory(cls, symbol, cls)
                    categories.append(category)

                symbol = QgsSymbol.defaultSymbol(selected_output_layer.geometryType())
                symbol.setColor(QColor(0, 0, 0, 128))  # Black with 50% transparency
                category = QgsRendererCategory("", symbol, "Other")
                categories.append(category)

                renderer = QgsCategorizedSymbolRenderer("class", categories)
                selected_output_layer.setRenderer(renderer)

            return selected_raster_layer, selected_output_layer
        return None, None

    def activate_tool(self):
        """
        Start the tool process.
        1. Open a panel on the right with more options.
        2. Provide options to start segmentation workflow and select a model.
        """
        self.cleanup()  # Cleanup any existing temporary layers

        # Popup dialog to select layers
        self.input_layer, self.output_layer = self.select_layers()

        if not self.input_layer or not self.output_layer:
            # User canceled the dialog
            return

        self.init_controller()

        # Create a dock widget on the right
        self.panel = DockWidget(self, "Tool Options", self.iface.mainWindow())
        self.panel.setWindowTitle("SegMap Options")
        self.panel.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)  # Align elements to the top

        # Add API URL display
        url_label = QLabel(f"API URL: {self.api_endpoint}")
        layout.addWidget(url_label)

        # Add "Select Model" dropdown
        model_label = QLabel("Select Model:")
        layout.addWidget(model_label)

        self.model_dropdown = QComboBox()
        models = self.controller.get_models() if self.controller else []
        if models:
            for model in models:
                self.model_dropdown.addItem(model['name'], model['id'])
            self.model_dropdown.setCurrentIndex(0)  # Default to the first model
            self.model_dropdown.currentIndexChanged.connect(self.update_model_selection)
            self.update_model_selection()  # Set the initial model ID
            layout.addWidget(self.model_dropdown)

        self.model_description_label = QLabel()
        self.model_description_label.setWordWrap(True)
        layout.addWidget(self.model_description_label)

        def update_description():
            current_index = self.model_dropdown.currentIndex()
            if current_index >= 0:
                model_description = models[current_index].get('description', "")
                self.model_description_label.setText(model_description if model_description else "")
            else:
                self.model_description_label.setText("")

        self.model_dropdown.currentIndexChanged.connect(update_description)
        update_description()  # Initialize the description block

        # Add "Select Class" dropdown
        class_label = QLabel("Select Class:")
        layout.addWidget(class_label)

        self.class_dropdown = QComboBox()
        if hasattr(self, 'classes') and self.classes:
            class_list = [cls.strip() for cls in self.classes.split(',')]
            for cls in class_list:
                self.class_dropdown.addItem(cls)
        layout.addWidget(self.class_dropdown)

        # Add "Done" button
        done_button = QPushButton("Confirm")
        done_button.clicked.connect(lambda: self.done_segmentation(save=True))
        layout.addWidget(done_button)

        # Add "Terminate" button
        terminate_button = QPushButton("Terminate")
        terminate_button.clicked.connect(self.cleanup)
        layout.addWidget(terminate_button)

        # Add spacer to push below elements to the bottom
        layout.addStretch()

        # Add help section (scrollable)
        help_label = QLabel(HELP_MSG)
        help_label.setWordWrap(True)
        help_label.setAlignment(Qt.AlignTop)

        help_scroll_area = QVBoxLayout()
        help_scroll_area.addWidget(help_label)

        help_container = QWidget()
        help_container.setLayout(help_scroll_area)
        help_container.setMinimumHeight(200)  # Set a minimum height for the scrollable area
        help_container.setMaximumHeight(800)  # Set a maximum height for the scrollable area

        layout.addWidget(help_container)

        # Set layout to a container widget and add it to the dock widget
        container_widget = QWidget()
        container_widget.setLayout(layout)
        self.panel.setWidget(container_widget)

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.panel)
        self.panel.show()

        self.enter_segmentation()

    def update_model_selection(self):
        """Update the selected model in the controller."""
        self.model_id = self.model_dropdown.currentData()

    def enter_segmentation(self):
        """Enter the segmentation workflow."""
        self.map_tool = QgsMapToolEmitPoint(self.canvas)
        self.map_tool.canvasClicked.connect(self.handle_canvas_click)
        self.canvas.setMapTool(self.map_tool)

        self.settings_action.setEnabled(False)  # Disable "Settings" button
        self.start_action.setEnabled(False)  # Disable "Start" button

    def handle_canvas_click(self, point, button):
        if not self.api_endpoint or not self.api_token:
            self.iface.messageBar().pushMessage(
                "Error", "API settings are not configured.", level=3
            )
            return

        # Create a new feature for the click
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        feature.setAttributes([1 if button == Qt.LeftButton else 0])
        self.controller.add_click(feature)

        # trigger segmentation
        try:
            self.controller.segment(self.model_id)
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", f"{str(e)}", level=Qgis.Critical
            )

    def done_segmentation(self, save=True):
        """
        Accept the segmentation result and save it to the selected layer.
        """
        # Transfer features from the segmentation layer to the selected layer
        if save and self.controller and self.output_layer:
            selected_class = self.class_dropdown.currentText()

            # if segm_layer and output_layer are not the same crs,
            # transform the segm_layer to the output_layer crs
            src_crs = self.controller.segm_layer.crs()
            dest_crs = self.output_layer.crs()
            if src_crs != dest_crs:
                self.controller.segm_layer.setCrs(dest_crs)

            for feature in self.controller.segm_layer.getFeatures():
                new_feature = QgsFeature(QgsFields([
                    QgsField("class", QMetaType.Type.QString)
                ]))
                new_feature.setGeometry(feature.geometry())
                new_feature.setAttribute("class", selected_class)
                self.output_layer.dataProvider().addFeature(new_feature)
            self.output_layer.updateExtents()
            self.output_layer.triggerRepaint()

        self.init_controller()
