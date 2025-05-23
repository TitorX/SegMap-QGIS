from typing import Optional, Any
import os
from qgis.PyQt.QtWidgets import (
    QAction,
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDockWidget,
)
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QIcon, QDesktopServices
from qgis.core import (
    Qgis,
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsFields,
    QgsMapLayer,
    QgsSettings,
)
from qgis.gui import QgsMapToolEmitPoint, QgsMapCanvas
from PyQt5.QtCore import QMetaType, QPoint
from iscontroller import ISController
from ui.ui_ToolPanel import Ui_ToolPanel


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


class DockWidget(QDockWidget):
    def __init__(self, map_controller: 'SegMap', *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.map_controller = map_controller
        self.ui = Ui_ToolPanel()
        self.ui.setupUi(self)

    def closeEvent(self, event: Any) -> None:
        self.map_controller.deactivate_tool()  # Cleanup when the panel is closed
        super().closeEvent(event)


class SegMap:
    PLUGIN_NAME = "SegMap"

    def __init__(self, iface) -> None:
        self.iface = iface
        self.canvas: QgsMapCanvas = iface.mapCanvas()
        self.settings = QgsSettings()
        self.api_endpoint: str = self.settings.value(
            "SegMap/api_endpoint", "https://segmap.nodes.studio"
        )
        self.api_token: str = self.settings.value(
            "SegMap/api_token", "demo"
        )

        self.controller: Optional[ISController] = None
        self.model_id: Optional[str] = None
        self.map_tool: Optional[QgsMapToolEmitPoint] = None
        self.panel: Optional[DockWidget] = None
        self.toolbar: Optional[Any] = None

    def initGui(self) -> None:
        """Create the GUI elements."""
        self.settings_action = QAction("SegMap: Settings", self.iface.mainWindow())
        self.start_action = QAction("SegMap: Start", self.iface.mainWindow())

        # Set icons for the actions
        self.settings_action.setIcon(
            QIcon(":images/themes/default/mActionMapSettings.svg")
        )

        self.start_action.setIcon(QIcon(
            get_resource_path('logo.svg')
        ))

        self.settings_action.triggered.connect(self.show_settings_dialog)
        self.start_action.triggered.connect(self.activate_tool)

        # Add buttons to the toolbar
        self.toolbar = self.iface.addToolBar(f"{self.PLUGIN_NAME} Toolbar")
        self.toolbar.addAction(self.start_action)
        self.toolbar.addAction(self.settings_action)

    def unload(self) -> None:
        """Remove the plugin from QGIS."""
        self.deactivate_tool()  # Cleanup any existing controller or map tool
        if self.toolbar:
            self.toolbar.clear()
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar = None

    def show_help_dialog(self) -> None:
        """Open help page in the default web browser."""
        url = QUrl("https://github.com/titorx/segmap-qgis?tab=readme-ov-file#segmap")
        QDesktopServices.openUrl(url)

    def show_settings_dialog(self) -> None:
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.PLUGIN_NAME} Settings")
        layout = QVBoxLayout()

        api_label = QLabel("API Endpoint:")
        self.api_input = QLineEdit()
        token_label = QLabel("API Token:")
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)

        self.api_input.setText(self.api_endpoint)
        self.token_input.setText(self.api_token)

        save_button = QPushButton("Save")
        save_button.clicked.connect(lambda: self.save_settings(dialog))

        layout.addWidget(api_label)
        layout.addWidget(self.api_input)
        layout.addWidget(token_label)
        layout.addWidget(self.token_input)
        layout.addWidget(save_button)

        dialog.setLayout(layout)
        dialog.exec_()

    def save_settings(self, dialog: QDialog) -> None:
        self.api_endpoint = self.api_input.text()
        self.api_token = self.token_input.text()

        # Save settings to QGIS settings for persistence
        self.settings.setValue("SegMap/api_endpoint", self.api_endpoint)
        self.settings.setValue("SegMap/api_token", self.api_token)
        dialog.accept()

    def init_controller(self) -> None:
        if self.controller:
            self.controller.teardown()  # Cleanup any existing controller

        self.controller = ISController(
            self.api_endpoint, self.api_token,
        )

    def activate_tool(self) -> None:
        """
        Start the tool process.
        1. Open a panel on the right with more options.
        2. Provide options to start segmentation workflow and select a model.
        """
        self.deactivate_tool()  # Cleanup any existing temporary layers
        self.init_controller()

        self.panel = DockWidget(self, "SegMap Options", self.iface.mainWindow())

        models = self.controller.get_models() if self.controller else []
        # populate the model dropdown with available models
        for model in models:
            self.panel.ui.modelSelect.addItem(model['name'], model['id'])

        def update_model_selection() -> None:
            """
            Update the model description and model_id based on the selected model.
            """
            current_index = self.panel.ui.modelSelect.currentIndex()
            model_description = models[current_index].get('description', "No description available.")
            self.panel.ui.modelDescription.setText(model_description)
            self.model_id = self.panel.ui.modelSelect.currentData()

        # signal to update the model_id when the selection changes
        self.panel.ui.modelSelect.currentIndexChanged.connect(
            update_model_selection)

        self.panel.ui.modelSelect.setCurrentIndex(0)  # Default to the first model
        update_model_selection()  # Set the initial model ID

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.panel)
        self.panel.show()

        # Update state of buttons
        for button in self.panel.ui.actionBtnGroup.buttons():
            button.setEnabled(False)
            button.hide()
        self.settings_action.setEnabled(False)  # Disable "Settings" button
        self.start_action.setEnabled(False)  # Disable "Start" button

        # connecting signals
        self.panel.ui.startBtn.clicked.connect(self.enter_segmentation)
        self.panel.ui.endBtn.clicked.connect(self.exit_segmentation)
        self.panel.ui.confirmBtn.clicked.connect(self.confirm_results)
        self.panel.ui.helpBtn.clicked.connect(self.show_help_dialog)

        # check readiness of the tool
        self.panel.ui.modelSelect.currentIndexChanged.connect(
            self.check_readness
        )
        self.panel.ui.rasterSelect.currentIndexChanged.connect(
            self.check_readness
        )
        self.panel.ui.outputSelect.currentIndexChanged.connect(
            self.check_readness
        )
        self.panel.ui.outputSelect.currentIndexChanged.connect(
            self.on_class_select_changed
        )
        self.panel.ui.classSelect.select.currentIndexChanged.connect(
            self.check_readness
        )

        # Display options
        self.panel.ui.opacitySlider.valueChanged.connect(
            lambda value: (
                self.controller.segm_layer.setOpacity(value / 100.0),
                self.controller.segm_layer.triggerRepaint()
            )
        )

        # Bind shortcuts to buttons
        self.panel.ui.startBtn.setShortcut(Qt.Key_Return)
        self.panel.ui.confirmBtn.setShortcut(Qt.Key_Return)
        self.panel.ui.undoBtn.setShortcut(Qt.Key_Left)
        self.panel.ui.redoBtn.setShortcut(Qt.Key_Right)
        self.panel.ui.endBtn.setShortcut(Qt.Key_Escape)

    def check_readness(self) -> None:
        all_valid = all([
            self.panel.ui.modelSelect.currentData(),
            self.panel.ui.rasterSelect.currentData(),
            self.panel.ui.outputSelect.currentData(),
            self.panel.ui.classSelect.select.currentText()
        ])
        if all_valid:
            self.panel.ui.startBtn.setEnabled(True)
        else:
            self.panel.ui.startBtn.setEnabled(False)
            # if the segmentation is already running, terminate it
            if self.map_tool:
                self.exit_segmentation()

    def on_class_select_changed(self) -> None:
        """When output layer is selected, read classes from it and update the class selection."""
        output_layer_id = self.panel.ui.outputSelect.currentData()
        if output_layer_id:
            output_layer = QgsProject.instance().mapLayer(output_layer_id)
            classes = set()
            for feature in output_layer.getFeatures():
                class_value = feature.attribute("class")
                if class_value:
                    classes.add(class_value)

            # Update the class selection dropdown
            self.panel.ui.classSelect.select.clear()
            self.panel.ui.classSelect.select.addItems(sorted(classes))

    def enter_segmentation(self) -> None:
        """Enter the segmentation workflow."""
        # connect click events to segment handler
        self.map_tool = QgsMapToolEmitPoint(self.canvas)
        self.map_tool.canvasClicked.connect(self.segment)
        self.canvas.setMapTool(self.map_tool)

        # Insert tmp layers
        QgsProject.instance().addMapLayer(self.controller.segm_layer)
        QgsProject.instance().addMapLayer(self.controller.click_layer)
        self.controller.segm_layer.setFlags(QgsMapLayer.Private)
        self.controller.click_layer.setFlags(QgsMapLayer.Private)

        # Disable buttons
        self.panel.ui.startBtn.hide()  # Hide "Start" button
        self.panel.ui.rasterSelect.setEnabled(False)  # Disable raster layer selection
        self.panel.ui.outputSelect.setEnabled(False)  # Disable output layer selection

        # Show and enable all buttons from action group
        for btn in self.panel.ui.actionBtnGroup.buttons():
            btn.setEnabled(True)
            btn.show()

        # Connect redo and undo actions
        self.panel.ui.undoBtn.clicked.connect(self.controller.undo)
        self.panel.ui.redoBtn.clicked.connect(self.controller.redo)

    def segment(self, point: QPoint, button: Qt.MouseButton) -> None:
        """Handle clicks on the map canvas to segment the raster layer."""
        if not self.api_endpoint or not self.api_token:
            self.iface.messageBar().pushMessage(
                "Error", "API settings are not configured.", level=3
            )
            return

        # Create a new feature for the click
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        feature.setAttributes([1 if button == Qt.LeftButton else 0])

        # trigger segmentation
        try:
            raster_layer_id = self.panel.ui.rasterSelect.currentData()
            raster_layer = QgsProject.instance().mapLayer(raster_layer_id)
            self.controller.segment(self.model_id, raster_layer, feature)
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", f"{str(e)}", level=Qgis.Critical
            )

    def confirm_results(self) -> None:
        """
        Save the segmentation results to the selected layer.
        """
        # Save features from the segmentation layer to the selected layer
        if self.controller and \
            self.panel.ui.outputSelect.currentData() and\
            self.panel.ui.classSelect.select.currentText():

            output_layer_id = self.panel.ui.outputSelect.currentData()
            output_layer = QgsProject.instance().mapLayer(output_layer_id)

            selected_class = self.panel.ui.classSelect.select.currentText()

            # if segm_layer and output_layer are not the same crs,
            # transform the segm_layer to the output_layer crs
            src_crs = self.controller.segm_layer.crs()
            dest_crs = output_layer.crs()
            if src_crs != dest_crs:
                self.controller.segm_layer.setCrs(dest_crs)

            for feature in self.controller.segm_layer.getFeatures():
                new_feature = QgsFeature(QgsFields([
                    QgsField("class", QMetaType.Type.QString)
                ]))
                new_feature.setGeometry(feature.geometry())
                new_feature.setAttribute("class", selected_class)
                output_layer.dataProvider().addFeature(new_feature)
            output_layer.updateExtents()
            output_layer.triggerRepaint()

        # Cleanup the controller
        self.init_controller()
        # Insert tmp layers
        QgsProject.instance().addMapLayer(self.controller.segm_layer)
        QgsProject.instance().addMapLayer(self.controller.click_layer)
        self.controller.segm_layer.setFlags(QgsMapLayer.Private)
        self.controller.click_layer.setFlags(QgsMapLayer.Private)

    def exit_segmentation(self) -> None:
        "Reverse enter_segmentation to exit the segmentation workflow."
        # Disconnect the map tool
        if self.map_tool:
            self.map_tool.deactivate()
            self.map_tool = None
            self.iface.actionPan().trigger()  # Switch back to pan tool

        # Remove temporary layers
        self.init_controller()

        # Disable buttons
        for button in self.panel.ui.actionBtnGroup.buttons():
            button.setEnabled(False)
            button.hide()

        # Enable buttons
        self.panel.ui.startBtn.show()
        self.panel.ui.rasterSelect.setEnabled(True)
        self.panel.ui.outputSelect.setEnabled(True)

    def deactivate_tool(self) -> None:
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
