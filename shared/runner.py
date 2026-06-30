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

        # IP 直打ちや Docker 内部ホスト名でのアクセスを通すため allowed_hosts を開放する。
        # MCP SDK >= 1.2 の FastMCP.Settings に存在するフィールド。
        # 古い SDK では属性自体がないため hasattr でガードする。
        if hasattr(mcp_instance.settings, "allowed_hosts"):
            mcp_instance.settings.allowed_hosts = ["*"]

        mcp_instance.run(transport="streamable-http")
    else:
        mcp_instance.run(transport="stdio")
