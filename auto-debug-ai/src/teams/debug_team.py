"""Debug team implementation using AutoGen team patterns."""

import asyncio
from typing import List, Optional, Dict, Any, AsyncIterator
from datetime import datetime
import json
from pathlib import Path

from autogen_agentchat.teams import BaseGroupChat, Swarm, RoundRobinGroupChat
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.messages import ChatMessage, TextMessage, HandoffMessage
from autogen_agentchat.conditions import (
    MaxMessageTermination,
    TextMentionTermination,
    HandoffTermination
)
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken
import structlog

from ..agents.debug_agents import DebugAgentFactory, TaskContext
from ..config import settings
from ..memory import MemoryManager
from ..monitoring import MetricsCollector


logger = structlog.get_logger()


class DebugTeam:
    """Orchestrates the debug agent team."""
    
    def __init__(self, enable_memory: bool = True, enable_monitoring: bool = True):
        self.agents = DebugAgentFactory.create_all_agents()
        self.enable_memory = enable_memory and settings.enable_memory
        self.enable_monitoring = enable_monitoring
        self.memory_manager = MemoryManager() if self.enable_memory else None
        self.metrics = MetricsCollector() if self.enable_monitoring else None
        self.team = None
        
    def _create_team(self, coordination_mode: str = None) -> BaseGroupChat:
        """Create the agent team based on coordination mode."""
        mode = coordination_mode or settings.team.coordination_mode
        
        # Get list of agents in order
        agent_list = []
        agent_order = ["planner", "locator", "coder", "executor"]
        
        if settings.team.enable_critic:
            agent_order.append("critic")
        
        if settings.team.enable_reviewer:
            agent_order.append("reviewer")
        
        for agent_name in agent_order:
            if agent_name in self.agents:
                agent_list.append(self.agents[agent_name])
        
        # Create termination conditions
        termination_conditions = [
            MaxMessageTermination(max_messages=settings.team.max_rounds),
            TextMentionTermination("TASK_COMPLETE"),
            TextMentionTermination("TASK_FAILED"),
            HandoffTermination(target="Human")
        ]
        
        # Create team based on mode
        if mode == "swarm":
            # Swarm uses handoffs between agents
            team = Swarm(
                participants=agent_list,
                termination_condition=termination_conditions[0]  # Swarm only supports one condition
            )
        elif mode == "round_robin":
            # Round robin cycles through agents
            team = RoundRobinGroupChat(
                participants=agent_list,
                termination_condition=termination_conditions[0]
            )
        else:
            # Default to swarm
            team = Swarm(
                participants=agent_list,
                termination_condition=termination_conditions[0]
            )
        
        return team
    
    async def solve_bug(
        self,
        bug_report: str,
        context: Optional[Dict[str, Any]] = None,
        stream: bool = True
    ) -> Dict[str, Any]:
        """Solve a bug using the agent team."""
        start_time = datetime.utcnow()
        task_context = await self._create_task_context(bug_report, context)
        
        try:
            # Record start metrics
            if self.metrics:
                self.metrics.record_task_start(task_context.task_id)
            
            # Search memory for similar issues
            similar_solutions = None
            if self.memory_manager:
                similar_solutions = await self.memory_manager.search_similar_issues(bug_report)
                if similar_solutions:
                    logger.info(
                        "found_similar_solutions",
                        task_id=task_context.task_id,
                        count=len(similar_solutions)
                    )
            
            # Create team
            self.team = self._create_team()
            
            # Prepare initial message
            initial_message = self._prepare_initial_message(
                bug_report,
                task_context,
                similar_solutions
            )
            
            # Run team
            if stream:
                result = await self._run_streaming(initial_message, task_context)
            else:
                result = await self._run_batch(initial_message, task_context)
            
            # Store successful solution in memory
            if result["success"] and self.memory_manager:
                await self.memory_manager.store_solution(
                    bug_report=bug_report,
                    solution=result["solution"],
                    context=task_context.model_dump()
                )
            
            # Record completion metrics
            if self.metrics:
                self.metrics.record_task_completion(
                    task_context.task_id,
                    success=result["success"],
                    duration=(datetime.utcnow() - start_time).total_seconds()
                )
            
            return result
            
        except Exception as e:
            logger.error(
                "team_execution_error",
                task_id=task_context.task_id,
                error=str(e),
                exc_info=True
            )
            
            if self.metrics:
                self.metrics.record_task_failure(
                    task_context.task_id,
                    error=str(e)
                )
            
            return {
                "success": False,
                "error": str(e),
                "task_id": task_context.task_id,
                "duration": (datetime.utcnow() - start_time).total_seconds()
            }
    
    async def _create_task_context(
        self,
        bug_report: str,
        context: Optional[Dict[str, Any]]
    ) -> TaskContext:
        """Create task context with additional information."""
        from uuid import uuid4
        
        task_context = TaskContext(
            task_id=str(uuid4()),
            bug_report=bug_report,
            max_iterations=settings.team.max_rounds
        )
        
        # Add any provided context
        if context:
            for key, value in context.items():
                if hasattr(task_context, key):
                    setattr(task_context, key, value)
        
        return task_context
    
    def _prepare_initial_message(
        self,
        bug_report: str,
        task_context: TaskContext,
        similar_solutions: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Prepare the initial message for the team."""
        message = f"""
## Bug Report
{bug_report}

## Task ID: {task_context.task_id}
"""
        
        if similar_solutions:
            message += "\n## Similar Past Solutions\n"
            for i, solution in enumerate(similar_solutions[:3], 1):
                message += f"\n### Solution {i} (Similarity: {solution['similarity']:.2f})\n"
                message += f"{solution['content']}\n"
                if 'metadata' in solution:
                    message += f"Context: {json.dumps(solution['metadata'], indent=2)}\n"
        
        message += "\n## Instructions\n"
        message += "Please analyze this bug report and work together to create a fix. "
        message += "Start by creating a detailed plan, then locate the relevant code, "
        message += "implement a fix, test it, and validate the solution."
        
        return message
    
    async def _run_streaming(
        self,
        initial_message: str,
        task_context: TaskContext
    ) -> Dict[str, Any]:
        """Run team with streaming output."""
        messages = []
        solution = None
        success = False
        
        # Use Console UI for streaming
        async for message in Console(self.team.run_stream(task=initial_message)):
            messages.append(message)
            
            # Track progress
            if hasattr(message, 'content'):
                content = message.content
                
                # Update task context based on messages
                if "PLAN:" in content:
                    task_context.plan = self._extract_plan(content)
                elif "PATCH:" in content:
                    if task_context.proposed_patches is None:
                        task_context.proposed_patches = []
                    task_context.proposed_patches.append(self._extract_patch(content))
                elif "TEST_RESULTS:" in content:
                    task_context.test_results = self._extract_test_results(content)
                elif "TASK_COMPLETE" in content:
                    success = True
                    solution = self._extract_solution(messages)
        
        return {
            "success": success,
            "solution": solution,
            "messages": messages,
            "task_context": task_context.model_dump(),
            "task_id": task_context.task_id
        }
    
    async def _run_batch(
        self,
        initial_message: str,
        task_context: TaskContext
    ) -> Dict[str, Any]:
        """Run team in batch mode."""
        result = await self.team.run(task=initial_message)
        
        # Extract solution from result
        success = False
        solution = None
        
        if hasattr(result, 'messages'):
            for message in result.messages:
                if "TASK_COMPLETE" in str(message):
                    success = True
                    solution = self._extract_solution(result.messages)
                    break
        
        return {
            "success": success,
            "solution": solution,
            "result": result,
            "task_context": task_context.model_dump(),
            "task_id": task_context.task_id
        }
    
    def _extract_plan(self, content: str) -> List[str]:
        """Extract plan steps from message content."""
        lines = content.split('\n')
        plan = []
        in_plan = False
        
        for line in lines:
            if "PLAN:" in line:
                in_plan = True
                continue
            elif in_plan and line.strip():
                if line.strip().startswith(('-', '*', '1.', '2.', '3.')):
                    plan.append(line.strip().lstrip('-*123456789. '))
                elif not line.startswith(' '):
                    break
        
        return plan
    
    def _extract_patch(self, content: str) -> Dict[str, Any]:
        """Extract patch information from message content."""
        # Simple extraction - in production, parse structured format
        return {
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _extract_test_results(self, content: str) -> Dict[str, Any]:
        """Extract test results from message content."""
        # Simple extraction - in production, parse structured format
        return {
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _extract_solution(self, messages: List[Any]) -> Dict[str, Any]:
        """Extract the final solution from messages."""
        # Combine relevant messages into solution
        solution_parts = []
        
        for message in messages:
            if hasattr(message, 'content'):
                content = message.content
                if any(keyword in content for keyword in ["PATCH:", "FIX:", "SOLUTION:"]):
                    solution_parts.append(content)
        
        return {
            "description": "Combined solution from agent team",
            "patches": solution_parts,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_team_status(self) -> Dict[str, Any]:
        """Get current status of the team."""
        status = {
            "agents": {},
            "team_type": type(self.team).__name__ if self.team else None,
            "memory_enabled": self.enable_memory,
            "monitoring_enabled": self.enable_monitoring
        }
        
        for name, agent in self.agents.items():
            status["agents"][name] = {
                "type": type(agent).__name__,
                "active": True  # In production, check actual status
            }
        
        return status