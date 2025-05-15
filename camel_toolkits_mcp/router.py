import importlib
import inspect
import re
import functools
import ast
from pathlib import Path
from typing import Dict, Optional, Any

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
EXCLUDED_TOOLKITS = ["mcp_toolkit"]

mcp = FastMCP("Camel Router")


@mcp.tool()
@mcp.resource("tools://all")
def get_toolkits_list():
    """Return all available toolkits in the camel.toolkits module.

    Returns:
        dict: A dictionary mapping toolkit names to their descriptions
    """
    toolkit_modules = {}

    # Get all Python files in the toolkits directory
    toolkit_files = [
        f
        for f in TOOLKIT_DIR.iterdir()
        if (
            f.is_file()
            and f.suffix == ".py"
            and f.stem != "__init__"
            and f.stem not in EXCLUDED_TOOLKITS
        )
    ]

    # Import each toolkit module and collect BaseToolkit subclasses
    for toolkit_file in toolkit_files:
        module_name = f"camel.toolkits.{toolkit_file.stem}"
        try:
            module = importlib.import_module(module_name)

            # Find all BaseToolkit subclasses in the module
            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, BaseToolkit)
                    and obj is not BaseToolkit
                ):

                    # Get the toolkit description
                    description = obj.__doc__ or "No description available"
                    toolkit_modules[name] = description.strip()
        except (ImportError, AttributeError):
            # Skip modules that can't be imported or don't contain toolkits
            pass

    return toolkit_modules


def extract_params_from_docstring(docstring):
    """
    Extract parameter information from a docstring.

    Args:
        docstring: The docstring to parse

    Returns:
        dict: Dictionary of parameter information
    """
    if not docstring:
        return {}

    # Regular expression to match parameter descriptions in docstring
    pattern = r"(?:Args|Parameters):\s*\n((?:\s+[a-zA-Z_][a-zA-Z0-9_]*.*)+)"
    param_match = re.search(pattern, docstring, re.MULTILINE)

    if not param_match:
        return {}

    param_section = param_match.group(1)

    # Extract individual parameter descriptions
    pattern = (
        r"\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\([^)]*\))?\s*:(.*?)(?=\n\s+[a-zA-Z_]|$)"
    )
    param_matches = re.finditer(pattern, param_section + "\n", re.DOTALL)

    params = {}
    for match in param_matches:
        name = match.group(1)
        description = match.group(2).strip()

        # Try to determine if parameter is required and extract default value
        required = True
        default = None

        # Look for indications of default values
        default_match = re.search(
            r"default\s*:\s*(?:obj:`)?([^`\)]+)(?:`\))?", description
        )
        if default_match:
            default_str = default_match.group(1).strip()
            if default_str in ["None", "null"]:
                default = None
                required = False
            elif default_str in ["True", "true"]:
                default = True
                required = False
            elif default_str in ["False", "false"]:
                default = False
                required = False
            elif default_str.startswith('"') or default_str.startswith("'"):
                # String default value
                default = default_str.strip("\"'")
                required = False
            elif default_str.startswith("{") or default_str.startswith("["):
                # Dict or list default
                try:
                    default = eval(default_str)
                    required = False
                except Exception:
                    pass
            else:
                # Try to interpret as number or other literal
                try:
                    default = eval(default_str)
                    required = False
                except Exception:
                    pass

        # Also check for "optional" in the description
        if "optional" in description.lower():
            required = False

        params[name] = {
            "required": required,
            "default": default,
            "description": description,
        }

    return params


