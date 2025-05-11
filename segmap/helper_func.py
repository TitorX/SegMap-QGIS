import os
import base64
from PyQt5.QtGui import QImage
import numpy as np
from qgis.core import (
    QgsMapSettings,
    QgsMapRendererParallelJob,
    QgsProject,
    QgsRasterLayer,
)
from qgis.gui import QgsMapCanvas
import tempfile
from PIL import Image


def qimage_to_numpy_rgb(image: QImage) -> np.ndarray:
    """Convert a QImage to a NumPy array (RGB only)."""
    # Ensure the image is in RGB format
    image = image.convertToFormat(QImage.Format_RGB888)

    # Save QImage to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        temp_filename = tmp_file.name

    image.save(tmp_file.name)

    # Load the temporary file into a NumPy array using PIL
    pil_image = Image.open(tmp_file.name)
    array = np.array(pil_image)

    # Delete the temporary file
    try:
        os.remove(temp_filename)
    except OSError:
        pass

    return array


def encode_image(image: np.ndarray) -> str:
    """Encode a 3-channel NumPy image to a base64-encoded string"""
    channel_first = np.transpose(image, (2, 0, 1))  # Change to channel first
    flattened_data = channel_first.flatten()
    base64_encoded = base64.b64encode(flattened_data).decode('utf-8')
    return base64_encoded


def read_displayed_raster_data(raster_layer: QgsRasterLayer, canvas: QgsMapCanvas) -> np.ndarray:
    """Read raster data from the displayed raster layer"""

    map_settings = QgsMapSettings()
    map_settings.setDestinationCrs(canvas.mapSettings().destinationCrs())
    map_settings.setTransformContext(QgsProject.instance().transformContext())
    map_settings.setOutputSize(canvas.size())
    map_settings.setExtent(canvas.extent())
    map_settings.setLayers([raster_layer])

    job = QgsMapRendererParallelJob(map_settings)
    job.start()
    job.waitForFinished()

    image = job.renderedImage()
    return qimage_to_numpy_rgb(image)
