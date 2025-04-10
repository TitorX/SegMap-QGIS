from PyQt5.QtWidgets import QComboBox
from PyQt5.QtCore import QMetaType, pyqtSlot as Slot
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsField,
    QgsMapLayer
)
from qgis.utils import iface


class UI_OutputLayerSelectComboBox(QComboBox):
    DUMB = "-- Empty --"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.updateLayerItems()  # Initialize with current polygon layers
        self.currentTextChanged.connect(self.handleSelection)
        QgsProject.instance().layersRemoved.connect(self.on_layers_removed)

    @Slot('QStringList')
    def on_layers_removed(self, layer_ids: list[str]):
        current_selection = self.currentData()
        if current_selection in layer_ids:
            # If the current selection is being removed, reset
            self.updateLayerItems()

    def showPopup(self):
        """
        Override the showPopup method to refresh the dropdown items
        with the latest polygon layers from the project.
        """
        self.updateLayerItems()
        super().showPopup()

    def updateLayerItems(self):
        """
        Update the dropdown menu with the latest vector layers of polygon type.
        """
        # Store the current selection
        current_selection = self.currentData()

        # Clear the current items in the dropdown
        self.clear()

        layer_items = [
            (layer.name() + f"[{layer.id()[-4:]}]", layer.id())
            for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsVectorLayer) and  # Check if the layer is a vector layer
                layer.geometryType() == QgsWkbTypes.PolygonGeometry and  # Check if the layer is a polygon layer
                QgsProject.instance().layerTreeRoot().findLayer(layer.id()) and  # Check if the layer is still present in the project
                not (layer.flags() & QgsMapLayer.Private)  # Exclude private layers
        ]

        # Add a placeholder item
        self.addItem(self.DUMB, None)  # No user data for placeholder
        self.setCurrentIndex(0)  # Reset to the placeholder

        # If there are polygon layers, add them to the dropdown
        for name, layer_id in layer_items:
            self.addItem(name, layer_id)

        # Add the "Create New" option
        self.addItem("Create New", None)  # No user data for "Create New"

        # Restore the previous selection if it still exists
        if current_selection and current_selection in [self.itemData(i) for i in range(self.count())]:
            self.setCurrentIndex(self.findData(current_selection))

    @Slot()
    def handleSelection(self):
        """
        Handle the selection of the "Create New" option to create a new polygon layer.
        """
        if self.currentText() == "Create New":
            # If "Create New" is selected, create a new polygon layer

            # Use the current canvas CRS to create a new polygon layer
            canvas = iface.mapCanvas()
            crs = canvas.mapSettings().destinationCrs()

            output_layer = QgsVectorLayer(
                f"Polygon?crs={crs.authid()}", "Segmentation Results", "memory"
            )
            # Add the new layer to the project
            QgsProject.instance().addMapLayer(output_layer)
            # Update the dropdown to include the new layer
            self.addItem(
                output_layer.name() + f"[{output_layer.id()[-4:]}]",
                output_layer.id()
            )
            self.setCurrentIndex(self.count() - 1)  # Select the new layer 
        elif self.currentData() is None:
            # If DUMB is selected, do nothing
            return
        else:
            # If a layer is selected, get the corresponding QgsVectorLayer
            output_layer = QgsProject.instance().mapLayer(self.currentData())

        # if the output_layer has no field called "class",
        # add a new field called "class" of type string
        if output_layer.fields().indexOf("class") == -1:
            output_layer.dataProvider().addAttributes(
                [QgsField("class", QMetaType.Type.QString)]
            )
            output_layer.updateFields()
