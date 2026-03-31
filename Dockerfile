FROM runpod/base:0.6.3-cuda11.8.0

# Match RunPod's current worker template defaults.
RUN ln -sf "$(which python3.11)" /usr/local/bin/python && \
    ln -sf "$(which python3.11)" /usr/local/bin/python3

COPY requirements.txt /requirements.txt
RUN uv pip install --upgrade -r /requirements.txt --no-cache-dir --system

WORKDIR /app

COPY handler.py /app/handler.py
COPY test_input.json /app/test_input.json

CMD ["python", "-u", "/app/handler.py"]

