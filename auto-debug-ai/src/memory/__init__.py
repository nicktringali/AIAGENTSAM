"""Memory management for Auto-Debug-AI."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from ..tools.memory_tools import MemorySearchTool, MemoryStoreTool
from ..config import settings


class MemoryManager:
    """Manages memory storage and retrieval for the debug system."""
    
    def __init__(self):
        self.search_tool = MemorySearchTool()
        self.store_tool = MemoryStoreTool()
        
    async def search_similar_issues(
        self,
        bug_report: str,
        max_results: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """Search for similar past issues and solutions."""
        try:
            from autogen_core import CancellationToken
            
            result = await self.search_tool.run(
                args=self.search_tool.__class__.__bases__[0].__args__[0](
                    query=bug_report,
                    category="solution",
                    max_results=max_results,
                    similarity_threshold=0.7
                ),
                cancellation_token=CancellationToken()
            )
            
            if result.result and result.result.results:
                return result.result.results
            
            return None
            
        except Exception as e:
            # Log error but don't fail the main process
            import structlog
            logger = structlog.get_logger()
            logger.error("memory_search_error", error=str(e))
            return None
    
    async def store_solution(
        self,
        bug_report: str,
        solution: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Store a successful solution for future reference."""
        try:
            from autogen_core import CancellationToken
            
            # Prepare content
            content = f"""
## Bug Report
{bug_report}

## Solution
{json.dumps(solution, indent=2)}

## Context
Task ID: {context.get('task_id', 'unknown')}
Iterations: {context.get('iteration', 0)}
Success: True
"""
            
            # Prepare metadata
            metadata = {
                "task_id": context.get("task_id", "unknown"),
                "iterations": context.get("iteration", 0),
                "timestamp": datetime.utcnow().isoformat(),
                "plan_steps": len(context.get("plan", [])),
                "patches_applied": len(context.get("proposed_patches", [])),
                "test_passed": context.get("test_results", {}).get("success", False)
            }
            
            result = await self.store_tool.run(
                args=self.store_tool.__class__.__bases__[0].__args__[0](
                    content=content,
                    metadata=metadata,
                    category="solution"
                ),
                cancellation_token=CancellationToken()
            )
            
            return result.result.success if result.result else False
            
        except Exception as e:
            # Log error but don't fail the main process
            import structlog
            logger = structlog.get_logger()
            logger.error("memory_store_error", error=str(e))
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        try:
            # Get collection info
            _, collection = self.search_tool._get_chroma_client()
            count = collection.count()
            
            return {
                "total_memories": count,
                "collection_name": settings.memory.collection_name,
                "embedding_model": settings.memory.embedding_model,
                "status": "healthy"
            }
            
        except Exception as e:
            return {
                "total_memories": 0,
                "status": "error",
                "error": str(e)
            }