def parse_constructor_source(toolkit_class):
    """
    Parse the source code of a class constructor to extract parameter information.

    Args:
        toolkit_class: The class to analyze

    Returns:
        dict: Dictionary of parameter information extracted from source
    """
    try:
        # Get the source code of the __init__ method
        source = inspect.getsource(toolkit_class.__init__)

        # Parse the source code into an AST
        tree = ast.parse(source)

        # Find the function definition node (should be the first one)
        function_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                function_def = node
                break

        if not function_def:
            return {}

        params = {}

        # Skip the 'self' parameter
        for arg in function_def.args.args[1:]:
            param_name = arg.arg
            # Check if parameter has a type annotation
            param_type = None
            if hasattr(arg, "annotation") and arg.annotation:
                try:
                    param_type = ast.unparse(arg.annotation)
                except (AttributeError, ValueError):
                    # ast.unparse is only available in Python 3.9+
                    param_type = "unknown"

            params[param_name] = {
                "required": True,  # Will be updated if default found
                "default": None,  # Will be updated if default found
                "type": param_type,
            }

        # Check for default values
        defaults = function_def.args.defaults
        if defaults:
            # Match defaults to parameters (from right to left)
            offset = len(function_def.args.args) - len(defaults)
            for i, default in enumerate(defaults):
                # Skip self parameter (offset already accounts for it)
                param_index = offset + i
                if param_index < 1:  # Skip 'self'
                    continue

                param_name = function_def.args.args[param_index].arg

                if param_name in params:
                    try:
                        # Extract the default value
                        default_value = ast.literal_eval(default)
                        params[param_name]["default"] = default_value
                        params[param_name]["required"] = False
                    except (ValueError, SyntaxError):
                        # For complex defaults that can't be evaluated statically
                        # Look for common patterns in the source
                        try:
                            default_str = ast.unparse(default).strip()
                            if default_str == "None":
                                params[param_name]["default"] = None
                                params[param_name]["required"] = False
                            elif default_str in ["dict()", "{}", "[]", "list()"]:
                                params[param_name]["default"] = eval(default_str)
                                params[param_name]["required"] = False
                            else:
                                # Store the source representation
                                params[param_name]["default_source"] = default_str
                                params[param_name]["required"] = False
                        except (AttributeError, ValueError):
                            # Can't determine the default precisely
                            params[param_name]["required"] = False

        # Also check for kwargs
        has_kwargs = function_def.args.kwarg is not None
        has_args = function_def.args.vararg is not None

        return {"params": params, "has_kwargs": has_kwargs, "has_args": has_args}

    except Exception as e:
        # If parsing fails, return empty dict
        return {"error": str(e)}


def get_toolkit_class_params(toolkit_class) -> dict:
    """Get information about the parameters required for toolkit initialization."""
    params = {}

    # First try to get parameters from the constructor signature
    signature = inspect.signature(toolkit_class.__init__)

    # Skip 'self' parameter and process the rest
    for name, param in list(signature.parameters.items())[1:]:
        # Skip *args and **kwargs as they don't provide useful type information
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        has_default = param.default != param.empty
        param_type = param.annotation if param.annotation != param.empty else None

        params[name] = {
            "required": not has_default,
            "default": param.default if has_default else None,
            "type": str(param_type) if param_type else "unknown",
        }

    # Try to get more precise information from source code
    source_info = parse_constructor_source(toolkit_class)
    if source_info and "params" in source_info:
        source_params = source_info["params"]
        for name, info in source_params.items():
            if name in params:
                # Update with more precise information if available
                if "default" in info and info["default"] is not None:
                    params[name]["default"] = info["default"]
                    params[name]["required"] = False
                if "default_source" in info:
                    params[name]["default_source"] = info["default_source"]
                if "type" in info and info["type"]:
                    params[name]["type"] = info["type"]

    # Then enrich with docstring information
    docstring_params = extract_params_from_docstring(toolkit_class.__doc__)

    # Merge signature params with docstring params
    for name, info in docstring_params.items():
        if name in params:
            # Update existing parameter with description
            params[name]["description"] = info["description"]

            # If signature doesn't indicate default but docstring does, use docstring
            if params[name]["default"] is None and info["default"] is not None:
                params[name]["default"] = info["default"]
                params[name]["required"] = False
        else:
            # Add parameter from docstring that wasn't in signature
            params[name] = info

    return params


def get_tool_name(tool):
    """Extract the name of a tool regardless of its format.

    Args:
        tool: A tool object from a toolkit

    Returns:
        str: The name of the tool
    """
    # Check for different attribute names used in different toolkit implementations
    if hasattr(tool, "name"):
        return tool.name
    elif hasattr(tool, "function_name"):
        return tool.function_name
    elif hasattr(tool, "func") and hasattr(tool.func, "__name__"):
        return tool.func.__name__
    elif hasattr(tool, "__name__"):
        return tool.__name__

    # Default to a unique identifier if nothing else works
    return f"tool_{id(tool)}"


