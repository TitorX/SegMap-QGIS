# Interactive Image Segmentation API

This document describes the RESTful API for interactive image segmentation with secure model management. The API is designed to be stateless, use bearer token authentication (OAuth2), and follow semantic versioning (`/v1` in the URL). All requests and responses use JSON format with UTC timestamps, and standard HTTP status codes are employed for error handling.

## Data Structures

All coordinate systems follow OpenCV's format:
- `x` increases from left to right (horizontal coordinate).
- `y` increases from top to bottom (vertical coordinate).

### 1. Polygon
Polygons are represented as arrays of points. Each point is a pair of coordinates `[x, y]`. The structure is a nested list:
- The first array represents the **outer ring** (only one).
- Subsequent arrays represent **inner rings** (holes), which can be zero or more.
- Each array contains a sequence of `[x1, y1, x2, y2, ...]`, where each pair `[xi, yi]` represents a point in the polygon.

Example:
```json
[
  [100, 200, 150, 250, ...],  // Outer ring
  [120, 220, 130, 240, ...],  // Inner ring (hole)
  ...
]
```

### 2. Clicks
Clicks are represented as an array of `[x, y, is_positive]`, where:
- `is_positive` is `1` for positive clicks and `0` for negative clicks.

Example:
```json
[
  [100, 200, 1],  // Positive click at (100, 200)
  [150, 250, 0],  // Negative click at (150, 250)
  ...
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
    [100, 200, 150, 250, ...],  // Outer contour
    [120, 220, 130, 240, ...],  // Inner hole
    ...
  ]
}
```

#### Response
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "segmentation": [
    [110, 210, 160, 260, ...],  // Outer contour
    [115, 215, 155, 255, ...],  // Inner hole
    ...
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
    "message": "Image size not supported by model",
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
