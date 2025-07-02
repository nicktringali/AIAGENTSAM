# Auto-Debug-AI 🤖

An autonomous, self-improving AI engineer that automatically diagnoses and fixes code issues using state-of-the-art language models and the AutoGen framework.

## 🌟 Features

- **Multi-Agent Architecture**: Six specialized AI agents work together to solve complex debugging tasks
- **Flagship LLMs**: Powered by GPT-4.1 (400k context) and Claude 3 Opus
- **Self-Learning**: Vector memory system stores and retrieves past solutions
- **Secure Execution**: Docker sandboxing for safe code execution
- **Production Ready**: Monitoring, logging, and API/CLI interfaces
- **Extensible**: Built on Microsoft's AutoGen framework

## 🏗️ Architecture

The system uses a multi-agent collaborative workflow:

1. **Planner** (GPT-4.1): Decomposes bug reports into actionable plans
2. **Locator** (GPT-4.1): Searches and identifies relevant code segments
3. **Coder** (Claude 3 Opus): Generates precise code fixes
4. **Executor**: Safely runs tests in Docker containers
5. **Critic** (GPT-4.1): Analyzes failures and provides feedback
6. **Reviewer** (Claude 3 Opus): Final validation and quality checks

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- OpenAI API key
- Anthropic API key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/auto-debug-ai.git
cd auto-debug-ai
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running with Docker Compose

```bash
docker-compose -f docker/docker-compose.yml up -d
```

This starts:
- Auto-Debug-AI API server (port 8000)
- Redis for caching
- ChromaDB for vector memory
- Prometheus for metrics
- Grafana for visualization (port 3000)

### CLI Usage

```bash
# Solve a bug from text
python cli.py solve --bug-report "TypeError: cannot concatenate 'str' and 'int'"

# Solve from file
python cli.py solve --bug-report bug_report.txt --file

# Get system status
python cli.py status

# Start API server
python cli.py server
```

### API Usage

```python
import httpx

# Create a debugging task
response = httpx.post("http://localhost:8000/solve", json={
    "bug_report": "ImportError: No module named 'requests'",
    "context": {"language": "python", "framework": "django"}
})

task = response.json()
print(f"Task ID: {task['task_id']}")

# Check task status
status = httpx.get(f"http://localhost:8000/tasks/{task['task_id']}").json()
print(f"Status: {status['status']}")
```

## 🔧 Configuration

Key settings in `.env`:

```bash
# LLM Models
PLANNER_MODEL=gpt-4-0125-preview
CODER_MODEL=claude-3-opus-20240229

# Features
ENABLE_MEMORY=true
ENABLE_CRITIC=true
ENABLE_REVIEWER=true

# Team Settings
COORDINATION_MODE=swarm  # or round_robin
MAX_ITERATIONS=5

# Docker Sandbox
SANDBOX_MEMORY_LIMIT=512m
SANDBOX_TIMEOUT=120
```

## 📊 Monitoring

Access monitoring dashboards:
- Prometheus metrics: http://localhost:9091
- Grafana dashboards: http://localhost:3000 (admin/admin)

Key metrics tracked:
- Task success rate
- Agent performance
- LLM token usage
- Execution times
- Memory utilization

## 🧪 Testing

Run the test suite:

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Full test suite with coverage
pytest --cov=src tests/
```

## 🔐 Security

- All code execution happens in isolated Docker containers
- Resource limits enforced (CPU, memory, PIDs)
- No network access in sandbox
- Command whitelisting
- Secret management via environment variables

## 🏃‍♂️ Development

### Project Structure

```
auto-debug-ai/
├── src/
│   ├── agents/          # Agent implementations
│   ├── tools/           # Agent tools
│   ├── teams/           # Team coordination
│   ├── memory/          # Vector memory system
│   ├── monitoring/      # Metrics and logging
│   ├── config.py        # Configuration
│   ├── main.py          # Main entry point
│   └── api.py           # FastAPI server
├── docker/              # Docker configurations
├── tests/               # Test suite
├── prompts/             # Agent system prompts
└── cli.py               # CLI interface
```

### Adding a New Agent

1. Create agent class in `src/agents/`
2. Add system prompt in `src/prompts/`
3. Register in `DebugAgentFactory`
4. Update team coordination in `src/teams/`

### Adding a New Tool

1. Create tool class in `src/tools/`
2. Implement `BaseTool` interface
3. Add to agent's tool list
4. Write tests

## 📈 Performance

Typical performance metrics:
- Simple bugs: 30-60 seconds
- Complex bugs: 2-5 minutes
- Success rate: ~85% on common issues
- Token usage: 5k-50k per task

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file

## 🙏 Acknowledgments

- Built on [Microsoft AutoGen](https://github.com/microsoft/autogen)
- Powered by OpenAI GPT-4 and Anthropic Claude
- Inspired by the vision of autonomous AI systems

## 📞 Support

- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Email: support@example.com

---

**Note**: This is an experimental system. Always review generated fixes before applying to production code.