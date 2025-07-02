"""Code manipulation and analysis tools."""

import os
import subprocess
from typing import Optional, List, Dict, Any, Literal
from pathlib import Path
import json
import ast
import tempfile

from autogen_core import CancellationToken
from autogen_agentchat.base import TaskResult
from autogen_ext.tools import BaseTool
from pydantic import BaseModel, Field
import ripgrepy
from unidiff import PatchSet
import black
import pylint.lint
import mypy.api

from ..config import settings


class CodeSearchInput(BaseModel):
    """Input for code search tool."""
    pattern: str = Field(description="Search pattern (regex supported)")
    file_pattern: Optional[str] = Field(default=None, description="File pattern to filter (e.g., '*.py')")
    path: Optional[str] = Field(default=".", description="Path to search in")
    max_results: int = Field(default=50, description="Maximum number of results")
    context_lines: int = Field(default=2, description="Number of context lines around matches")


class CodeSearchResult(BaseModel):
    """Result from code search."""
    matches: List[Dict[str, Any]] = Field(description="List of matches with file, line, and content")
    total_matches: int = Field(description="Total number of matches found")
    truncated: bool = Field(description="Whether results were truncated")


class CodeSearchTool(BaseTool[CodeSearchInput, CodeSearchResult]):
    """Tool for searching code using ripgrep."""
    
    def __init__(self):
        super().__init__(
            name="search_code",
            description="Search for code patterns using ripgrep"
        )
    
    async def run(
        self, 
        args: CodeSearchInput, 
        cancellation_token: CancellationToken
    ) -> TaskResult[CodeSearchResult]:
        """Execute code search."""
        try:
            rg = ripgrepy.Ripgrepy(args.pattern, args.path)
            
            if args.file_pattern:
                rg = rg.glob(args.file_pattern)
            
            # Add context lines
            rg = rg.context(args.context_lines)
            
            # Execute search
            matches = []
            for match in rg:
                if len(matches) >= args.max_results:
                    break
                
                matches.append({
                    "file": str(match["data"]["path"]["text"]),
                    "line": match["data"]["line_number"],
                    "content": match["data"]["lines"]["text"],
                    "match_text": match["data"]["submatches"][0]["match"]["text"] if match["data"]["submatches"] else ""
                })
            
            result = CodeSearchResult(
                matches=matches,
                total_matches=len(matches),
                truncated=len(matches) >= args.max_results
            )
            
            return TaskResult(result, task_result_type="CodeSearchResult")
            
        except Exception as e:
            return TaskResult(
                CodeSearchResult(matches=[], total_matches=0, truncated=False),
                error=str(e)
            )


class FileReadInput(BaseModel):
    """Input for file read tool."""
    file_path: str = Field(description="Path to the file to read")
    start_line: Optional[int] = Field(default=None, description="Start line (1-indexed)")
    end_line: Optional[int] = Field(default=None, description="End line (1-indexed)")


class FileReadResult(BaseModel):
    """Result from file read."""
    content: str = Field(description="File content")
    file_path: str = Field(description="Absolute file path")
    total_lines: int = Field(description="Total number of lines in file")
    language: Optional[str] = Field(description="Detected programming language")


class FileReadTool(BaseTool[FileReadInput, FileReadResult]):
    """Tool for reading files."""
    
    def __init__(self):
        super().__init__(
            name="read_file",
            description="Read contents of a file with optional line range"
        )
    
    async def run(
        self,
        args: FileReadInput,
        cancellation_token: CancellationToken
    ) -> TaskResult[FileReadResult]:
        """Read file contents."""
        try:
            file_path = Path(args.file_path).resolve()
            
            if not file_path.exists():
                return TaskResult(
                    FileReadResult(content="", file_path=str(file_path), total_lines=0),
                    error=f"File not found: {file_path}"
                )
            
            # Check file size
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > settings.max_file_size_mb:
                return TaskResult(
                    FileReadResult(content="", file_path=str(file_path), total_lines=0),
                    error=f"File too large: {file_size_mb:.2f}MB (max: {settings.max_file_size_mb}MB)"
                )
            
            # Read file
            content = file_path.read_text(encoding='utf-8')
            lines = content.splitlines()
            total_lines = len(lines)
            
            # Apply line range if specified
            if args.start_line or args.end_line:
                start = (args.start_line or 1) - 1
                end = args.end_line or total_lines
                lines = lines[start:end]
                content = '\n'.join(lines)
            
            # Detect language
            suffix = file_path.suffix.lower()
            language_map = {
                '.py': 'python',
                '.js': 'javascript',
                '.ts': 'typescript',
                '.java': 'java',
                '.cpp': 'cpp',
                '.c': 'c',
                '.go': 'go',
                '.rs': 'rust',
                '.rb': 'ruby',
                '.php': 'php'
            }
            language = language_map.get(suffix)
            
            result = FileReadResult(
                content=content,
                file_path=str(file_path),
                total_lines=total_lines,
                language=language
            )
            
            return TaskResult(result, task_result_type="FileReadResult")
            
        except Exception as e:
            return TaskResult(
                FileReadResult(content="", file_path=args.file_path, total_lines=0),
                error=str(e)
            )


class ApplyPatchInput(BaseModel):
    """Input for applying patches."""
    patches: List[Dict[str, Any]] = Field(description="List of patches to apply")
    dry_run: bool = Field(default=False, description="Whether to only validate without applying")


