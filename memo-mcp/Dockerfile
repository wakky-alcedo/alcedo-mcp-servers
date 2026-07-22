FROM python:3.12-slim

WORKDIR /app

# shared/ も含めてコピーするため、ビルドコンテキストはリポジトリルートを想定
COPY memo-mcp/requirements.txt ./memo-mcp/requirements.txt
RUN pip install --no-cache-dir -r memo-mcp/requirements.txt

COPY shared/ ./shared/
COPY memo-mcp/ ./memo-mcp/

ENV MCP_TRANSPORT=streamable-http
ENV MCP_PORT=8804

EXPOSE 8804

CMD ["python3", "memo-mcp/server.py"]
