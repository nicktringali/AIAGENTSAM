"""Code execution tools with Docker sandboxing."""

import os
import asyncio
import tempfile
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
import shutil

from autogen_core import CancellationToken
from autogen_agentchat.base import TaskResult
from autogen_ext.tools import BaseTool
from autogen_ext.code_executors import DockerCodeExecutor
from pydantic import BaseModel, Field
import docker
from docker.errors import DockerException

from ..config import settings


class RunTestsInput(BaseModel):
    """Input for running tests."""
    working_directory: str = Field(default=".", description="Working directory for tests")
    test_command: Optional[str] = Field(default=None, description="Test command to run")
    test_files: Optional[List[str]] = Field(default=None, description="Specific test files to run")
    timeout: int = Field(default=120, description="Timeout in seconds")
    environment: Dict[str, str] = Field(default_factory=dict, description="Environment variables")


class RunTestsResult(BaseModel):
    """Result from running tests."""
    success: bool = Field(description="Whether all tests passed")
    output: str = Field(description="Combined stdout and stderr")
    exit_code: int = Field(description="Process exit code")
    tests_run: Optional[int] = Field(default=None, description="Number of tests run")
    tests_passed: Optional[int] = Field(default=None, description="Number of tests passed")
    tests_failed: Optional[int] = Field(default=None, description="Number of tests failed")
    execution_time: float = Field(description="Execution time in seconds")
    
    
class RunTestsTool(BaseTool[RunTestsInput, RunTestsResult]):
    """Tool for running tests in Docker sandbox."""
    
    def __init__(self):
        super().__init__(
            name="run_tests",
            description="Run tests in an isolated Docker container"
        )
        self.docker_client = None
        
    def _get_docker_client(self):
        """Get or create Docker client."""
        if self.docker_client is None:
            try:
                self.docker_client = docker.from_env()
            except DockerException as e:
                raise RuntimeError(f"Failed to connect to Docker: {e}")
        return self.docker_client
    
    def _detect_test_command(self, working_dir: Path) -> Optional[str]:
        """Detect appropriate test command based on project structure."""
        # Python projects
        if (working_dir / "pytest.ini").exists() or (working_dir / "pyproject.toml").exists():
            return "pytest -xvs"
        elif (working_dir / "setup.py").exists():
            return "python -m pytest"
        elif (working_dir / "manage.py").exists():
            return "python manage.py test"
        
        # JavaScript/TypeScript projects
        elif (working_dir / "package.json").exists():
            try:
                with open(working_dir / "package.json") as f:
                    package = json.load(f)
                    scripts = package.get("scripts", {})
                    if "test" in scripts:
                        return "npm test"
                    elif "jest" in scripts:
                        return "npm run jest"
            except:
                pass
        
        # Go projects
        elif (working_dir / "go.mod").exists():
            return "go test ./..."
        
        # Rust projects
        elif (working_dir / "Cargo.toml").exists():
            return "cargo test"
        
        # Default Python
        return "python -m pytest"
    
    async def run(
        self,
        args: RunTestsInput,
        cancellation_token: CancellationToken
    ) -> TaskResult[RunTestsResult]:
        """Run tests in Docker container."""
        import time
        start_time = time.time()
        
        try:
            client = self._get_docker_client()
            working_dir = Path(args.working_directory).resolve()
            
            # Detect test command if not provided
            test_command = args.test_command
            if not test_command:
                test_command = self._detect_test_command(working_dir)
            
            # Add specific test files if provided
            if args.test_files:
                test_command += " " + " ".join(args.test_files)
            
            # Prepare Docker configuration
            container_config = {
                "image": settings.docker_sandbox.image,
                "command": ["/bin/bash", "-c", test_command],
                "working_dir": settings.docker_sandbox.work_dir,
                "volumes": {
                    str(working_dir): {
                        "bind": settings.docker_sandbox.work_dir,
                        "mode": "rw"
                    }
                },
                "environment": args.environment,
                "mem_limit": settings.docker_sandbox.memory_limit,
                "cpu_quota": int(settings.docker_sandbox.cpu_limit * 100000),
                "pids_limit": settings.docker_sandbox.pids_limit,
                "network_mode": "none",  # No network access
                "security_opt": ["no-new-privileges"],
                "read_only": False,  # Allow writing test artifacts
                "remove": True,  # Auto-remove container after exit
                "detach": True
            }
            
            # Create and start container
            container = client.containers.create(**container_config)
            container.start()
            
            # Wait for completion with timeout
            try:
                exit_status = await asyncio.wait_for(
                    asyncio.to_thread(container.wait),
                    timeout=args.timeout
                )
                exit_code = exit_status['StatusCode']
            except asyncio.TimeoutError:
                container.kill()
                return TaskResult(
                    RunTestsResult(
                        success=False,
                        output="Test execution timed out",
                        exit_code=-1,
                        execution_time=args.timeout
                    ),
                    error=f"Tests timed out after {args.timeout} seconds"
                )
            
            # Get logs
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            
            # Parse test results from output
            tests_run = None
            tests_passed = None
            tests_failed = None
            
            # Try to parse pytest output
            if "pytest" in test_command:
                import re
                # Look for pytest summary
                summary_match = re.search(r'(\d+) passed(?:, (\d+) failed)?(?:, (\d+) error)?', logs)
                if summary_match:
                    tests_passed = int(summary_match.group(1))
                    tests_failed = int(summary_match.group(2) or 0) + int(summary_match.group(3) or 0)
                    tests_run = tests_passed + tests_failed
            
            # Try to parse npm/jest output
            elif "npm test" in test_command or "jest" in test_command:
                import re
                # Look for jest summary
                summary_match = re.search(r'Tests:\s+(\d+) passed(?:, (\d+) failed)?(?:, (\d+) total)?', logs)
                if summary_match:
                    tests_passed = int(summary_match.group(1))
                    tests_failed = int(summary_match.group(2) or 0)
                    tests_run = int(summary_match.group(3) or tests_passed + tests_failed)
            
            execution_time = time.time() - start_time
            
            result = RunTestsResult(
                success=exit_code == 0,
                output=logs,
                exit_code=exit_code,
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                execution_time=execution_time
            )
            
            return TaskResult(result, task_result_type="RunTestsResult")
            
        except Exception as e:
            execution_time = time.time() - start_time
            return TaskResult(
                RunTestsResult(
                    success=False,
                    output=str(e),
                    exit_code=-1,
                    execution_time=execution_time
                ),
                error=str(e)
            )


