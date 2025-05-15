"""Tests for the router module."""

from unittest import mock

from camel_toolkits_mcp.router import get_tool_name


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
