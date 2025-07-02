"""Pytest configuration and fixtures."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
import os
import tempfile
from pathlib import Path

from src.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    # Disable external services
    monkeypatch.setattr(settings, "enable_memory", False)
    monkeypatch.setattr(settings, "enable_telemetry", False)
    monkeypatch.setattr(settings, "enable_web_dashboard", False)
    
    # Use test API keys
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    
    return settings


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        yield workspace


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = AsyncMock()
    client.complete = AsyncMock()
    client.complete.return_value = MagicMock(
        content="Test response",
        model="test-model",
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        raw_response=None
    )
    return client


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing."""
    client = MagicMock()
    
    # Mock container
    container = MagicMock()
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = b"Test output"
    
    client.containers.create.return_value = container
    client.containers.get.return_value = container
    
    return client


@pytest.fixture
def sample_bug_report():
    """Sample bug report for testing."""
    return """
TypeError: unsupported operand type(s) for +: 'int' and 'str'

File: calculator.py, line 15
Error occurs when trying to add user input to a number.

Stack trace:
  File "calculator.py", line 15, in calculate
    result = base_value + user_input
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""


@pytest.fixture
def sample_code_file():
    """Sample Python code with a bug."""
    return '''
def calculate(base_value, user_input):
    """Calculate result by adding user input to base value."""
    # Bug: user_input is a string, needs conversion
    result = base_value + user_input
    return result

def main():
    base = 10
    user_value = input("Enter a number: ")
    result = calculate(base, user_value)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
'''


@pytest.fixture
def sample_test_file():
    """Sample test file."""
    return '''
import pytest
from calculator import calculate

def test_calculate_with_integers():
    assert calculate(10, 5) == 15
    
def test_calculate_with_string():
    # This test will fail due to the bug
    assert calculate(10, "5") == 15
'''