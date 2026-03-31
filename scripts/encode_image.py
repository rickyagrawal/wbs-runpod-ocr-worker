import base64
import json
import mimetypes
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/encode_image.py /path/to/image")

    path = Path(sys.argv[1])
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    payload = {
        "input": {
            "image_base64": f"data:{mime};base64,{encoded}",
            "max_new_tokens": 1024,
        }
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
