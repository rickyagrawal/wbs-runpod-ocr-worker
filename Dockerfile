FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

ARG MODEL_ID=lightonai/LightOnOCR-2-1B
ARG MODEL_DIR=/opt/models/lightonocr-2-1b

ENV MODEL_ID=${MODEL_ID}
ENV MODEL_DIR=${MODEL_DIR}
ENV MODEL_PATH=${MODEL_DIR}
ENV HF_HOME=/opt/hf
ENV TRANSFORMERS_CACHE=/opt/hf
ENV HF_HUB_ENABLE_HF_TRANSFER=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt /requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /requirements.txt

RUN python - <<'PY'
import os
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id=os.environ["MODEL_ID"],
    local_dir=os.environ["MODEL_DIR"],
    local_dir_use_symlinks=False,
    allow_patterns=[
        "added_tokens.json",
        "chat_template.jinja",
        "config.json",
        "generation_config.json",
        "model.safetensors",
        "processor_config.json",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
    ],
)
PY

WORKDIR /app

COPY handler.py /app/handler.py
COPY test_input.json /app/test_input.json

CMD ["python", "-u", "/app/handler.py"]
