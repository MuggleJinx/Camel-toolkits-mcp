import importlib
import inspect
import os
import re
import functools
from pathlib import Path
from typing import Dict, Optional, List

from camel.toolkits.base import BaseToolkit
from camel.toolkits.function_tool import FunctionTool

import importlib.util

from mcp.server.fastmcp import FastMCP


def get_camel_toolkit_dir() -> Path:
    """Finds the filesystem path to camel.toolkits directory."""
    spec = importlib.util.find_spec("camel.toolkits")
    if spec and spec.submodule_search_locations:
        return Path(spec.submodule_search_locations[0])
    raise ImportError("Cannot locate camel.toolkits module")


TOOLKIT_DIR = get_camel_toolkit_dir() 


mcp = FastMCP("Camel Router")


@mcp.tool()
def get_toolkits():
    """Return all available toolkits in the camel.toolkits module.
    
    Returns:
        dict: A dictionary mapping toolkit names to their descriptions
    """
    toolkit_modules = {}
    
    # Get all Python files in the toolkits directory
    toolkit_files = [
        f for f in TOOLKIT_DIR.iterdir() 
        if f.is_file() and f.suffix == '.py' and f.stem != '__init__'
    ]
    
    # Import each toolkit module and collect BaseToolkit subclasses
    for toolkit_file in toolkit_files:
        module_name = f"camel.toolkits.{toolkit_file.stem}"
        try:
            module = importlib.import_module(module_name)
            
            # Find all BaseToolkit subclasses in the module
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                        issubclass(obj, BaseToolkit) and 
                        obj is not BaseToolkit):
                    
                    # Get the toolkit description
                    description = obj.__doc__ or "No description available"
                    toolkit_modules[name] = description.strip()
        except (ImportError, AttributeError):
            # Skip modules that can't be imported or don't contain toolkits
            pass
    
    return toolkit_modules


def get_toolkit_requirements(toolkit_class) -> List[str]:
    """Analyze the toolkit class to determine required API keys.
    
    Args:
        toolkit_class: The toolkit class to analyze
        
    Returns:
        List[str]: List of required environment variable names
    """
    required_keys = []
    
    # Check toolkit source code for environment variable references
    source = inspect.getsource(toolkit_class)
    
    # Look for common patterns like os.environ.get('API_KEY')
    env_patterns = [
        r"os\.environ\.get\(['\"]([A-Z0-9_]+)['\"]",  # os.environ.get('KEY')
        r"os\.environ\[['\"]([A-Z0-9_]+)['\"]",       # os.environ['KEY']
        r"os\.getenv\(['\"]([A-Z0-9_]+)['\"]",        # os.getenv('KEY')
    ]
    
    for pattern in env_patterns:
        matches = re.findall(pattern, source)
        required_keys.extend(matches)
    
    # Check if there's an explicit REQUIRED_KEYS class variable
    if hasattr(toolkit_class, 'REQUIRED_KEYS'):
        required_keys.extend(toolkit_class.REQUIRED_KEYS)
    
    # Add common keys based on toolkit name
    toolkit_name = toolkit_class.__name__.lower()
    if 'notion' in toolkit_name:
        required_keys.append('NOTION_TOKEN')
    elif 'openai' in toolkit_name:
        required_keys.append('OPENAI_API_KEY')
    elif 'google' in toolkit_name or 'gmail' in toolkit_name:
        required_keys.append('GOOGLE_API_KEY')
    
    # Remove duplicates
    return list(set(required_keys))


def check_missing_env_keys(required_keys: List[str]) -> List[str]:
    """Check which required environment variables are missing.
    
    Args:
        required_keys: List of required environment variable names
        
    Returns:
        List[str]: List of missing environment variable names
    """
    missing_keys = []
    
    for key in required_keys:
        if not os.environ.get(key):
            missing_keys.append(key)
            
    return missing_keys


