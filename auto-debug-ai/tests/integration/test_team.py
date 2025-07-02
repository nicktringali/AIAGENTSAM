"""Integration tests for debug team."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio

from src.teams.debug_team import DebugTeam
from src.agents.debug_agents import TaskContext


class TestDebugTeamIntegration:
    """Integration tests for the debug team."""
    
    @pytest.mark.asyncio
    async def test_team_creation(self, mock_settings):
        """Test debug team creation."""
        with patch('src.teams.debug_team.DebugAgentFactory.create_all_agents') as mock_factory:
            # Mock agents
            mock_agents = {
                "planner": MagicMock(),
                "locator": MagicMock(),
                "coder": MagicMock(),
                "executor": MagicMock()
            }
            mock_factory.return_value = mock_agents
            
            team = DebugTeam(enable_memory=False, enable_monitoring=False)
            
            assert team.agents == mock_agents
            assert not team.enable_memory
            assert not team.enable_monitoring
    
    @pytest.mark.asyncio
    async def test_solve_bug_simple(self, mock_settings, sample_bug_report):
        """Test solving a simple bug."""
        with patch('src.teams.debug_team.DebugAgentFactory.create_all_agents') as mock_factory:
            # Create mock agents
            mock_planner = AsyncMock()
            mock_planner.name = "Planner"
            
            mock_locator = AsyncMock()
            mock_locator.name = "Locator"
            
            mock_coder = AsyncMock()
            mock_coder.name = "Coder"
            
            mock_executor = AsyncMock()
            mock_executor.name = "Executor"
            
            mock_agents = {
                "planner": mock_planner,
                "locator": mock_locator,
                "coder": mock_coder,
                "executor": mock_executor
            }
            mock_factory.return_value = mock_agents
            
            # Create team
            team = DebugTeam(enable_memory=False, enable_monitoring=False)
            
            # Mock team run
            with patch.object(team, '_create_team') as mock_create_team:
                mock_team_instance = AsyncMock()
                mock_team_instance.run = AsyncMock()
                mock_team_instance.run.return_value = MagicMock(
                    messages=["TASK_COMPLETE"]
                )
                mock_create_team.return_value = mock_team_instance
                
                # Solve bug
                result = await team.solve_bug(
                    bug_report=sample_bug_report,
                    stream=False
                )
                
                assert "task_id" in result
                assert "success" in result
                assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_task_context_creation(self):
        """Test task context creation."""
        from src.agents.debug_agents import create_debug_context
        
        bug_report = "Test bug report"
        context = await create_debug_context(bug_report)
        
        assert context.bug_report == bug_report
        assert context.task_id is not None
        assert context.iteration == 0
        assert context.max_iterations == 5