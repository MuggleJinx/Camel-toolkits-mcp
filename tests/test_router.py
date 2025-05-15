"""Tests for the router module."""

import pytest
from unittest import mock

from camel_toolkits_mcp.router import get_toolkits_list, get_tool_name


def test_get_tool_name():
    """Test the get_tool_name function."""
    # Test with name attribute
    tool_with_name = mock.Mock()
    tool_with_name.name = "tool_name"
    assert get_tool_name(tool_with_name) == "tool_name"
    
    # Test with function_name attribute
    tool_with_function_name = mock.Mock()
    tool_with_function_name.name = None
    tool_with_function_name.function_name = "function_name"
    assert get_tool_name(tool_with_function_name) == "function_name"
    
    # Test with func.__name__ attribute
    tool_with_func = mock.Mock()
    tool_with_func.name = None
    tool_with_func.function_name = None
    tool_with_func.func.__name__ = "func_name"
    assert get_tool_name(tool_with_func) == "func_name"
    
    # Test with __name__ attribute
    tool_with_dunder_name = mock.Mock()
    tool_with_dunder_name.name = None
    tool_with_dunder_name.function_name = None
    tool_with_dunder_name.func = None
    tool_with_dunder_name.__name__ = "dunder_name"
    assert get_tool_name(tool_with_dunder_name) == "dunder_name"
    
    # Test default case
    tool_without_name = mock.Mock()
    tool_without_name.name = None
    tool_without_name.function_name = None
    tool_without_name.func = None
    tool_without_name.__name__ = None
    assert get_tool_name(tool_without_name).startswith("tool_") 