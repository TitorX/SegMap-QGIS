import os
import base64
import time
from collections import OrderedDict
import numpy as np
import cv2
import torch
from fastapi.responses import JSONResponse
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from isegm.inference.predictors import get_predictor as build_predictor
from isegm.inference import utils
from isegm.inference import clicker


DEBUG = False


MODELS = OrderedDict(
    [
        (
            "C+L ICL",
            {
                "name": "C+L ICL",
                "description": """CFR-ICL model trained on COCO and LVIS datasets. It uses a ViT-H model as backbone.
""",
                "weights": "coco_lvis_icl_vit_huge.pth",
                "input_channels": 3,
            },
        ),
        (
            "C+L RITM",
            {
                "name": "C+L RITM",
                "description": "Lightning RITM model. It runs fast but is less accurate",
                "weights": "coco_lvis_h18s_itermask.pth",
                "input_channels": 3,
            },
        ),

    ]
)
DEVICE = "cuda"
PREDICTOR_POOL_CACHE_SIZE = 5
PREDICTOR_POOL = OrderedDict()


def get_predictor(model_name):
    if model_name in PREDICTOR_POOL:
        return PREDICTOR_POOL[model_name]

    model_info = MODELS.get(model_name)
    if model_info is None:
        raise ValueError(f"No model with name {model_name}")

    if model_name == "SAM":
        from segment_anything import sam_model_registry

        model = sam_model_registry["default"](
            checkpoint=os.path.join("weights", model_info["weights"])
        )
        model.to(DEVICE)

        mode = "SAM"
    else:
        model = utils.load_is_model(
            os.path.join("weights", model_info["weights"]),
            DEVICE,
            True if "RITM" in model_name else False,
            cpu_dist_maps=True,
        )

        mode = "NoBRS"

    predictor = build_predictor(
        model,
        mode,
        DEVICE,
        zoom_in_params={"target_size": (448, 448), "skip_clicks": -1},
        predictor_params={
            "net_clicks_limit": 20,
            "cascade_step": 0,
            "cascade_adaptive": False,
        },
    )

    if model_name == "SAM":
        predictor.transforms = []

    if len(PREDICTOR_POOL) >= PREDICTOR_POOL_CACHE_SIZE:
        drop = list(PREDICTOR_POOL.keys())[1]
        del PREDICTOR_POOL[drop]

    PREDICTOR_POOL[model_name] = predictor

    return predictor


def mask_to_polygon(binary_mask):
    """
    Converts a binary mask (0, 255) to a list of polygons in GeoJSON format, considering holes.

    Args:
        binary_mask (np.ndarray): A binary mask of shape (height, width) with values 0 or 255.

    Returns:
        list: A list of GeoJSON-like dictionaries, each containing a polygon representation with holes.
    """
    contours, hierarchy = cv2.findContours(binary_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []

    hierarchy = hierarchy[0]
    polygons = []

    for i, contour in enumerate(contours):
        polygon = contour.squeeze().tolist()
        if len(polygon) < 3:
            continue  # Skip invalid polygons

        # filter small polygons
        if cv2.contourArea(contour) < 100:
            continue

        # Ensure the polygon is closed
        if polygon[0] != polygon[-1]:
            polygon.append(polygon[0])

        # GeoJSON requires exterior rings to be counter-clockwise and holes to be clockwise
        if hierarchy[i][3] == -1:  # No parent, it's an exterior ring
            if not is_counter_clockwise(polygon):
                polygon.reverse()
            polygons.append({"exterior": polygon, "holes": []})
        else:  # Has a parent, it's an interior ring (hole)
            if is_counter_clockwise(polygon):
                polygon.reverse()
            parent_index = hierarchy[i][3]
            if parent_index < len(polygons):  # Ensure the parent exists
                # Append the hole to the parent polygon
                polygons[parent_index]["holes"].append(polygon)

    geojson_list = []
    for poly in polygons:
        geojson =  {
            "type": "Polygon",
            "coordinates": [poly["exterior"]] + poly["holes"]
        }
        geojson_list.append(geojson)

    return geojson_list


def polygon_to_mask(polygons, width, height):
    """
    Converts a list of polygons in GeoJSON format to a binary mask (0, 255), considering holes.

    Args:
        polygons (list): A list of GeoJSON-like dictionaries, each containing a polygon representation.
        width (int): The width of the output mask.
        height (int): The height of the output mask.

    Returns:
        np.ndarray: A binary mask of shape (height, width) with values 0 or 255.
    """
    binary_mask = np.zeros((height, width), dtype=np.uint8)

    for polygon in polygons:
        if polygon["type"] == "Polygon":
            coordinates = polygon["coordinates"]
            exterior = np.array(coordinates[0], dtype=np.int32)
            cv2.fillPoly(binary_mask, [exterior], 255)

            for hole in coordinates[1:]:
                hole_array = np.array(hole, dtype=np.int32)
                cv2.fillPoly(binary_mask, [hole_array], 0)

    return binary_mask


def is_counter_clockwise(polygon):
    """
    Determines if a polygon is wound counter-clockwise.

    Args:
        polygon (list): A list of [x, y] points representing the polygon.

    Returns:
        bool: True if the polygon is counter-clockwise, False otherwise.
    """
    area = 0
    for i in range(len(polygon) - 1):
        x1, y1 = polygon[i]
        x2, y2 = polygon[i + 1]
        area += (x2 - x1) * (y2 + y1)
    return area > 0


def segment(model_name, image, click_points, prev_prediction=None):
    clicks = clicker.Clicker()
    for i in click_points:
        clicks.add_click(clicker.Click(is_positive=i[2], coords=(i[1], i[0])))

    predictor = get_predictor(model_name)

    predictor.set_input_image(image)
    if model_name == "SAM":
        predictor.low_res_masks = prev_prediction

    if torch.is_tensor(prev_prediction):
        prev_prediction = prev_prediction.to(DEVICE)

    with torch.no_grad():
        pred_prob = predictor.get_prediction(clicks, prev_prediction)

    if model_name == "SAM":
        prev_prediction = getattr(predictor, "low_res_masks")
    else:
        prev_prediction = predictor.prev_prediction
        prev_prediction = prev_prediction.detach().cpu()

    threshold = 0.5
    while threshold > 0:
        pred_mask = (pred_prob > threshold).astype(int).astype(np.uint8)
        if pred_mask.sum() > 0:
            break
        else:
            threshold -= 0.05

    pred_mask *= 255
    cnts = mask_to_polygon(pred_mask)
    return cnts


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_token = os.getenv("BEARER_TOKEN", None)
if bearer_token:
    security = HTTPBearer()

    @app.middleware("http")
    async def verify_bearer_token(request, call_next):
        if request.url.path not in ["/v1/models"]:  # Exclude urls
            credentials: HTTPAuthorizationCredentials = await security(request)
            if not credentials or credentials.credentials != bearer_token:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Access denied, invalid token"}
                )
        response = await call_next(request)
        return response


