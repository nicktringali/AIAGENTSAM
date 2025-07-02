"""Unit tests for configuration management."""

import pytest
from src.config import Settings, ModelConfig, get_model_client


class TestConfiguration:
    """Test configuration management."""
    
    def test_default_settings(self):
        """Test default settings initialization."""
        settings = Settings()
        
        assert settings.planner_model.provider == "openai"
        assert settings.coder_model.provider == "anthropic"
        assert settings.team.coordination_mode == "swarm"
        assert settings.team.max_rounds == 20
        
    def test_model_config(self):
        """Test model configuration."""
        config = ModelConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.5,
            max_tokens=2000
        )
        
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.5
        assert config.max_tokens == 2000
        
    def test_get_model_client_openai(self, monkeypatch):
        """Test OpenAI client creation."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        
        config = ModelConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key"
        )
        
        client = get_model_client(config)
        assert client is not None
        
    def test_get_model_client_anthropic(self, monkeypatch):
        """Test Anthropic client creation."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        
        config = ModelConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key="test-key"
        )
        
        client = get_model_client(config)
        assert client is not None
        
    def test_get_model_client_invalid_provider(self):
        """Test invalid provider raises error."""
        config = ModelConfig(
            provider="invalid",
            model="test"
        )
        
        with pytest.raises(ValueError, match="Unknown model provider"):
            get_model_client(config)