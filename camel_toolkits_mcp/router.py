import importlib
import inspect
import re
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

# Cache for toolkit classes to avoid repeated lookups
TOOLKIT_CLASS_CACHE = {}


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
        f for f in TOOLKIT_DIR.iterdir() 
        if (f.is_file() and f.suffix == '.py' and 
            f.stem != '__init__' and f.stem not in EXCLUDED_TOOLKITS)
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
                    
                    # Cache the toolkit class for later use
                    TOOLKIT_CLASS_CACHE[name] = obj
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
    pattern = r"\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\([^)]*\))?\s*:(.*?)(?=\n\s+[a-zA-Z_]|$)"
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
                default = default_str.strip('"\'')
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
            "description": description
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
            if isinstance(node, ast.FunctionDef) and node.name == '__init__':
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
            if hasattr(arg, 'annotation') and arg.annotation:
                try:
                    param_type = ast.unparse(arg.annotation)
                except (AttributeError, ValueError):
                    # ast.unparse is only available in Python 3.9+
                    param_type = "unknown"
            
            params[param_name] = {
                "required": True,  # Will be updated if default found
                "default": None,   # Will be updated if default found
                "type": param_type
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
        
        return {
            "params": params,
            "has_kwargs": has_kwargs,
            "has_args": has_args
        }
        
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
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, 
                          inspect.Parameter.VAR_KEYWORD):
            continue
            
        has_default = param.default != param.empty
        param_type = param.annotation if param.annotation != param.empty else None
        
        params[name] = {
            "required": not has_default,
            "default": param.default if has_default else None,
            "type": str(param_type) if param_type else "unknown"
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


def create_toolkit_instance(toolkit_class, **kwargs):
    """Create an instance of a toolkit class with the given parameters.
    
    Args:
        toolkit_class: The toolkit class to instantiate
        **kwargs: Additional parameters to pass to the constructor
        
    Returns:
        An instance of the toolkit class
    """
    try:
        # Create the instance with provided kwargs
        return toolkit_class(**kwargs)
    except Exception as e:
        # If error occurs with the provided parameters, try with no parameters
        if not kwargs:
            # If kwargs is already empty, re-raise the exception
            raise
        try:
            # Try creating with no parameters as fallback
            return toolkit_class()
        except Exception:
            # If both attempts fail, raise the original error
            raise e


def find_toolkit_class(toolkit_name: str):
    """Find the toolkit class by name.
    
    Args:
        toolkit_name: Name of the toolkit class to find
        
    Returns:
        The toolkit class or None if not found
    """
    # Check cache first
    if toolkit_name in TOOLKIT_CLASS_CACHE:
        return TOOLKIT_CLASS_CACHE[toolkit_name]
        
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
                
                # Verify it's a proper toolkit class
                if (inspect.isclass(toolkit_class) and 
                        issubclass(toolkit_class, BaseToolkit)):
                    # Cache for future use
                    TOOLKIT_CLASS_CACHE[toolkit_name] = toolkit_class
                    return toolkit_class
        except ImportError:
            continue
    
    return None


@mcp.tool()
def list_toolkit_functions(toolkit_name: str, include_methods: bool = True):
    """List all available functions in a toolkit.
    
    Args:
        toolkit_name: The name of the toolkit class
        include_methods: Whether to include methods defined directly on the toolkit
        
    Returns:
        dict: Dictionary containing function information
    """
    toolkit_class = find_toolkit_class(toolkit_name)
    if not toolkit_class:
        return {"error": f"Toolkit '{toolkit_name}' not found"}
    
    # Create toolkit instance
    try:
        toolkit_instance = create_toolkit_instance(toolkit_class)
    except Exception as e:
        return {
            "status": "error",
            "toolkit": toolkit_name,
            "error": str(e),
            "message": f"Failed to initialize toolkit: {str(e)}"
        }
    
    # Get all tools
    tools = toolkit_instance.get_tools()
    
    # Get function names from tools
    functions = {}
    
    for tool in tools:
        name = get_tool_name(tool)
        
        # Try to get function info
        if isinstance(tool, FunctionTool):
            doc = tool.func.__doc__ or "No description available"
            
            # Get parameter information
            params = {}
            try:
                signature = inspect.signature(tool.func)
                for param_name, param in signature.parameters.items():
                    if param_name == 'self':
                        continue
                    params[param_name] = {
                        "required": param.default == param.empty,
                        "default": None if param.default == param.empty else param.default,
                        "type": str(param.annotation) if param.annotation != param.empty else "unknown"
                    }
            except Exception:
                # If we can't get signature, create empty params dict
                pass
                
            functions[name] = {
                "type": "tool",
                "description": doc.strip(),
                "parameters": params
            }
        else:
            functions[name] = {
                "type": "tool",
                "description": "Tool function"
            }
    
    # Also check methods directly on the toolkit if requested
    if include_methods:
        for name, member in inspect.getmembers(toolkit_instance):
            # Skip internal methods and properties
            if name.startswith('_'):
                continue
                
            # Skip if already added as a tool
            if name in functions:
                continue
                
            # Add methods defined directly on the toolkit
            if inspect.ismethod(member):
                doc = member.__doc__ or "No description available"
                
                # Get parameter information
                params = {}
                try:
                    signature = inspect.signature(member)
                    for param_name, param in list(signature.parameters.items()):
                        if param_name == 'self':
                            continue
                        params[param_name] = {
                            "required": param.default == param.empty,
                            "default": None if param.default == param.empty else param.default,
                            "type": str(param.annotation) if param.annotation != param.empty else "unknown"
                        }
                except Exception:
                    # If we can't get signature, create empty params dict
                    pass
                
                functions[name] = {
                    "type": "method",
                    "description": doc.strip(),
                    "parameters": params
                }
    
    return {
        "status": "success",
        "toolkit": toolkit_name,
        "functions": functions
    }


@mcp.tool()
def execute_toolkit_function(
    toolkit_name: str,
    function_name: str,
    toolkit_params: Optional[Dict[str, Any]] = None,
    function_args: Optional[Dict[str, Any]] = None
):
    """Execute a function from a specific toolkit dynamically.
    
    Args:
        toolkit_name: Name of the toolkit class (e.g., "NotionToolkit")
        function_name: Name of the function to execute
        toolkit_params: Parameters to initialize the toolkit with
        function_args: Arguments to pass to the function
        
    Returns:
        The result of the function execution
    """
    # Find the toolkit class
    toolkit_class = find_toolkit_class(toolkit_name)
    if not toolkit_class:
        return {"error": f"Toolkit '{toolkit_name}' not found"}
    
    # Initialize the toolkit
    try:
        toolkit_instance = create_toolkit_instance(
            toolkit_class, 
            **(toolkit_params or {})
        )
    except Exception as e:
        return {
            "status": "error",
            "toolkit": toolkit_name,
            "error": str(e),
            "message": f"Failed to initialize toolkit: {str(e)}"
        }
    
    # Get tools from the toolkit
    tools = toolkit_instance.get_tools()
    
    # Check for exact match in tools
    target_tool = None
    target_function = None
    
    # First try exact match in tools
    for tool in tools:
        tool_name = get_tool_name(tool)
        
        if tool_name == function_name:
            target_tool = tool
            
            # Get the actual function
            if isinstance(tool, FunctionTool):
                target_function = tool.func
            else:
                target_function = getattr(tool, 'func', tool)
                
            if not callable(target_function):
                return {
                    "status": "error",
                    "message": f"Function '{function_name}' is not callable"
                }
                
            break
    
    # If not found in tools, check if it's a method on the toolkit
    if not target_function:
        if hasattr(toolkit_instance, function_name):
            potential_method = getattr(toolkit_instance, function_name)
            if callable(potential_method):
                target_function = potential_method
        
    # If still not found, try case-insensitive search
    if not target_function:
        # Try case-insensitive search in tools
        for tool in tools:
            tool_name = get_tool_name(tool)
            
            if tool_name.lower() == function_name.lower():
                if isinstance(tool, FunctionTool):
                    target_function = tool.func
                else:
                    target_function = getattr(tool, 'func', tool)
                    
                if callable(target_function):
                    break
        
        # Try case-insensitive search in methods
        if not target_function:
            for name in dir(toolkit_instance):
                if name.lower() == function_name.lower():
                    potential_method = getattr(toolkit_instance, name)
                    if callable(potential_method) and not name.startswith('_'):
                        target_function = potential_method
                        break
    
    # If still not found, return error with available functions
    if not target_function:
        # Get the list of available functions for better error message
        available_functions = []
        
        # Add tool functions
        for tool in tools:
            available_functions.append(get_tool_name(tool))
            
        # Add methods defined on the toolkit
        for name, member in inspect.getmembers(toolkit_instance):
            if (not name.startswith('_') and 
                    inspect.ismethod(member) and 
                    name not in available_functions):
                available_functions.append(name)
                
        return {
            "status": "error",
            "message": f"Function '{function_name}' not found in toolkit '{toolkit_name}'",
            "available_functions": available_functions
        }
    
    # Execute the function
    try:
        result = target_function(**(function_args or {}))
        return {
            "status": "success",
            "toolkit": toolkit_name,
            "function": function_name,
            "result": result
        }
    except Exception as e:
        error_msg = f"Error executing function: {str(e)}"
        return {
            "status": "error",
            "toolkit": toolkit_name,
            "function": function_name,
            "error": str(e),
            "message": error_msg
        }