class ModelResponse(BaseModel):
    id: str
    name: str
    input_channels: int
    description: str


class SegmentRequest(BaseModel):
    model_id: str
    image: str
    clicks: list
    previous_mask: list
    width: int
    height: int
    channel: int


class SegmentResponse(BaseModel):
    segmentation: list
    model_used: str
    processing_time: float


@app.get("/v1/models", response_model=list[ModelResponse])
def get_models():
    models = [
        {
            "id": k,
            "name": v["name"],
            "input_channels": v["input_channels"],
            "description": v["description"],
        }
        for k, v in MODELS.items()
    ]
    return models


@app.post("/v1/segment", response_model=SegmentResponse)
@app.exception_handler(RequestValidationError)
def segment_endpoint(request: SegmentRequest):
    # Parse image from base64
    width = request.width
    height = request.height
    channel = request.channel
    image = np.frombuffer(
        base64.b64decode(request.image),
        dtype=np.uint8
    ).reshape((channel, height, width)).transpose((1, 2, 0))

    if len(request.previous_mask) > 0:
        prev_mask = polygon_to_mask(
            request.previous_mask, width, height
        )

        prev_mask = torch.from_numpy(prev_mask)
        prev_mask = prev_mask.unsqueeze(0).unsqueeze(0)
    else:
        prev_mask = None

    processing_time = time.time()
    cnts = segment(
        request.model_id, image, request.clicks, prev_mask
    )
    processing_time = time.time() - processing_time

    # Debugging block to save images and clicks on segmentation map
    if DEBUG:
        if prev_mask is not None:
            debug_prev_mask_path = "debug_prev_mask.png"
            cv2.imwrite(debug_prev_mask_path, prev_mask.squeeze().cpu().numpy())
        else:
            # create a blank image
            prev_mask = np.zeros((height, width), dtype=np.uint8)
            cv2.imwrite("debug_prev_mask.png", prev_mask)

        debug_image_path = "debug_image.png"
        cv2.imwrite(debug_image_path, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))

        debug_segmentation_path = "debug_segmentation.png"
        segmentation_mask = polygon_to_mask(cnts, width, height)
        segmentation_mask = cv2.cvtColor(segmentation_mask, cv2.COLOR_GRAY2RGB)

        # Add clicks to the segmentation map for debugging
        for click in request.clicks:
            x, y, is_positive = int(click[0]), int(click[1]), int(click[2])
            color = (0, 255, 0) if is_positive else (0, 0, 255)
            cv2.circle(segmentation_mask, (x, y), 5, color, -1)

        cv2.imwrite(debug_segmentation_path, segmentation_mask)

    response = {
        "segmentation": cnts,
        "model_used": request.model_id,
        "processing_time": processing_time,
    }
    return response
