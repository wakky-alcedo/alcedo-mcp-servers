FROM python:3.12-slim

WORKDIR /app

# shared/ も含めてコピーするため、ビルドコンテキストはリポジトリルートを想定
COPY task-mcp/requirements.txt ./task-mcp/requirements.txt
RUN pip install --no-cache-dir -r task-mcp/requirements.txt

COPY shared/ ./shared/
COPY task-mcp/ ./task-mcp/

ENV MCP_TRANSPORT=streamable-http
ENV MCP_PORT=8800

EXPOSE 8800

CMD ["python3", "task-mcp/server.py"]
