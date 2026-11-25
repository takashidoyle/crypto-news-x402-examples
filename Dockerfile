FROM python:3.12-slim
WORKDIR /app
COPY mcp_stdio_bridge.py /app/mcp_stdio_bridge.py
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/app/mcp_stdio_bridge.py"]
