import base64
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path
from urllib.request import urlopen

import runpod
import torch
from PIL import Image
from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor


MODEL_ID = os.environ.get("MODEL_ID", "lightonai/LightOnOCR-2-1B")
MODE_TO_RUN = os.environ.get("MODE_TO_RUN", "serverless")
DEFAULT_MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "1024"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32

_MODEL = None
_PROCESSOR = None


def load_model():
    global _MODEL, _PROCESSOR

    if _MODEL is not None and _PROCESSOR is not None:
        return _MODEL, _PROCESSOR

    started = time.time()
    print(f"Loading model={MODEL_ID} device={DEVICE} dtype={DTYPE}", flush=True)
    _MODEL = LightOnOcrForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype=DTYPE,
    ).to(DEVICE)
    _PROCESSOR = LightOnOcrProcessor.from_pretrained(MODEL_ID)
    _MODEL.eval()
    print(f"Model loaded in {time.time() - started:.2f}s", flush=True)
    return _MODEL, _PROCESSOR


def decode_data_url_or_base64(value: str) -> bytes:
    if value.startswith("data:"):
        _, encoded = value.split(",", 1)
        return base64.b64decode(encoded)
    return base64.b64decode(value)


def load_image(job_input: dict) -> Image.Image:
    if "image_base64" in job_input:
        raw = decode_data_url_or_base64(job_input["image_base64"])
        return Image.open(io.BytesIO(raw)).convert("RGB")

    if "image_url" in job_input:
        with urlopen(job_input["image_url"]) as response:
            return Image.open(io.BytesIO(response.read())).convert("RGB")

    if "image_path" in job_input and MODE_TO_RUN != "serverless":
        return Image.open(job_input["image_path"]).convert("RGB")

    raise ValueError("Provide image_base64, image_url, or image_path.")


def run_ocr(image: Image.Image, max_new_tokens: int) -> str:
    model, processor = load_model()
    conversation = [{"role": "user", "content": [{"type": "image", "image": image}]}]
    inputs = processor.apply_chat_template(
        conversation,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    )
    inputs = {
        key: value.to(device=DEVICE, dtype=DTYPE) if value.is_floating_point() else value.to(DEVICE)
        for key, value in inputs.items()
    }
    with torch.inference_mode():
        output_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)
    generated_ids = output_ids[0, inputs["input_ids"].shape[1]:]
    return processor.decode(generated_ids, skip_special_tokens=True)


def handler(job):
    started = time.time()
    job_input = job["input"]
    max_new_tokens = int(job_input.get("max_new_tokens", DEFAULT_MAX_NEW_TOKENS))

    try:
        image = load_image(job_input)
        text = run_ocr(image, max_new_tokens=max_new_tokens)
        return {
            "ok": True,
            "text": text,
            "model": MODEL_ID,
            "device": DEVICE,
            "seconds": round(time.time() - started, 3),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "model": MODEL_ID,
            "device": DEVICE,
            "seconds": round(time.time() - started, 3),
        }


def run_local():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/app/test_input.json")
    payload = json.loads(path.read_text())
    result = handler(payload)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if MODE_TO_RUN == "serverless":
        runpod.serverless.start({"handler": handler})
    else:
        run_local()

