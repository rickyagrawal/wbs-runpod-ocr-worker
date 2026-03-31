#!/usr/bin/env python3
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


REST_BASE = "https://rest.runpod.io/v1"
API_BASE = "https://api.runpod.ai/v2"


def request_json(url: str, api_key: str, method: str = "GET", body: dict | None = None) -> dict | list:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=1800) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


def create_endpoint(api_key: str, template_id: str, gpu_type: str, data_center: str) -> dict:
    payload = {
        "name": f"cold-probe-{int(time.time())}",
        "templateId": template_id,
        "computeType": "GPU",
        "gpuCount": 1,
        "gpuTypeIds": [gpu_type],
        "dataCenterIds": [data_center],
        "minCudaVersion": "11.8",
        "workersMin": 0,
        "workersMax": 1,
        "idleTimeout": 5,
        "scalerType": "QUEUE_DELAY",
        "scalerValue": 4,
        "executionTimeoutMs": 600000,
        "flashboot": True,
    }
    return request_json(f"{REST_BASE}/endpoints", api_key, method="POST", body=payload)


def delete_endpoint(api_key: str, endpoint_id: str) -> None:
    try:
        request_json(f"{REST_BASE}/endpoints/{endpoint_id}", api_key, method="DELETE")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise


def get_health(api_key: str, endpoint_id: str) -> dict:
    return request_json(f"{API_BASE}/{endpoint_id}/health", api_key)


def submit_async(api_key: str, endpoint_id: str, image_path: str, max_new_tokens: int) -> dict:
    with open(image_path, "rb") as handle:
        image_base64 = base64.b64encode(handle.read()).decode()
    payload = {
        "input": {
            "image_base64": image_base64,
            "max_new_tokens": max_new_tokens,
        }
    }
    return request_json(f"{API_BASE}/{endpoint_id}/run", api_key, method="POST", body=payload)


def get_status(api_key: str, endpoint_id: str, job_id: str) -> dict:
    return request_json(f"{API_BASE}/{endpoint_id}/status/{urllib.parse.quote(job_id)}", api_key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure RunPod cold start and first async completion.")
    parser.add_argument("--template-id", default="xkr2kl7lp7")
    parser.add_argument("--gpu-type", default="NVIDIA L4")
    parser.add_argument("--data-center", default="US-TX-1")
    parser.add_argument("--image-path", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--poll-seconds", type=int, default=5)
    args = parser.parse_args()

    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print("RUNPOD_API_KEY is required", file=sys.stderr)
        return 2

    started = time.time()
    endpoint = create_endpoint(api_key, args.template_id, args.gpu_type, args.data_center)
    endpoint_id = endpoint["id"]
    print(json.dumps({"event": "endpoint_created", "endpoint_id": endpoint_id, "started_at": started}))

    ready_at = None
    job_id = None
    completed = None

    try:
        while ready_at is None:
            health = get_health(api_key, endpoint_id)
            workers = health.get("workers", {})
            print(json.dumps({"event": "health", "seconds": round(time.time() - started, 3), "health": health}))
            if workers.get("ready", 0) or workers.get("idle", 0):
                ready_at = time.time()
                break
            time.sleep(args.poll_seconds)

        queued_at = time.time()
        queued = submit_async(api_key, endpoint_id, args.image_path, args.max_new_tokens)
        job_id = queued["id"]
        print(json.dumps({"event": "job_submitted", "job_id": job_id, "seconds": round(queued_at - started, 3), "response": queued}))

        while True:
            status = get_status(api_key, endpoint_id, job_id)
            print(json.dumps({"event": "status", "seconds": round(time.time() - started, 3), "status": status}))
            if status.get("status") in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}:
                completed = time.time()
                break
            time.sleep(args.poll_seconds)

        print(
            json.dumps(
                {
                    "event": "summary",
                    "endpoint_id": endpoint_id,
                    "job_id": job_id,
                    "seconds_to_ready": round(ready_at - started, 3) if ready_at else None,
                    "seconds_to_submit": round(queued_at - started, 3),
                    "seconds_to_terminal": round(completed - started, 3) if completed else None,
                    "seconds_submit_to_terminal": round(completed - queued_at, 3) if completed else None,
                }
            )
        )
        return 0
    finally:
        delete_endpoint(api_key, endpoint_id)
        print(json.dumps({"event": "endpoint_deleted", "endpoint_id": endpoint_id}))


if __name__ == "__main__":
    raise SystemExit(main())
