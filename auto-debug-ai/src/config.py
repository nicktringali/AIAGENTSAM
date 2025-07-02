"""Configuration management for Auto-Debug-AI system."""

import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class ModelConfig(BaseModel):
    """Model configuration."""
    provider: str = Field(description="Model provider (openai or anthropic)")
    model: str = Field(description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key (if not in env)")
    temperature: float = Field(default=0.0, description="Temperature for generation")
    max_tokens: int = Field(default=4000, description="Maximum tokens per request")
    timeout: int = Field(default=300, description="Request timeout in seconds")


class DockerSandboxConfig(BaseModel):
    """Docker sandbox configuration."""
    image: str = Field(default="auto-debug-sandbox:latest", description="Docker image")
    memory_limit: str = Field(default="512m", description="Memory limit")
    cpu_limit: float = Field(default=0.5, description="CPU limit (cores)")
    pids_limit: int = Field(default=100, description="PIDs limit")
    timeout: int = Field(default=120, description="Execution timeout in seconds")
    work_dir: str = Field(default="/workspace", description="Working directory in container")


class MemoryConfig(BaseModel):
    """Memory system configuration."""
    provider: str = Field(default="chromadb", description="Memory provider")
    collection_name: str = Field(default="auto_debug_memory", description="Collection name")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model")
    persist_directory: Optional[str] = Field(default="./chroma_db", description="Persistence directory")


class AgentConfig(BaseModel):
    """Individual agent configuration."""
    name: str = Field(description="Agent name")
    model_config: ModelConfig = Field(description="Model configuration")
    system_prompt_file: Optional[str] = Field(default=None, description="Path to system prompt file")
    max_iterations: int = Field(default=5, description="Maximum iterations for the agent")
    enable_tools: bool = Field(default=True, description="Enable tool usage")
    enable_reflection: bool = Field(default=True, description="Enable reflection on tool use")


class TeamConfig(BaseModel):
    """Team configuration."""
    max_rounds: int = Field(default=20, description="Maximum conversation rounds")
    enable_critic: bool = Field(default=True, description="Enable critic agent")
    enable_reviewer: bool = Field(default=True, description="Enable reviewer agent")
    coordination_mode: str = Field(default="swarm", description="Coordination mode: swarm, round_robin, or selector")


class Settings(BaseSettings):
    """Main application settings."""
    
    # Model configurations
    planner_model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            provider="openai",
            model=os.getenv("PLANNER_MODEL", "gpt-4-0125-preview"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.1
        )
    )
    
    locator_model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            provider="openai",
            model=os.getenv("LOCATOR_MODEL", "gpt-4-0125-preview"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.0
        )
    )
    
    coder_model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            provider="anthropic",
            model=os.getenv("CODER_MODEL", "claude-3-opus-20240229"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.0,
            max_tokens=8000
        )
    )
    
    executor_model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            provider="openai",
            model="gpt-4-0125-preview",
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.0
        )
    )
    
    critic_model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            provider="openai",
            model=os.getenv("CRITIC_MODEL", "gpt-4-0125-preview"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.1
        )
    )
    
    reviewer_model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            provider="anthropic",
            model=os.getenv("REVIEWER_MODEL", "claude-3-opus-20240229"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.0
        )
    )
    
    # Docker sandbox
    docker_sandbox: DockerSandboxConfig = Field(
        default_factory=lambda: DockerSandboxConfig()
    )
    
    # Memory system
    memory: MemoryConfig = Field(
        default_factory=lambda: MemoryConfig()
    )
    
    # Team configuration
    team: TeamConfig = Field(
        default_factory=lambda: TeamConfig()
    )
    
    # Redis configuration
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    
    # Security
    allowed_commands: list[str] = Field(
        default_factory=lambda: ["python", "pytest", "npm", "node", "bash", "sh", "git", "pip", "poetry", "rg"],
        description="Allowed commands in sandbox"
    )
    max_file_size_mb: int = Field(default=10, description="Maximum file size in MB")
    max_context_length: int = Field(default=100000, description="Maximum context length")
    
    # Monitoring
    prometheus_port: int = Field(default=9090, description="Prometheus metrics port")
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format")
    enable_telemetry: bool = Field(default=True, description="Enable OpenTelemetry")
    
    # Features
    enable_memory: bool = Field(default=True, description="Enable memory system")
    enable_web_dashboard: bool = Field(default=False, description="Enable web dashboard")
    dashboard_port: int = Field(default=8000, description="Dashboard port")
    dashboard_host: str = Field(default="127.0.0.1", description="Dashboard host")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


def get_model_client(model_config: ModelConfig):
    """Create a model client from configuration."""
    if model_config.provider == "openai":
        from autogen_ext.models.openai import OpenAIChatCompletionClient
        return OpenAIChatCompletionClient(
            model=model_config.model,
            api_key=model_config.api_key,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            timeout=model_config.timeout
        )
    elif model_config.provider == "anthropic":
        from autogen_ext.models.anthropic import AnthropicChatCompletionClient
        return AnthropicChatCompletionClient(
            model=model_config.model,
            api_key=model_config.api_key,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            timeout=model_config.timeout
        )
    else:
        raise ValueError(f"Unknown model provider: {model_config.provider}")