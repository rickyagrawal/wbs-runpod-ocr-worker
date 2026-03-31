# WBS RunPod OCR Worker

Queue-style RunPod Serverless worker for testing OCR models against WBS document images.

Current default model:

- `lightonai/LightOnOCR-2-1B`

## Files

- `handler.py`: dual-mode OCR worker
- `Dockerfile`: RunPod-compatible worker image
- `requirements.txt`: Python dependencies
- `test_input.json`: local pod-mode test payload

## How it works

The worker loads the OCR model once at process startup and then accepts jobs with:

- `image_base64`
- or `image_url`

For local or Pod-style testing, it also accepts:

- `image_path`

## Local pod-style test

Set pod mode and point `test_input.json` at a real image:

```bash
MODE_TO_RUN=pod python handler.py test_input.json
```

Example payload:

```json
{
  "input": {
    "image_path": "./vishal-license.jpg",
    "max_new_tokens": 1024
  }
}
```

## Build the image

```bash
docker build -t YOUR_DOCKERHUB_USER/wbs-runpod-ocr-worker:latest .
docker push YOUR_DOCKERHUB_USER/wbs-runpod-ocr-worker:latest
```

## Deploy to RunPod

Use a Queue endpoint and import the Docker image from your registry.

Recommended endpoint settings:

- `workersMin = 0`
- `workersMax = 1`
- cheap 24 GB GPU first, like `RTX 3090`, `RTX A5000`, or similar
- queue endpoint, not load balancer

Environment variables:

- `MODE_TO_RUN=serverless`
- `MODEL_ID=lightonai/LightOnOCR-2-1B`
- `MODEL_PATH=/opt/models/lightonocr-2-1b`
- optional `MAX_NEW_TOKENS=1024`

## Example serverless request

```json
{
  "input": {
    "image_base64": "BASE64_IMAGE_BYTES",
    "max_new_tokens": 1024
  }
}
```

## Notes

- This is the correct Serverless worker shape. It avoids Pod-time `pip install` and other runtime bootstrap hacks.
- If cold starts are too slow, the next step is model caching or baking the model into the image.

## Cold-start probe

This repo includes an async probe that creates a temporary endpoint, pins it to one GPU type and one data center, submits one job, polls until terminal status, and deletes the endpoint:

```bash
RUNPOD_API_KEY=... python scripts/measure_cold_start.py \
  --image-path /path/to/vishal-license.jpg \
  --gpu-type "NVIDIA L4" \
  --data-center US-TX-1
```

This is the right way to test low-budget fallback behavior because it avoids `runsync` cold-start weirdness and measures:

- seconds to ready
- seconds to first async submit
- seconds to terminal result