class ApplyPatchResult(BaseModel):
    """Result from applying patches."""
    success: bool = Field(description="Whether all patches were applied successfully")
    applied_patches: List[str] = Field(description="List of successfully applied patches")
    failed_patches: List[Dict[str, str]] = Field(description="List of failed patches with errors")
    
    
class ApplyPatchTool(BaseTool[ApplyPatchInput, ApplyPatchResult]):
    """Tool for applying code patches."""
    
    def __init__(self):
        super().__init__(
            name="apply_patch",
            description="Apply unified diff patches to files"
        )
    
    async def run(
        self,
        args: ApplyPatchInput,
        cancellation_token: CancellationToken
    ) -> TaskResult[ApplyPatchResult]:
        """Apply patches to files."""
        applied = []
        failed = []
        
        for patch_data in args.patches:
            try:
                file_path = Path(patch_data['file_path'])
                
                if 'unified_diff' in patch_data:
                    # Apply unified diff
                    if not args.dry_run:
                        # Parse and apply patch
                        patch = PatchSet(patch_data['unified_diff'])
                        for patched_file in patch:
                            target_file = Path(patched_file.target_file)
                            if target_file.exists():
                                # Apply patch using patch command
                                with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
                                    f.write(str(patch))
                                    temp_patch = f.name
                                
                                result = subprocess.run(
                                    ['patch', '-p1', str(target_file)],
                                    input=open(temp_patch).read(),
                                    capture_output=True,
                                    text=True
                                )
                                
                                os.unlink(temp_patch)
                                
                                if result.returncode != 0:
                                    raise Exception(f"Patch failed: {result.stderr}")
                    
                    applied.append(str(file_path))
                    
                elif 'content' in patch_data:
                    # Replace entire file content
                    if not args.dry_run:
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_text(patch_data['content'], encoding='utf-8')
                    
                    applied.append(str(file_path))
                    
                else:
                    failed.append({
                        'file': str(file_path),
                        'error': 'Invalid patch format'
                    })
                    
            except Exception as e:
                failed.append({
                    'file': patch_data.get('file_path', 'unknown'),
                    'error': str(e)
                })
        
        result = ApplyPatchResult(
            success=len(failed) == 0,
            applied_patches=applied,
            failed_patches=failed
        )
        
        return TaskResult(result, task_result_type="ApplyPatchResult")


class CodeAnalysisInput(BaseModel):
    """Input for code analysis."""
    file_path: str = Field(description="File to analyze")
    analysis_type: Literal["lint", "type_check", "format_check", "all"] = Field(
        default="all",
        description="Type of analysis to perform"
    )


class CodeAnalysisResult(BaseModel):
    """Result from code analysis."""
    lint_errors: Optional[List[Dict[str, Any]]] = Field(default=None)
    type_errors: Optional[List[str]] = Field(default=None)
    format_issues: Optional[bool] = Field(default=None)
    summary: str = Field(description="Summary of analysis results")


class CodeAnalysisTool(BaseTool[CodeAnalysisInput, CodeAnalysisResult]):
    """Tool for analyzing code quality."""
    
    def __init__(self):
        super().__init__(
            name="analyze_code",
            description="Run linting, type checking, and format checking on code"
        )
    
    async def run(
        self,
        args: CodeAnalysisInput,
        cancellation_token: CancellationToken
    ) -> TaskResult[CodeAnalysisResult]:
        """Analyze code quality."""
        file_path = Path(args.file_path)
        
        if not file_path.exists():
            return TaskResult(
                CodeAnalysisResult(summary=f"File not found: {file_path}"),
                error=f"File not found: {file_path}"
            )
        
        lint_errors = None
        type_errors = None
        format_issues = None
        
        # Python-specific analysis
        if file_path.suffix == '.py':
            # Linting
            if args.analysis_type in ["lint", "all"]:
                try:
                    from pylint import epylint as lint
                    (pylint_stdout, pylint_stderr) = lint.py_run(
                        str(file_path) + ' --output-format=json',
                        return_std=True
                    )
                    lint_output = pylint_stdout.getvalue()
                    if lint_output:
                        lint_errors = json.loads(lint_output)
                except Exception as e:
                    lint_errors = [{"error": str(e)}]
            
            # Type checking
            if args.analysis_type in ["type_check", "all"]:
                try:
                    result = mypy.api.run([str(file_path)])
                    if result[0]:  # stdout
                        type_errors = result[0].strip().split('\n')
                except Exception as e:
                    type_errors = [str(e)]
            
            # Format checking
            if args.analysis_type in ["format_check", "all"]:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    formatted = black.format_str(content, mode=black.Mode())
                    format_issues = content != formatted
                except Exception as e:
                    format_issues = None
        
        # Create summary
        issues = []
        if lint_errors:
            issues.append(f"{len(lint_errors)} lint errors")
        if type_errors:
            issues.append(f"{len(type_errors)} type errors")
        if format_issues:
            issues.append("formatting issues")
        
        summary = f"Analysis complete: {', '.join(issues) if issues else 'No issues found'}"
        
        result = CodeAnalysisResult(
            lint_errors=lint_errors,
            type_errors=type_errors,
            format_issues=format_issues,
            summary=summary
        )
        
        return TaskResult(result, task_result_type="CodeAnalysisResult")