def get_tool_name(tool):
    """Extract the name of a tool regardless of its format.
    
    Args:
        tool: A tool object from a toolkit
        
    Returns:
        str: The name of the tool
    """
    # Check for different attribute names used in different toolkit implementations
    if hasattr(tool, 'name'):
        return tool.name
    elif hasattr(tool, 'function_name'):
        return tool.function_name
    elif hasattr(tool, 'func') and hasattr(tool.func, '__name__'):
        return tool.func.__name__
    elif hasattr(tool, '__name__'):
        return tool.__name__
    
    # Default to a unique identifier if nothing else works
    return f"tool_{id(tool)}"


@mcp.tool()
def register_toolkit(toolkit_name: str, api_keys: Optional[Dict[str, str]] = None):
    """Initialize a toolkit by name and register all its tools with MCP.
    
    Args:
        toolkit_name: The name of the toolkit class to initialize
                     (e.g., "NotionToolkit")
        api_keys: Dictionary containing API keys for the toolkit.
                Example: {"NOTION_TOKEN": "secret_abc123"}
    
    Returns:
        dict: Information about the registered tools or missing requirements
    """
    # Find the module containing the toolkit
    toolkit_class = None
    
    # Search in all toolkit modules
    toolkit_files = [
        f for f in TOOLKIT_DIR.iterdir() 
        if f.is_file() and f.suffix == '.py' and f.stem != '__init__'
    ]
    
    for toolkit_file in toolkit_files:
        module_name = f"camel.toolkits.{toolkit_file.stem}"
        try:
            module = importlib.import_module(module_name)
            
            # Check if this module contains the requested toolkit
            if hasattr(module, toolkit_name):
                toolkit_class = getattr(module, toolkit_name)
                break
        except ImportError:
            continue
    
    if toolkit_class is None:
        return {"error": f"Toolkit '{toolkit_name}' not found"}
    
    # Check if it's a valid toolkit class
    if not (inspect.isclass(toolkit_class) and 
            issubclass(toolkit_class, BaseToolkit)):
        return {"error": f"'{toolkit_name}' is not a valid toolkit class"}
    
    # Check if toolkit requires API keys
    required_keys = get_toolkit_requirements(toolkit_class)
    
    # Set any provided API keys in the environment
    if api_keys:
        for key, value in api_keys.items():
            if value:  # Only set non-empty values
                os.environ[key] = value
    
    # Check for missing keys
    missing_keys = check_missing_env_keys(required_keys)
    
    if missing_keys:
        # Return information about missing keys
        return {
            "status": "missing_api_keys",
            "toolkit": toolkit_name,
            "missing_keys": missing_keys,
            "message": (
                f"Missing required API keys: {', '.join(missing_keys)}. "
                f"Please provide these keys to register the toolkit."
            )
        }
    
    # Initialize the toolkit
    toolkit_instance = toolkit_class()
    
    # Get all tools from the toolkit
    tools = toolkit_instance.get_tools()
    
    # Register each tool with MCP
    registered_tools = []
    for tool in tools:
        # Determine the function name and function itself
        function_name = get_tool_name(tool)
        
        # For FunctionTool objects, get the underlying function
        if isinstance(tool, FunctionTool):
            function = tool.func
        else:
            # For other types of tools, try to get a callable
            function = getattr(tool, 'func', tool)
            if not callable(function):
                # Skip tools without a callable function
                continue
        
        # Create a properly wrapped function that preserves the signature
        def create_wrapped_tool(func):
            sig = inspect.signature(func)

            @functools.wraps(func)
            def wrapped_function(*args, **kwargs):
                if 'args' in kwargs and 'args' not in sig.parameters:
                    del kwargs['args']
                return func(*args, **kwargs)
            
            return wrapped_function

        wrapped_function = create_wrapped_tool(function)
        mcp.tool(name=function_name)(wrapped_function)
        
        # Get the description from the docstring
        doc = function.__doc__ or "No description available"
        
        registered_tools.append({
            "name": function_name,
            "description": doc.strip()
        })
    
    return {
        "status": "success",
        "toolkit": toolkit_name,
        "registered_tools": registered_tools,
        "total_tools": len(registered_tools)
    }