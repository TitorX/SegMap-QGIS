from typing import List, Dict
import os
import requests
from qgis.core import (
    QgsVectorLayer,
    QgsRasterLayer,
    QgsField,
    QgsFillSymbol,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsMarkerSymbol,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsProject,
)
from qgis.utils import iface
from PyQt5.QtCore import QMetaType
from helper_func import (
    read_displayed_raster_data, encode_image,
)


class ISController:
    """
    This class handles interactive image segmentation using RESTful API endpoints.

    Coordinate System:
    - OpenCV format is used for all coordinates.
    - `x` increases from left to right (horizontal coordinate).
    - `y` increases from top to bottom (vertical coordinate).
    - The origin (0, 0) is at the top-left corner of the image.

    API Data format details:
    - Polygon: GeoJSON format with coordinates in the order of [x, y].
        Example:
        {
            "type": "Polygon",
            "coordinates": [
                // Exterior ring (counter-clockwise)
                [
                [100.0, 0.0], [101.0, 0.0], [101.0, 1.0], [100.0, 1.0], [100.0, 0.0]
                ],
                // Hole 1 (clockwise)
                [
                [100.8, 0.8], [100.8, 0.2], [100.2, 0.2], [100.2, 0.8], [100.8, 0.8]
                ],
                // Hole 2 (clockwise)
                [
                [100.4, 0.4], [100.6, 0.4], [100.6, 0.6], [100.4, 0.6], [100.4, 0.4]
                ]
            ]
        }
    - Clicks: A list of [x, y, is_positive], where x and y are the coordinates of the click,
        and is_positive is 1 for positive clicks and 0 for negative clicks.
        Example:
        [
            [100, 200, 1],  # Positive click at (100, 200)
            [150, 250, 0],  # Negative click at (150, 250)
            ...
        ]
    - Image: A base64-encoded string representing the image. The image format is
        channel-first (C, H, W) and must be reshaped into a 1-D array before transmission.
        The server will reconstruct the original shape.
        Ensure the image shape matches the model's input requirements.
    """

    def __init__(
        self,
        api_url: str,
        token: str,
    ):
        self.api_url = api_url
        self.token = token
        self.current_model = None
        self.canvas = iface.mapCanvas()

        # Set up the style for the clicks layer,
        # use point symbol with colors depending on click type
        # 0: red, 1: green
        click_renderer = QgsCategorizedSymbolRenderer(
            "click_type",
            [
                QgsRendererCategory(
                    0, QgsMarkerSymbol.createSimple({"color": "red"}),
                    "Negative Click"
                ),
                QgsRendererCategory(
                    1,
                    QgsMarkerSymbol.createSimple({"color": "green"}),
                    "Positive Click",
                ),
            ],
        )

        # Set style for the segmentation layer
        segm_symbol = QgsFillSymbol.createSimple(
            {
                "color": "0,0,255,255,rgb:0,0,1,0.5",
            }
        )

        # Initialize QGIS layers with the canvas CRS
        crs = self.canvas.mapSettings().destinationCrs()
        self.click_layer = QgsVectorLayer(
            f"Point?crs={crs.authid()}", "Tmp Clicks", "memory"
        )
        self.click_layer.dataProvider().addAttributes(
            [QgsField("click_type", QMetaType.Type.Int)]
        )

        self.click_layer.updateFields()
        self.click_layer.setRenderer(click_renderer)

        self.segm_layer = QgsVectorLayer(
            f"Polygon?crs={crs.authid()}", "Tmp Segmentation", "memory"
        )
        self.segm_layer.renderer().setSymbol(segm_symbol)

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_models(self) -> List[Dict]:
        """Retrieve a list of available models for segmentation."""
        response = requests.get(os.path.join(self.api_url, "models"), headers=self._headers())
        response.raise_for_status()
        return response.json()

    def add_click(self, feature: QgsFeature):
        """Add a click feature to the click layer."""
        self.click_layer.dataProvider().addFeature(feature)
        self.click_layer.updateExtents()
        self.click_layer.triggerRepaint()

    def segment(self, model_id, raster_layer) -> Dict:
        """Perform image segmentation using the current model and manage clicks/mask."""

        # Read image data from the current canvas
        image = read_displayed_raster_data(raster_layer, self.canvas)
        base64_image = encode_image(image)

        # Collect clicks from the click layer
        clicks = self._get_click_list()

        # Prepare payload
        payload = {
            "model_id": model_id,
            "image": base64_image,
            "clicks": clicks,
            "width": image.shape[1],
            "height": image.shape[0],
            "channel": image.shape[2],
        }

        # if self.segm_layer has feature, convert it to previous_mask in the payload
        if False:
        # if self.segm_layer.featureCount() > 0:
            payload["previous_mask"] = self._segm_layer_to_geojson()
        else:
            payload["previous_mask"] = []

        response = requests.post(
            os.path.join(self.api_url, "segment"), json=payload, headers=self._headers()
        )
        response.raise_for_status()
        result = response.json()

        # Save segmentation result to the segmentation layer
        self._geojson_to_segm_layer(result["segmentation"])

    def _geojson_to_segm_layer(self, segm: List[Dict]):
        """Save segmentation result to the segmentation layer."""
        provider = self.segm_layer.dataProvider()
        provider.truncate()  # Clear existing features

        target_crs = self.segm_layer.crs()

        for polygon in segm:
            feature = QgsFeature()

            geo_polygon = []
            for ring in polygon["coordinates"]:
                qgis_ring = []
                for point in ring:
                    # Convert pixel coordinates to geo coordinates
                    geo_x, geo_y = self._pixel2geo_coords(
                        point[0], point[1], target_crs
                    )
                    qgis_ring.append(QgsPointXY(geo_x, geo_y))
                geo_polygon.append(qgis_ring)

            geometry = QgsGeometry.fromPolygonXY(geo_polygon)
            feature.setGeometry(geometry)

            provider.addFeature(feature)

        self.segm_layer.updateExtents()
        self.segm_layer.triggerRepaint()

    def _segm_layer_to_geojson(self):
        """Export all features in segm_layer to GeoJSON format."""
        features = list(self.segm_layer.getFeatures())
        geojson_features = []

        for feature in features:
            geometry = feature.geometry()
            polygon = []

            for ring in geometry.asPolygon():
                ring_points = []
                for point in ring:
                    # Convert geo coordinates to pixel coordinates
                    pixel_x, pixel_y = self._geo2pixel_coords(point, self.segm_layer.crs())
                    ring_points.append([pixel_x, pixel_y])
                polygon.append(ring_points)

            geojson_features.append({
                "type": "Polygon",
                "coordinates": polygon
            })

        return geojson_features

    def _get_click_list(self):
        """Convert click_layer to a list of click coordinates."""
        clicks = []
        for feature in self.click_layer.getFeatures():
            geometry = feature.geometry()
            if geometry.isEmpty():
                continue

            point = geometry.asPoint()
            click_type = feature["click_type"]

            # Convert geo coordinates to pixel coordinates
            pixel_x, pixel_y = self._geo2pixel_coords(point, self.click_layer.crs())
            clicks.append([pixel_x, pixel_y, click_type])

        return clicks

    def _geo2pixel_coords(
            self, point: QgsPointXY,
            point_crs: QgsCoordinateReferenceSystem
        ) -> List[float]:
        """Convert geo coordinates to pixel coordinates."""
        # if point crs is not the same as the canvas crs, transform it to canvas crs
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        if point_crs != canvas_crs:
            transform = QgsCoordinateTransform(
                point_crs, canvas_crs, QgsProject.instance()
            )
            point = transform.transform(point)

        extent = self.canvas.extent()

        # Convert to pixel coordinates
        pixel_x = (point.x() - extent.xMinimum()) / extent.width() * self.canvas.width()
        pixel_y = (extent.yMaximum() - point.y()) / extent.height() * self.canvas.height()

        return [pixel_x, pixel_y]

    def _pixel2geo_coords(
        self, pixel_x: float, pixel_y: float,
        target_crs: QgsCoordinateReferenceSystem
    ) -> List[float]:
        """Convert pixel coordinates to geo coordinates."""
        extent = self.canvas.extent()

        # Convert to geo coordinates
        geo_x = extent.xMinimum() + pixel_x / self.canvas.width() * extent.width()
        geo_y = extent.yMaximum() - pixel_y / self.canvas.height() * extent.height()

        canvas_crs = self.canvas.mapSettings().destinationCrs()
        # Transform to target CRS if necessary
        if target_crs != canvas_crs:
            point = QgsPointXY(geo_x, geo_y)
            transform = QgsCoordinateTransform(
                canvas_crs,
                target_crs,
                QgsProject.instance(),
            )
            point = transform.transform(point)
            geo_x, geo_y = point.x(), point.y()

        return [geo_x, geo_y]

    def teardown(self):
        """Remove layers from the QGIS project."""
        QgsProject.instance().removeMapLayer(self.click_layer.id())
        QgsProject.instance().removeMapLayer(self.segm_layer.id())
        iface.mapCanvas().refresh()
