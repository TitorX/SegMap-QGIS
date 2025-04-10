# SegMap Server Documentation

## Running the Server

To run the SegMap server, follow these steps:

### 1. Build the Docker Image
Use the provided `Dockerfile` to build the Docker image:
```bash
docker build -t segmap-server .
```

### 2. Run the Docker Container
The SegMap server requires access to a folder containing model weights. This folder must be mounted to `/app/weights` inside the container. Additionally, the server uses a bearer token for authentication, which must be set using the `BEARER_TOKEN` environment variable. Since the application requires an NVIDIA GPU for deep learning, ensure that GPU resources are assigned to the container.

Run the container with the following command:
```bash
docker run --gpus all -e BEARER_TOKEN=<your_token> -v /path/to/weights:/app/weights -p 8080:80 segmap-server
```

Replace `<your_token>` with your desired bearer token and `/path/to/weights` with the path to your local weights folder. The server will be accessible at `http://localhost:8080`.

### 3. Accessing the Server from QGIS-plugin
To access the SegMap server from the QGIS plugin, ensure that the plugin is configured to point to the server's URL (e.g., `http://localhost:8080`) and has `BEARER_TOKEN` set.

### 4. Preparing the Weights Folder

The SegMap server requires a folder containing model weights and a `models.yaml` file to function correctly. This folder must be mounted to `/app/weights` inside the Docker container during runtime.

#### Folder Structure
Ensure your weights folder is structured as follows:
```
weights/
├── models.yaml
├── coco_lvis_icl_vit_huge.pth
```

- `models.yaml`: A YAML file that defines the available models and their corresponding weights.
- `*.pth` : Weight files for the models.

#### `models.yaml` Format
The `models.yaml` file specifies the models available for segmentation. Each model entry includes:
- `name`: The name of the model.
- `input_channels`: The number of input channels the model expects.
- `description`: A brief description of the model.
- `weights`: The filename of the model's weight file.

Example:
```yaml
CFR-ICL:
  name: "CFR-ICL"
  input_channels: 3
  description: "A model for general-purpose segmentation tasks. Use ViT-H backbone"
  weights: "coco_lvis_icl_vit_huge.pth"
```

#### Downloading the Weights
You can download the weights from the following repositories:
- [CFR-ICL](https://github.com/TitorX/CFR-ICL-Interactive-Segmentation)
- [RITM](https://github.com/SamsungLabs/ritm_interactive_segmentation)

After downloading, place the weight files and `models.yaml` in the `weights/` folder as shown above.

## API Overview

This section describes the RESTful API for interactive image segmentation with secure model management. The API is designed to be stateless, use bearer token authentication. All requests and responses use JSON format and standard HTTP status codes are employed for error handling.

### Data Structures

All coordinate systems follow OpenCV's format:
- `x` increases from left to right (horizontal coordinate).
- `y` increases from top to bottom (vertical coordinate).
- The coordinate system is in pixel space, which means it counts the number of pixels. Coordinates can be either float or int, but they will eventually be converted to int during processing.

```
                  x
   (0,0) +----------------->
         | 
      y  | 
         | 
         | 
         v
```

This diagram follows the OpenCV coordinate system format.

#### 1. Polygon
Polygons are represented in GeoJSON format. Each polygon contains an exterior ring and zero or more interior rings (holes). The structure is as follows:
- The `type` field is always `"Polygon"`.
- The `coordinates` field is an array of arrays:
  - The first array represents the **exterior ring**.
  - Subsequent arrays represent **interior rings** (holes).
  - Each array contains a sequence of `[x, y]` points.

Example:
```json
{
  "type": "Polygon",
  "coordinates": [
    [[100, 200], [150, 250], [200, 200], [100, 200]],  // Exterior ring
    [[120, 220], [130, 240], [140, 220], [120, 220]]   // Interior ring (hole)
  ]
}
```

#### 2. Clicks
Clicks are represented as an array of `[x, y, is_positive]`, where:
- `is_positive` is `1` for positive clicks and `0` for negative clicks.

Example:
```json
[
  [100, 200, 1],  // Positive click at (100, 200)
  [150, 250, 0]   // Negative click at (150, 250)
]
```

#### 3. Image
Images are provided as base64-encoded strings. The image format is channel-first `(C, H, W)` and must be reshaped into a 1-D array before transmission. The server will reconstruct the original shape.

---

### Endpoints

#### 1. Model Discovery `GET /v1/models`
Retrieve a list of available models for segmentation.

##### Request
```http
GET /models HTTP/1.1
Authorization: Bearer <token>
Accept: application/json
```

##### Response
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "models": [
    {
      "id": "CFR-ICL-ViT-H",
      "name": "CFR-ICL ViT-H",
      "input_channels": 3,
      "description": "A model for general-purpose segmentation tasks. Use ViT-H backbone",
    }
  ]
}
```

---

#### 2. Image Segmentation `POST /v1/segment`
Perform image segmentation using a specified model.

##### Request
```http
POST /segment HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>
Accept: application/json

{
  "model_id": "CFR-ICL-ViT-H",
  "image": "[base64-encoded-string]",
  "clicks": [
    [100, 200, 1],  // Positive click
    [150, 250, 0]   // Negative click
  ],
  "previous_mask": [
    {
      "type": "Polygon",
      "coordinates": [
        [[100, 200], [150, 250], [200, 200], [100, 200]],  // Exterior ring
        [[120, 220], [130, 240], [140, 220], [120, 220]]   // Interior ring (hole)
      ]
    },
    {
      "type": "Polygon",
      "coordinates": [
        [[300, 400], [350, 450], [400, 400], [300, 400]]  // Another polygon
      ]
    }
  ],
  "width": 512,
  "height": 512,
  "channel": 3
}
```

##### Response
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "segmentation": [
    {
      "type": "Polygon",
      "coordinates": [
        [[110, 210], [160, 260], [210, 210], [110, 210]],  // Exterior ring
        [[115, 215], [155, 255], [165, 215], [115, 215]]   // Interior ring (hole)
      ]
    },
    {
      "type": "Polygon",
      "coordinates": [
        [[310, 410], [360, 460], [410, 410], [310, 410]]  // Another polygon
      ]
    }
  ],
  "model_used": "CFR-ICL-ViT-H",
}
```

---

### Error Handling

**Common Errors:**
| Status | Error Code           | Suggested Action                     |
|--------|----------------------|--------------------------------------|
| 401    | invalid_token        | Renew authentication token           |
| 403    | model_access_denied  | Request model permissions from admin |
| 500    | internal_error       | Retry with exponential backoff       |
