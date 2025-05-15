#!/usr/bin/env python3
"""
Camel Toolkits MCP Server - Exposes Camel toolkits as MCP-compatible tools.
"""

import os
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
    # Get MCP port from environment or use default
    port = int(os.environ.get("MCP_PORT", 8080))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    
    logger.info(f"Starting Camel Toolkits MCP Server on {host}:{port}")
    logger.info("Available tools:")
    logger.info("- get_toolkits_list(): Lists all available toolkits")
    logger.info("- register_toolkit(): Registers a toolkit by name")
    logger.info("- get_toolkit_info(): Get information about a toolkit's parameters")
    
    # Start the MCP server
    mcp.start(host=host, port=port)
    return 0


if __name__ == "__main__":
    main()