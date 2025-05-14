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

```bash
# Clone the repository
git clone https://github.com/yourusername/camel-toolkits-mcp.git
cd camel-toolkits-mcp

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Starting the Server

```bash
python server.py
```

This will start the MCP server, which exposes two main tools:

1. `get_toolkits()` - Lists all available toolkits in the Camel framework
2. `register_toolkit(toolkit_name, api_keys)` - Loads a specific toolkit and registers its tools

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

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
