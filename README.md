# Camel Toolkits MCP

A lightweight server that exports [Camel](https://github.com/camel-ai/camel) framework toolkits as MCP-compatible tools.

## Overview

This project bridges the gap between the Camel AI framework's toolkit ecosystem and MCP (Model Control Protocol) compatible clients. It allows you to dynamically load and expose any Camel toolkit as an MCP server, making these tools available to a wide range of LLM-based applications.

Key features:
- Dynamically discover and list available Camel toolkits
- Load and register toolkits at runtime with a simple API
- Automatic detection and handling of required API keys
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

## Usage

Start the server:

```bash
python -m camel_toolkits_mcp
```

This will start an MCP server that exposes the following tools:

- `get_toolkits_list()`: Lists all available Camel toolkits
- `register_toolkit()`: Registers a toolkit by name
- `get_toolkit_info()`: Gets information about a toolkit's parameters

### Using with UVX

You can easily configure UVX to run the Camel toolkits server in your `.uvx.json` file:

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
        "NOTION_TOKEN": "your-notion-token"
      }
    }
  }
}
```

This configuration will automatically launch the Camel toolkits server when starting UVX.

### Example: Using Notion Toolkit

```python
# First, discover available toolkits
toolkits = get_toolkits()
print(toolkits)  # Shows all available toolkits including NotionToolkit

# Register the Notion toolkit
result = register_toolkit("NotionToolkit")

# If API keys are required, you'll get a response like:
# {
#   "status": "missing_api_keys",
#   "toolkit": "NotionToolkit",
#   "missing_keys": ["NOTION_TOKEN"],
#   "message": "Missing required API keys: NOTION_TOKEN. Please provide these keys to register the toolkit."
# }

# Register with API keys:
result = register_toolkit(
    "NotionToolkit", 
    api_keys={"NOTION_TOKEN": "your_notion_api_key"}
)

# Now all Notion toolkit tools are available for use through MCP
```

## Architecture

The router works by:
1. Scanning the Camel framework's toolkit directory
2. Analyzing each toolkit class to detect its tools and API requirements
3. Creating proper MCP-compatible wrappers for each tool function
4. Registering these wrappers with the FastMCP server

## Supported Toolkits

This server supports all toolkits in the Camel framework, including:
- NotionToolkit
- OpenAIToolkit
- WebSearchToolkit
- And many more...

## API Key Management

For toolkits requiring API keys (like Notion, OpenAI, etc.), you can provide them in two ways:

1. Set in environment variables before starting the server
2. Provide them directly when calling `register_toolkit`

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

To publish a new version:

1. Update the version in `camel_toolkits_mcp/__init__.py`
2. Create a new GitHub release with a tag like `v0.1.0`
3. The GitHub workflow will automatically build and publish to PyPI

## License

This project is licensed under the MIT License - see the LICENSE file for details.
