# Camel Toolkits MCP

A lightweight server that exports [Camel](https://github.com/camel-ai/camel) framework toolkits as MCP-compatible tools.

## Overview

This project bridges the gap between the Camel AI framework's toolkit ecosystem and MCP (Model Control Protocol) compatible clients. It allows you to dynamically load and expose any Camel toolkit as an MCP server, making these tools available to a wide range of LLM-based applications.

Key features:
- Dynamically discover and list available Camel toolkits
- Load and execute toolkit functions at runtime
- Seamless conversion of Camel toolkit functions to MCP-compatible tools

## Installation

You can install the package directly from PyPI:

```bash
pip install camel-toolkits-mcp
```

Or install from source:

```bash
git clone https://github.com/jinx0a/camel-toolkits-mcp.git
cd camel-toolkits-mcp
pip install -e .
```

## Config with MCP clients

### Using with uvx

You can easily configure uvx to run the Camel toolkits server like this:

```json
{
  "mcpServers": {
    "camel-toolkits": {
      "command": "uvx",
      "args": [
        "camel-toolkits-mcp"
      ],
      "env": {
        "OPENAI_API_KEY": "your-openai-key",
        "NOTION_TOKEN": "your-notion-token",
        "..." : "..."
      }
    }
  }
}
```

### Local Development Configuration

If you're developing this package locally, you can configure UVX to use your development version:

```json
{
  "mcpServers": {
    "camel_toolkits_mcp": {
      "command": "/path/to/python",
      "args": [
        "/path/to/camel_toolkits_mcp/server.py"
      ],
      "env": {
        "OPENAI_API_KEY": "your-openai-key",
        "NOTION_TOKEN": "your-notion-token",
        "..." : "..."
      }
    }
  }
}
```

## Available Tools

The server exposes the following MCP-compatible tools:

- `get_toolkits_list()`: Lists all available Camel toolkits with their descriptions
- `list_toolkit_functions(toolkit_name, include_methods=True)`: Lists all functions available in a specific toolkit
- `execute_toolkit_function(toolkit_name, function_name, toolkit_params=None, function_args=None)`: Executes a specific function from a toolkit

### Example: Using Tools

```python
# First, discover available toolkits
toolkits = get_toolkits_list()
print(toolkits)  # Shows all available toolkits

# List functions in a specific toolkit (e.g., NotionToolkit)
functions = list_toolkit_functions(toolkit_name="NotionToolkit")

# Execute a toolkit function
result = execute_toolkit_function(
    toolkit_name="NotionToolkit",
    function_name="search_pages",
    toolkit_params={"notion_token": "your-notion-token"},
    function_args={"query": "meeting notes"}
)
```

## Architecture

The router works by:
1. Scanning the Camel framework's toolkit directory
2. Analyzing each toolkit class to detect its tools and API requirements
3. Creating proper MCP-compatible wrappers for each tool function
4. Exposing these functions through the FastMCP server

## Supported Toolkits

This server supports all toolkits in the Camel framework, including:
- NotionToolkit
- OpenAIToolkit
- WebSearchToolkit
- And many more...

## API Key Management

For toolkits requiring API keys (like Notion, OpenAI, etc.), you should provide them in the environment variables when configuring the MCP server.

## Development

To set up a development environment:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

## Contributing

Contributions are welcome! The project uses GitHub Actions for CI/CD:

1. Tests are run automatically on pull requests
2. New releases are automatically published to PyPI when a GitHub release is created

## License

This project is licensed under the MIT License - see the LICENSE file for details.
