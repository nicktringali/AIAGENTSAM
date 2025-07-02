"""Unit tests for debug agents."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.agents.debug_agents import (
    PlannerAgent, LocatorAgent, CoderAgent,
    ExecutorAgent, CriticAgent, ReviewerAgent,
    DebugAgentFactory, TaskContext
)


class TestDebugAgents:
    """Test debug agent implementations."""
    
    @pytest.mark.asyncio
    async def test_planner_agent_creation(self, mock_llm_client):
        """Test Planner agent creation."""
        with patch('src.agents.debug_agents.get_model_client', return_value=mock_llm_client):
            agent = PlannerAgent()
            
            assert agent.name == "Planner"
            assert agent.description == "Expert at analyzing bugs and creating detailed action plans"
            assert "Locator" in agent._handoffs
    
    @pytest.mark.asyncio
    async def test_locator_agent_creation(self, mock_llm_client):
        """Test Locator agent creation."""
        with patch('src.agents.debug_agents.get_model_client', return_value=mock_llm_client):
            agent = LocatorAgent()
            
            assert agent.name == "Locator"
            assert agent.description == "Expert at searching and locating relevant code segments"
            assert len(agent._tools) > 0
    
    @pytest.mark.asyncio
    async def test_coder_agent_creation(self, mock_llm_client):
        """Test Coder agent creation."""
        with patch('src.agents.debug_agents.get_model_client', return_value=mock_llm_client):
            agent = CoderAgent()
            
            assert agent.name == "Coder"
            assert agent.description == "Expert at writing clean, efficient code fixes"
            assert "Executor" in agent._handoffs
    
    @pytest.mark.asyncio
    async def test_task_context(self):
        """Test TaskContext model."""
        context = TaskContext(
            task_id="test-123",
            bug_report="Test bug",
            plan=["step1", "step2"],
            iteration=2
        )
        
        assert context.task_id == "test-123"
        assert context.bug_report == "Test bug"
        assert len(context.plan) == 2
        assert context.iteration == 2
        assert context.max_iterations == 5
    
    def test_debug_agent_factory(self, mock_llm_client):
        """Test DebugAgentFactory."""
        with patch('src.agents.debug_agents.get_model_client', return_value=mock_llm_client):
            # Test create all agents
            agents = DebugAgentFactory.create_all_agents()
            
            assert "planner" in agents
            assert "locator" in agents
            assert "coder" in agents
            assert "executor" in agents
            
            # Test create specific agent
            planner = DebugAgentFactory.create_agent("planner")
            assert isinstance(planner, PlannerAgent)
            
            # Test invalid agent type
            with pytest.raises(ValueError, match="Unknown agent type"):
                DebugAgentFactory.create_agent("invalid")