"""Debug agents implementation using AutoGen framework."""

import os
from typing import List, Dict, Any, Optional, Sequence
from pathlib import Path
import json
import asyncio
from datetime import datetime

from autogen_agentchat.agents import AssistantAgent, BaseChatAgent
from autogen_agentchat.messages import (
    TextMessage, 
    HandoffMessage, 
    ToolCallMessage, 
    ToolCallResultMessage,
    ChatMessage
)
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.anthropic import AnthropicChatCompletionClient
from pydantic import BaseModel, Field

from ..config import settings, get_model_client
from ..tools import (
    CodeSearchTool,
    FileReadTool,
    ApplyPatchTool,
    RunTestsTool,
    CodeAnalysisTool,
    MemorySearchTool
)


class TaskContext(BaseModel):
    """Shared context for the debugging task."""
    task_id: str = Field(description="Unique task ID")
    bug_report: str = Field(description="Original bug report")
    plan: Optional[List[str]] = Field(default=None, description="Task plan")
    located_files: Optional[List[str]] = Field(default=None, description="Located relevant files")
    proposed_patches: Optional[List[Dict[str, Any]] = Field(default=None, description="Proposed code patches")
    test_results: Optional[Dict[str, Any]] = Field(default=None, description="Test execution results")
    critique: Optional[str] = Field(default=None, description="Critique feedback")
    iteration: int = Field(default=0, description="Current iteration")
    max_iterations: int = Field(default=5, description="Maximum allowed iterations")


class PlannerAgent(AssistantAgent):
    """Agent responsible for analyzing bugs and creating action plans."""
    
    def __init__(self, model_client=None):
        if model_client is None:
            model_client = get_model_client(settings.planner_model)
        
        system_prompt = Path(__file__).parent.parent / "prompts" / "planner_prompt.txt"
        system_message = system_prompt.read_text() if system_prompt.exists() else ""
        
        super().__init__(
            name="Planner",
            model_client=model_client,
            system_message=system_message,
            description="Expert at analyzing bugs and creating detailed action plans",
            handoffs=["Locator"]
        )


class LocatorAgent(AssistantAgent):
    """Agent responsible for locating relevant code and files."""
    
    def __init__(self, model_client=None):
        if model_client is None:
            model_client = get_model_client(settings.locator_model)
        
        system_prompt = Path(__file__).parent.parent / "prompts" / "locator_prompt.txt"
        system_message = system_prompt.read_text() if system_prompt.exists() else ""
        
        # Initialize search tools
        tools = [
            CodeSearchTool(),
            FileReadTool(),
            MemorySearchTool() if settings.enable_memory else None
        ]
        tools = [t for t in tools if t is not None]
        
        super().__init__(
            name="Locator",
            model_client=model_client,
            system_message=system_message,
            tools=tools,
            description="Expert at searching and locating relevant code segments",
            handoffs=["Coder", "Planner"]
        )


class CoderAgent(AssistantAgent):
    """Agent responsible for writing code fixes."""
    
    def __init__(self, model_client=None):
        if model_client is None:
            model_client = get_model_client(settings.coder_model)
        
        system_prompt = Path(__file__).parent.parent / "prompts" / "coder_prompt.txt"
        system_message = system_prompt.read_text() if system_prompt.exists() else ""
        
        # Initialize coding tools
        tools = [
            FileReadTool(),
            CodeAnalysisTool()
        ]
        
        super().__init__(
            name="Coder",
            model_client=model_client,
            system_message=system_message,
            tools=tools,
            description="Expert at writing clean, efficient code fixes",
            handoffs=["Executor", "Locator"]
        )


class ExecutorAgent(AssistantAgent):
    """Agent responsible for executing code and running tests."""
    
    def __init__(self, model_client=None):
        if model_client is None:
            model_client = get_model_client(settings.executor_model)
        
        system_prompt = Path(__file__).parent.parent / "prompts" / "executor_prompt.txt"
        system_message = system_prompt.read_text() if system_prompt.exists() else ""
        
        # Initialize execution tools
        tools = [
            ApplyPatchTool(),
            RunTestsTool()
        ]
        
        super().__init__(
            name="Executor",
            model_client=model_client,
            system_message=system_message,
            tools=tools,
            description="Expert at safely executing code and running tests",
            handoffs=["Critic", "Reviewer"]
        )


class CriticAgent(AssistantAgent):
    """Agent responsible for analyzing failures and providing feedback."""
    
    def __init__(self, model_client=None):
        if model_client is None:
            model_client = get_model_client(settings.critic_model)
        
        system_prompt = Path(__file__).parent.parent / "prompts" / "critic_prompt.txt"
        system_message = system_prompt.read_text() if system_prompt.exists() else ""
        
        super().__init__(
            name="Critic",
            model_client=model_client,
            system_message=system_message,
            description="Expert at analyzing failures and providing actionable feedback",
            handoffs=["Coder", "Planner"]
        )


class ReviewerAgent(AssistantAgent):
    """Agent responsible for final code review and validation."""
    
    def __init__(self, model_client=None):
        if model_client is None:
            model_client = get_model_client(settings.reviewer_model)
        
        system_prompt = Path(__file__).parent.parent / "prompts" / "reviewer_prompt.txt"
        system_message = system_prompt.read_text() if system_prompt.exists() else ""
        
        # Initialize review tools
        tools = [
            FileReadTool(),
            CodeAnalysisTool(),
            RunTestsTool()
        ]
        
        super().__init__(
            name="Reviewer",
            model_client=model_client,
            system_message=system_message,
            tools=tools,
            description="Senior engineer conducting final code reviews",
            handoffs=["Coder"]  # Can request changes from coder
        )


class DebugAgentFactory:
    """Factory for creating debug agents."""
    
    @staticmethod
    def create_all_agents() -> Dict[str, BaseChatAgent]:
        """Create all debug agents with their configurations."""
        agents = {
            "planner": PlannerAgent(),
            "locator": LocatorAgent(),
            "coder": CoderAgent(),
            "executor": ExecutorAgent()
        }
        
        # Optionally add critic and reviewer
        if settings.team.enable_critic:
            agents["critic"] = CriticAgent()
        
        if settings.team.enable_reviewer:
            agents["reviewer"] = ReviewerAgent()
        
        return agents
    
    @staticmethod
    def create_agent(agent_type: str) -> BaseChatAgent:
        """Create a specific agent by type."""
        agent_map = {
            "planner": PlannerAgent,
            "locator": LocatorAgent,
            "coder": CoderAgent,
            "executor": ExecutorAgent,
            "critic": CriticAgent,
            "reviewer": ReviewerAgent
        }
        
        if agent_type not in agent_map:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        return agent_map[agent_type]()


async def create_debug_context(bug_report: str) -> TaskContext:
    """Create initial task context from bug report."""
    from uuid import uuid4
    
    return TaskContext(
        task_id=str(uuid4()),
        bug_report=bug_report,
        max_iterations=settings.team.max_rounds
    )