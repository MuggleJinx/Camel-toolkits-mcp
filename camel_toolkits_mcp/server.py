#!/usr/bin/env python3
"""
Camel Toolkits MCP Server - Exposes Camel toolkits as MCP-compatible tools.
"""

import logging
from camel_toolkits_mcp.router import mcp

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Run the Camel Toolkits MCP server."""
    mcp.run("stdio")
    return 0


if __name__ == "__main__":
    main()
