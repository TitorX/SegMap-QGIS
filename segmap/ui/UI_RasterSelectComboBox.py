from PyQt5.QtWidgets import QComboBox
from PyQt5.QtCore import pyqtSlot as Slot
from qgis.core import QgsProject, QgsRasterLayer


class UI_RasterSelectComboBox(QComboBox):
    DUMB = "-- Empty --"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.updateLayerItems()  # Initialize with current raster layers
        QgsProject.instance().layersRemoved.connect(self.on_layers_removed)

    @Slot('QStringList')
    def on_layers_removed(self, layer_ids: list[str]):
        current_selection = self.currentData()
        if current_selection in layer_ids:
            # If the current selection is being removed, reset
            self.updateLayerItems()

    def updateLayerItems(self):
        """
        Update the dropdown menu with the latest raster layers from QGIS.
        """
        # Store the current selection
        current_selection = self.currentData()

        # Clear the current items in the dropdown
        self.clear()

        layer_items = [
            (layer.name() + f"[{layer.id()[-4:]}]", layer.id())
            for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsRasterLayer) and  # Check if the layer is a raster layer
               QgsProject.instance().layerTreeRoot().findLayer(layer.id())  # Check if the layer is still present in the project
        ]

        # Add a placeholder item
        self.addItem(self.DUMB, None)  # No user data for placeholder
        self.setCurrentIndex(0)  # Reset to the placeholder

        # If there valid layers, add them to the dropdown
        for name, layer_id in layer_items:
            self.addItem(name, layer_id)

        # Restore the previous selection if it still exists
        if current_selection and current_selection in [self.itemData(i) for i in range(self.count())]:
            self.setCurrentIndex(self.findData(current_selection))

    def showPopup(self):
        self.updateLayerItems()
        super().showPopup()
