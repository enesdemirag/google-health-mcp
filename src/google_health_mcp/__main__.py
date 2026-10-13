import argparse
import json

import uvicorn
from pydantic import ValidationError

from google_health_mcp.config import Settings
from google_health_mcp.server import create_app, create_server


def main():
    parser = argparse.ArgumentParser(
        description="Run the standalone, multi-user Google Health MCP MCP server."
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print the configured URLs and tool names without starting the server or exposing secrets.",
    )
    parser.add_argument(
        "--export-tools",
        action="store_true",
        help="Print the MCP tool catalog as JSON for documentation and connector review.",
    )
    args = parser.parse_args()
    try:
        settings = Settings()
    except ValidationError as exc:
        parser.error(
            "Invalid operator configuration: "
            + "; ".join(error["msg"] for error in exc.errors(include_input=False))
        )
    if args.describe:
        print(
            json.dumps(
                {
                    "name": "Google Health MCP",
                    "transport": "streamable-http",
                    "mcp_url": f"{settings.public_base_url}/mcp",
                    "google_redirect_uri": settings.google_redirect_uri,
                    "authentication": "Google OAuth through the server-owned OAuth proxy",
                    "tools": [
                        "get_connection_status",
                        "list_health_metrics",
                        "get_metric_history",
                        "get_sleep_sessions",
                        "get_workouts",
                        "get_health_overview",
                        "get_daily_health_context",
                    ],
                },
                indent=2,
            )
        )
        return
    if args.export_tools:
        import asyncio

        async def export():
            server = create_server(settings)
            tools = await server.list_tools()
            print(
                json.dumps(
                    {
                        "tools": [
                            tool.to_mcp_tool().model_dump(mode="json", by_alias=True, exclude_none=True)
                            for tool in tools
                        ]
                    },
                    indent=2,
                )
            )

        asyncio.run(export())
        return
    uvicorn.run(
        create_app(settings), host=settings.host, port=settings.port, access_log=False, log_level="warning"
    )


if __name__ == "__main__":
    main()
