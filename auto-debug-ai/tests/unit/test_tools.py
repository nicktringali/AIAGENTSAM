"""Unit tests for agent tools."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile

from autogen_core import CancellationToken
from src.tools.code_tools import (
    CodeSearchTool, CodeSearchInput,
    FileReadTool, FileReadInput,
    ApplyPatchTool, ApplyPatchInput,
    CodeAnalysisTool, CodeAnalysisInput
)
from src.tools.execution_tools import (
    RunTestsTool, RunTestsInput,
    ExecuteCodeTool, ExecuteCodeInput
)


class TestCodeTools:
    """Test code manipulation tools."""
    
    @pytest.mark.asyncio
    async def test_code_search_tool(self):
        """Test code search functionality."""
        tool = CodeSearchTool()
        
        with patch('ripgrepy.Ripgrepy') as mock_rg:
            # Mock ripgrep results
            mock_rg.return_value = [
                {
                    "data": {
                        "path": {"text": "test.py"},
                        "line_number": 10,
                        "lines": {"text": "def test_function():"},
                        "submatches": [{"match": {"text": "test"}}]
                    }
                }
            ]
            
            args = CodeSearchInput(
                pattern="test",
                file_pattern="*.py",
                path=".",
                max_results=10
            )
            
            result = await tool.run(args, CancellationToken())
            
            assert result.result is not None
            assert len(result.result.matches) > 0
            assert result.result.matches[0]["file"] == "test.py"
    
    @pytest.mark.asyncio
    async def test_file_read_tool(self, temp_workspace, sample_code_file):
        """Test file reading functionality."""
        tool = FileReadTool()
        
        # Create test file
        test_file = temp_workspace / "test.py"
        test_file.write_text(sample_code_file)
        
        args = FileReadInput(
            file_path=str(test_file),
            start_line=1,
            end_line=5
        )
        
        result = await tool.run(args, CancellationToken())
        
        assert result.result is not None
        assert "def calculate" in result.result.content
        assert result.result.language == "python"
        assert result.result.total_lines > 0
    
    @pytest.mark.asyncio
    async def test_apply_patch_tool(self, temp_workspace):
        """Test patch application."""
        tool = ApplyPatchTool()
        
        # Create test file
        test_file = temp_workspace / "test.py"
        test_file.write_text("original content")
        
        args = ApplyPatchInput(
            patches=[{
                "file_path": str(test_file),
                "content": "new content"
            }],
            dry_run=False
        )
        
        result = await tool.run(args, CancellationToken())
        
        assert result.result is not None
        assert result.result.success
        assert len(result.result.applied_patches) == 1
        assert test_file.read_text() == "new content"


class TestExecutionTools:
    """Test code execution tools."""
    
    @pytest.mark.asyncio
    async def test_run_tests_tool(self, mock_docker_client):
        """Test test execution functionality."""
        tool = RunTestsTool()
        tool.docker_client = mock_docker_client
        
        args = RunTestsInput(
            working_directory=".",
            test_command="pytest",
            timeout=30
        )
        
        result = await tool.run(args, CancellationToken())
        
        assert result.result is not None
        assert result.result.output == "Test output"
        assert result.result.exit_code == 0
        assert result.result.success
    
    @pytest.mark.asyncio
    async def test_execute_code_tool(self):
        """Test code execution functionality."""
        tool = ExecuteCodeTool()
        
        with patch.object(tool, '_get_executor') as mock_executor:
            # Mock executor
            executor = AsyncMock()
            executor.execute_code_blocks = AsyncMock()
            executor.execute_code_blocks.return_value = MagicMock(
                output="Hello World",
                exit_code=0
            )
            mock_executor.return_value = executor
            
            args = ExecuteCodeInput(
                code='print("Hello World")',
                language="python",
                timeout=10
            )
            
            result = await tool.run(args, CancellationToken())
            
            assert result.result is not None
            assert result.result.success
            assert "Hello World" in result.result.output