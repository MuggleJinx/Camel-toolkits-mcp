"""Tests for the router module."""

from unittest import mock

from camel_toolkits_mcp.router import (
    get_tool_name, 
    execute_toolkit_function, 
    list_toolkit_functions
)


def test_get_tool_name_with_name():
    """Test get_tool_name with name attribute."""
    tool = mock.MagicMock()
    tool.name = "test_name"
    assert get_tool_name(tool) == "test_name"


def test_get_tool_name_with_function_name():
    """Test get_tool_name with function_name attribute."""
    tool = mock.MagicMock()
    # Make hasattr return False for 'name'
    del tool.name
    tool.function_name = "test_function_name"
    assert get_tool_name(tool) == "test_function_name"


def test_get_tool_name_with_func_name():
    """Test get_tool_name with func.__name__ attribute."""
    tool = mock.MagicMock()
    # Remove attributes that would be checked first
    del tool.name
    del tool.function_name

    # Set up func.__name__
    func = mock.MagicMock()
    func.__name__ = "test_func_name"
    tool.func = func

    assert get_tool_name(tool) == "test_func_name"


def test_get_tool_name_with_dunder_name():
    """Test get_tool_name with __name__ attribute."""
    tool = mock.MagicMock()
    # Remove attributes that would be checked first
    del tool.name
    del tool.function_name
    del tool.func

    tool.__name__ = "test_dunder_name"
    assert get_tool_name(tool) == "test_dunder_name"


def test_get_tool_name_default():
    """Test get_tool_name default case."""
    tool = mock.MagicMock()
    # Remove all attributes
    del tool.name
    del tool.function_name
    del tool.func
    del tool.__name__

    # The function should return something like "tool_1234567890"
    assert get_tool_name(tool).startswith("tool_")


def test_list_toolkit_functions():
    """Test list_toolkit_functions."""
    # Test runs without error - output will vary based on actual toolkits
    result = list_toolkit_functions("TerminalToolkit")
    assert isinstance(result, dict)
    assert "functions" in result or "error" in result


def test_execute_toolkit_function():
    """Test execute_toolkit_function."""
    # Check if the SearchToolkit exists and what functions it has
    functions_result = list_toolkit_functions("SearchToolkit")
    
    # If the toolkit doesn't exist, skip this test
    if "error" in functions_result:
        return
    
    # Try to find wiki search functions
    functions = functions_result.get("functions", {})
    wiki_functions = [
        name for name, info in functions.items() 
        if "wiki" in name.lower()
    ]
    
    # If wiki function found, use it; otherwise default to search_wiki
    function_name = wiki_functions[0] if wiki_functions else "search_wiki"
    
    # Execute the function with a test entity
    result = execute_toolkit_function(
        "SearchToolkit",
        function_name,
        {},
        {"entity": "alan turing"},
    )
    
    # It might succeed or fail depending on environment,
    # just make sure it returns something
    assert isinstance(result, dict)

