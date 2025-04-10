# SegMap API Documentation

This document describes the RESTful API for interactive image segmentation with secure model management. The API is designed to be stateless, use bearer token authentication (OAuth2), and follow semantic versioning (`/v1` in the URL). All requests and responses use JSON format with UTC timestamps, and standard HTTP status codes are employed for error handling.

## Data Structures

All coordinate systems follow OpenCV's format:
- `x` increases from left to right (horizontal coordinate).
- `y` increases from top to bottom (vertical coordinate).
- The coordinate system is in pixel space, which means it counts the number of pixels. Coordinates can be either float or int, but they will eventually be converted to int during processing.

### 1. Polygon
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

### 2. Clicks
Clicks are represented as an array of `[x, y, is_positive]`, where:
- `is_positive` is `1` for positive clicks and `0` for negative clicks.

Example:
```json
[
  [100, 200, 1],  // Positive click at (100, 200)
  [150, 250, 0]   // Negative click at (150, 250)
]
```

### 3. Image
Images are provided as base64-encoded strings. The image format is channel-first `(C, H, W)` and must be reshaped into a 1-D array before transmission. The server will reconstruct the original shape. The image shape must match the model's input shape.

---

## Endpoints

### 1. Model Discovery `GET /models`
Retrieve a list of available models for segmentation.

#### Request
```http
GET /models HTTP/1.1
Authorization: Bearer <token>
Accept: application/json
```

#### Response
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "models": [
    {
      "id": "seg-model-v3",
      "name": "Segment Anything Model v3",
      "version": "3.1.0",
      "input_shape": {
        "channels": 3,
        "width": 512,
        "height": 512
      },
      "description": "Interactive segmentation model with click support",
      "status": "active",
      "created_at": "2025-01-15"
    }
  ]
}
```

---

### 2. Image Segmentation `POST /segment`
Perform image segmentation using a specified model.

#### Request
```http
POST /segment HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>
Accept: application/json

{
  "model_id": "seg-model-v3",
  "image": "base64-encoded-string",
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

#### Response
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
  "model_used": "seg-model-v3",
  "processing_time": 0.45,
  "timestamp": "2025-04-08T22:47:32Z"
}
```

---

## Error Handling
Standard error response format:
```json
{
  "error": {
    "code": "invalid_shape",
    "message": "Image size not supported by model"
  }
}
```

**Common Errors:**
| Status | Error Code           | Suggested Action                     |
|--------|----------------------|--------------------------------------|
| 400    | invalid_shape        | Verify image shape doesn't match     |
| 401    | invalid_token        | Renew authentication token           |
| 403    | model_access_denied  | Request model permissions from admin |
| 404    | model_not_found      | Check available models via `/models` |
| 500    | internal_error       | Retry with exponential backoff       |