def create_toolkit_instance(toolkit_class, **kwargs):
    """Create an instance of a toolkit class with the given parameters.

    Args:
        toolkit_class: The toolkit class to instantiate
        **kwargs: Additional parameters to pass to the constructor

    Returns:
        An instance of the toolkit class
    """
    # Get information about the constructor parameters
    params_info = get_toolkit_class_params(toolkit_class)

    # Filter out kwargs that don't match constructor parameters
    valid_kwargs = {k: v for k, v in kwargs.items() if k in params_info}

    # Create the instance
    return toolkit_class(**valid_kwargs)


@mcp.tool()
def register_toolkit(
    toolkit_name: str, toolkit_params: Optional[Dict[str, Any]] = None
):
    """Initialize a toolkit by name and register all its tools with MCP.

    Args:
        toolkit_name: The name of the toolkit class to initialize
                     (e.g., "NotionToolkit")
        toolkit_params: Additional parameters to pass to the constructor.
                Example: {"base_url": "https://api.example.com"}

    Returns:
        dict: Information about the registered tools
    """
    # Find the module containing the toolkit
    toolkit_class = None

    # Search in all toolkit modules
    toolkit_files = [
        f
        for f in TOOLKIT_DIR.iterdir()
        if f.is_file() and f.suffix == ".py" and f.stem != "__init__"
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
    if not (inspect.isclass(toolkit_class) and issubclass(toolkit_class, BaseToolkit)):
        return {"error": f"'{toolkit_name}' is not a valid toolkit class"}

    # Get parameter information for toolkit initialization
    toolkit_init_params = get_toolkit_class_params(toolkit_class)

    # Initialize the toolkit with provided parameters
    try:
        toolkit_instance = create_toolkit_instance(
            toolkit_class, **(toolkit_params or {})
        )
    except Exception as e:
        return {
            "status": "error",
            "toolkit": toolkit_name,
            "error": str(e),
            "toolkit_params": toolkit_init_params,
            "message": (
                f"Failed to initialize toolkit: {str(e)}. "
                f"Check the required parameters."
            ),
        }

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
            function = getattr(tool, "func", tool)
            if not callable(function):
                # Skip tools without a callable function
                continue

        # Create a properly wrapped function that preserves the signature
        def create_wrapped_tool(func):
            sig = inspect.signature(func)

            @functools.wraps(func)
            def wrapped_function(*args, **kwargs):
                # Clean kwargs to match function signature
                if "args" in kwargs and "args" not in sig.parameters:
                    del kwargs["args"]

                # Call the function
                return func(*args, **kwargs)

            return wrapped_function

        wrapped_function = create_wrapped_tool(function)
        mcp.tool(name=function_name)(wrapped_function)

        # Get the description from the docstring
        doc = function.__doc__ or "No description available"

        registered_tools.append({"name": function_name, "description": doc.strip()})

    return {
        "status": "success",
        "toolkit": toolkit_name,
        "registered_tools": registered_tools,
        "total_tools": len(registered_tools),
    }


@mcp.tool()
def get_toolkit_info(toolkit_name: str):
    """Get information about a toolkit's initialization parameters.

    Args:
        toolkit_name: The name of the toolkit class to examine
                     (e.g., "TerminalToolkit")

    Returns:
        dict: Information about the toolkit's parameters
    """
    # Find the module containing the toolkit
    toolkit_class = None

    # Search in all toolkit modules
    toolkit_files = [
        f
        for f in TOOLKIT_DIR.iterdir()
        if f.is_file() and f.suffix == ".py" and f.stem != "__init__"
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
    if not (inspect.isclass(toolkit_class) and issubclass(toolkit_class, BaseToolkit)):
        return {"error": f"'{toolkit_name}' is not a valid toolkit class"}

    # Get parameter information from source and docstring
    params = get_toolkit_class_params(toolkit_class)

    # Get constructor source info for additional context
    source_info = parse_constructor_source(toolkit_class)

    return {
        "toolkit": toolkit_name,
        "parameters": params,
        "has_kwargs": source_info.get("has_kwargs", False) if source_info else False,
        "has_args": source_info.get("has_args", False) if source_info else False,
        "docstring": toolkit_class.__doc__,
    }
