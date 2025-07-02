"""Main entry point for Auto-Debug-AI system."""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json

import structlog
from structlog.stdlib import LoggerFactory
from python_json_logger import jsonlogger

from .config import settings
from .teams import DebugTeam
from .monitoring import MetricsCollector


# Configure structured logging
def configure_logging():
    """Configure structured logging based on settings."""
    if settings.log_format == "json":
        # JSON format for production
        logHandler = structlog.stdlib.LoggerFactory()
        formatter = jsonlogger.JsonFormatter()
        handler = structlog.stdlib.LoggerFactory()
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Human-readable format for development
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.dev.ConsoleRenderer()
            ],
            context_class=dict,
            logger_factory=LoggerFactory(),
            cache_logger_on_first_use=True,
        )


class AutoDebugAI:
    """Main application class for Auto-Debug-AI."""
    
    def __init__(self):
        configure_logging()
        self.logger = structlog.get_logger()
        self.team = None
        self.metrics = MetricsCollector() if settings.enable_telemetry else None
        
    async def initialize(self):
        """Initialize the system."""
        self.logger.info("initializing_system", settings=settings.model_dump())
        
        # Create debug team
        self.team = DebugTeam(
            enable_memory=settings.enable_memory,
            enable_monitoring=settings.enable_telemetry
        )
        
        self.logger.info("system_initialized")
        
    async def solve_bug(
        self,
        bug_report: str,
        context: Optional[Dict[str, Any]] = None,
        stream: bool = True
    ) -> Dict[str, Any]:
        """Solve a bug using the AI team."""
        if not self.team:
            await self.initialize()
        
        self.logger.info("solving_bug", bug_report_length=len(bug_report))
        
        try:
            result = await self.team.solve_bug(
                bug_report=bug_report,
                context=context,
                stream=stream
            )
            
            self.logger.info(
                "bug_solved",
                success=result.get("success", False),
                task_id=result.get("task_id")
            )
            
            return result
            
        except Exception as e:
            self.logger.error("solve_bug_error", error=str(e), exc_info=True)
            raise
    
    async def solve_bug_from_file(
        self,
        file_path: str,
        context: Optional[Dict[str, Any]] = None,
        stream: bool = True
    ) -> Dict[str, Any]:
        """Solve a bug from a file containing the bug report."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Bug report file not found: {file_path}")
        
        bug_report = path.read_text(encoding='utf-8')
        return await self.solve_bug(bug_report, context, stream)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get system status."""
        status = {
            "system": "ready" if self.team else "not_initialized",
            "settings": {
                "memory_enabled": settings.enable_memory,
                "monitoring_enabled": settings.enable_telemetry,
                "coordination_mode": settings.team.coordination_mode,
                "max_iterations": settings.team.max_rounds
            }
        }
        
        if self.team:
            status["team"] = await self.team.get_team_status()
        
        if self.metrics:
            status["metrics"] = self.metrics.get_system_metrics()
        
        return status
    
    async def shutdown(self):
        """Shutdown the system gracefully."""
        self.logger.info("shutting_down_system")
        
        # Export final metrics if enabled
        if self.metrics:
            metrics_export = self.metrics.export_metrics()
            self.logger.info("final_metrics", metrics=metrics_export)
        
        # Cleanup resources
        # In production, add cleanup for Docker clients, DB connections, etc.
        
        self.logger.info("system_shutdown_complete")


async def main_cli():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Auto-Debug-AI: Autonomous AI-powered debugging system"
    )
    
    parser.add_argument(
        "action",
        choices=["solve", "status", "server"],
        help="Action to perform"
    )
    
    parser.add_argument(
        "--bug-report",
        "-b",
        help="Bug report text or file path"
    )
    
    parser.add_argument(
        "--file",
        "-f",
        action="store_true",
        help="Treat bug-report as file path"
    )
    
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming output"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for results"
    )
    
    parser.add_argument(
        "--context",
        "-c",
        help="Additional context as JSON"
    )
    
    args = parser.parse_args()
    
    # Create application instance
    app = AutoDebugAI()
    
    try:
        if args.action == "solve":
            if not args.bug_report:
                parser.error("--bug-report is required for solve action")
            
            # Parse context if provided
            context = None
            if args.context:
                try:
                    context = json.loads(args.context)
                except json.JSONDecodeError:
                    parser.error("Invalid JSON in --context")
            
            # Solve bug
            if args.file:
                result = await app.solve_bug_from_file(
                    args.bug_report,
                    context=context,
                    stream=not args.no_stream
                )
            else:
                result = await app.solve_bug(
                    args.bug_report,
                    context=context,
                    stream=not args.no_stream
                )
            
            # Output results
            output_json = json.dumps(result, indent=2)
            
            if args.output:
                Path(args.output).write_text(output_json)
                print(f"Results written to: {args.output}")
            else:
                print("\n=== RESULTS ===")
                print(output_json)
        
        elif args.action == "status":
            status = await app.get_status()
            print(json.dumps(status, indent=2))
        
        elif args.action == "server":
            # Import and run the API server
            from .api import run_server
            await run_server(app)
        
    finally:
        await app.shutdown()


async def main_api():
    """Main API server entry point."""
    from .api import run_server
    
    app = AutoDebugAI()
    await app.initialize()
    
    try:
        await run_server(app)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    # Run CLI by default
    asyncio.run(main_cli())