class ExecuteCodeInput(BaseModel):
    """Input for executing arbitrary code."""
    code: str = Field(description="Code to execute")
    language: str = Field(default="python", description="Programming language")
    timeout: int = Field(default=30, description="Timeout in seconds")
    working_directory: Optional[str] = Field(default=None, description="Working directory")


class ExecuteCodeResult(BaseModel):
    """Result from code execution."""
    success: bool = Field(description="Whether execution completed successfully")
    output: str = Field(description="Combined stdout and stderr")
    exit_code: int = Field(description="Process exit code")
    execution_time: float = Field(description="Execution time in seconds")


class ExecuteCodeTool(BaseTool[ExecuteCodeInput, ExecuteCodeResult]):
    """Tool for executing arbitrary code in sandbox."""
    
    def __init__(self):
        super().__init__(
            name="execute_code",
            description="Execute code snippets in an isolated environment"
        )
        self.executor = None
    
    def _get_executor(self):
        """Get or create code executor."""
        if self.executor is None:
            self.executor = DockerCodeExecutor(
                image=settings.docker_sandbox.image,
                timeout=settings.docker_sandbox.timeout,
                work_dir=settings.docker_sandbox.work_dir
            )
        return self.executor
    
    async def run(
        self,
        args: ExecuteCodeInput,
        cancellation_token: CancellationToken
    ) -> TaskResult[ExecuteCodeResult]:
        """Execute code in sandbox."""
        import time
        start_time = time.time()
        
        try:
            executor = self._get_executor()
            
            # Create code block based on language
            code_blocks = [{
                "code": args.code,
                "language": args.language
            }]
            
            # Execute code
            result = await executor.execute_code_blocks(
                code_blocks,
                cancellation_token=cancellation_token
            )
            
            execution_time = time.time() - start_time
            
            # Extract output
            output = result.output if hasattr(result, 'output') else str(result)
            exit_code = result.exit_code if hasattr(result, 'exit_code') else (0 if result else 1)
            
            return TaskResult(
                ExecuteCodeResult(
                    success=exit_code == 0,
                    output=output,
                    exit_code=exit_code,
                    execution_time=execution_time
                ),
                task_result_type="ExecuteCodeResult"
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return TaskResult(
                ExecuteCodeResult(
                    success=False,
                    output=str(e),
                    exit_code=-1,
                    execution_time=execution_time
                ),
                error=str(e)
            )