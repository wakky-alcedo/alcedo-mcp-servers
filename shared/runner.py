"""
全MCPサーバー共通のユーティリティ。

各サーバーの server.py からは以下のように使う:

    from shared.runner import run_server
    ...
    if __name__ == "__main__":
        run_server(mcp)
"""

import os


def run_server(mcp_instance) -> None:
    """
    環境変数 MCP_TRANSPORT に応じてサーバーを起動する。

    - "stdio" (デフォルト): 手元PCのClaude Code等からローカルプロセスとして起動する場合
    - "streamable-http": docker-srv上に常駐させ、Cloudflare Tunnel経由で
                          claude.aiのカスタムコネクタやスマホアプリから繋ぐ場合
    """
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "streamable-http":
        mcp_instance.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp_instance.settings.port = int(os.environ.get("MCP_PORT", "8800"))
        mcp_instance.run(transport="streamable-http")
    else:
        mcp_instance.run(transport="stdio")
