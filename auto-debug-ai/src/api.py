"""FastAPI server for Auto-Debug-AI."""

from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from .config import settings


class BugReportRequest(BaseModel):
    """Request model for bug report submission."""
    bug_report: str = Field(description="The bug report or error description")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    stream: bool = Field(default=True, description="Whether to stream results")


class TaskResponse(BaseModel):
    """Response model for task creation."""
    task_id: str = Field(description="Unique task ID")
    status: str = Field(description="Task status")
    created_at: str = Field(description="Task creation timestamp")


class TaskStatusResponse(BaseModel):
    """Response model for task status."""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class SystemStatusResponse(BaseModel):
    """Response model for system status."""
    status: str
    version: str = "0.1.0"
    settings: Dict[str, Any]
    metrics: Optional[Dict[str, Any]] = None


# Global app instance
app_instance = None

# In-memory task storage (in production, use Redis or a database)
tasks = {}


def create_app(auto_debug_app=None) -> FastAPI:
    """Create FastAPI application."""
    global app_instance
    app_instance = auto_debug_app
    
    app = FastAPI(
        title="Auto-Debug-AI API",
        description="Autonomous AI-powered debugging system API",
        version="0.1.0"
    )
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "service": "Auto-Debug-AI",
            "version": "0.1.0",
            "status": "ready"
        }
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    @app.get("/status", response_model=SystemStatusResponse)
    async def get_status():
        """Get system status."""
        if not app_instance:
            raise HTTPException(status_code=503, detail="System not initialized")
        
        status = await app_instance.get_status()
        return SystemStatusResponse(
            status=status.get("system", "unknown"),
            settings=status.get("settings", {}),
            metrics=status.get("metrics")
        )
    
    @app.post("/solve", response_model=TaskResponse)
    async def create_task(
        request: BugReportRequest,
        background_tasks: BackgroundTasks
    ):
        """Create a new debugging task."""
        if not app_instance:
            raise HTTPException(status_code=503, detail="System not initialized")
        
        # Create task
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "request": request.model_dump()
        }
        tasks[task_id] = task
        
        # Start solving in background
        background_tasks.add_task(
            solve_task,
            task_id,
            request.bug_report,
            request.context,
            request.stream
        )
        
        return TaskResponse(
            task_id=task_id,
            status="pending",
            created_at=task["created_at"]
        )
    
    @app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
    async def get_task_status(task_id: str):
        """Get task status."""
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task = tasks[task_id]
        return TaskStatusResponse(
            task_id=task_id,
            status=task["status"],
            result=task.get("result"),
            error=task.get("error"),
            created_at=task["created_at"],
            updated_at=task["updated_at"]
        )
    
    @app.post("/solve/stream")
    async def solve_streaming(request: BugReportRequest):
        """Solve bug with streaming response."""
        if not app_instance:
            raise HTTPException(status_code=503, detail="System not initialized")
        
        async def generate():
            """Generate streaming response."""
            try:
                # Create task context
                task_id = str(uuid.uuid4())
                yield f"data: {{'event': 'task_created', 'task_id': '{task_id}'}}\n\n"
                
                # Run solving process
                result = await app_instance.solve_bug(
                    bug_report=request.bug_report,
                    context=request.context,
                    stream=True
                )
                
                # Stream result
                yield f"data: {{'event': 'task_completed', 'result': {result}}}\n\n"
                
            except Exception as e:
                yield f"data: {{'event': 'error', 'error': '{str(e)}'}}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    
    return app


async def solve_task(
    task_id: str,
    bug_report: str,
    context: Optional[Dict[str, Any]],
    stream: bool
):
    """Background task to solve bug."""
    try:
        # Update status
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # Solve bug
        result = await app_instance.solve_bug(
            bug_report=bug_report,
            context=context,
            stream=stream
        )
        
        # Update task with result
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result"] = result
        tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
    except Exception as e:
        # Update task with error
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()


async def run_server(auto_debug_app=None):
    """Run the API server."""
    app = create_app(auto_debug_app)
    
    config = uvicorn.Config(
        app,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        log_level=settings.log_level.lower()
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    # For testing
    import asyncio
    asyncio.run(run_server())