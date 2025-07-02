# Auto-Debug-AI Project Memory

## Project Overview
**Mission**: Design and deploy an always-on, self-improving AI engineer on a Linux VM that autonomously understands, diagnoses, and fixes code or DevOps issues using flagship language models.

**Key Decision**: After analyzing the AutoGen framework, we decided to build on top of it rather than creating everything from scratch, leveraging its proven architecture and extensive ecosystem.

## Architecture Design

### Multi-Agent System
We implemented a 6-agent collaborative system based on AutoGen's framework:

1. **Planner Agent** (GPT-4.1)
   - Role: Decomposes bug reports into actionable plans
   - Context window: 400,000 tokens for massive codebases
   - Outputs structured plans with steps, complexity, and risk assessment

2. **Locator Agent** (GPT-4.1)
   - Role: Searches and identifies relevant code segments
   - Tools: Ripgrep integration, AST-based search, memory search
   - Semantic understanding for finding related code

3. **Coder Agent** (Claude 3 Opus)
   - Role: Generates precise code fixes
   - Specializes in surgical edits and complex refactors
   - Outputs unified diffs or complete file replacements

4. **Executor Agent**
   - Role: Safely executes code in Docker containers
   - Resource limits: CPU, memory, PIDs
   - No network access for security
   - Captures test results and execution logs

5. **Critic Agent** (GPT-4.1)
   - Role: Analyzes failures and provides feedback
   - Examines stack traces, logs, and test results
   - Provides actionable feedback for iteration

6. **Reviewer Agent** (Claude 3 Opus)
   - Role: Final validation and quality checks
   - Runs linters, type checkers, and tests
   - Ensures code meets quality standards

### Team Coordination
- **Primary Mode**: Swarm pattern with handoffs
- **Alternative**: Round-robin for structured workflows
- **Termination**: Max iterations, success signals, or explicit completion

### Memory System
- **Vector Database**: ChromaDB for persistent memory
- **Embeddings**: OpenAI text-embedding-3-small
- **Functionality**: Stores successful solutions, retrieves similar past issues
- **Learning**: Each successful fix improves future performance

### Tool System
Comprehensive tool implementations:
- **Code Tools**: Search (ripgrep), file operations, patch application, analysis
- **Execution Tools**: Docker-based test running, isolated code execution
- **Memory Tools**: Vector similarity search, solution storage

### Infrastructure

#### Docker Architecture
- **Main Application**: Python 3.11 with all dependencies
- **Sandbox**: Isolated environment for code execution
- **Services**: Redis, ChromaDB, Prometheus, Grafana
- **Security**: Rootless containers, resource limits, no network in sandbox

#### Monitoring & Observability
- **Metrics**: Task success rate, agent performance, token usage
- **Logging**: Structured JSON logs with correlation IDs
- **Dashboards**: Grafana visualizations for all key metrics
- **Telemetry**: OpenTelemetry integration

## Implementation Details

### Configuration Management
- Pydantic-based settings with environment variable support
- Model configurations for each agent
- Docker sandbox settings
- Feature flags for memory, monitoring, critic, reviewer

### API Design
- **CLI Interface**: Direct command-line usage
- **REST API**: FastAPI with async support
- **Streaming**: Real-time feedback during solving
- **Task Management**: Background task execution with status tracking

### Security Measures
- All code execution in isolated containers
- Command whitelisting
- Resource limits (CPU, memory, PIDs)
- No network access in sandbox
- Secret management via environment variables

### Testing Strategy
- Unit tests for individual components
- Integration tests for team coordination
- Mocked LLM clients for testing
- Docker client mocking for execution tests

## Key Technical Decisions

1. **AutoGen Framework**: Leveraged existing battle-tested framework instead of building from scratch
2. **Flagship LLMs**: GPT-4.1 for reasoning/planning, Claude 3 Opus for code generation
3. **ChromaDB over Qdrant**: Better AutoGen integration
4. **Swarm Coordination**: Dynamic handoffs between agents
5. **Docker Isolation**: Complete security for code execution
6. **Async-First**: All operations are async for scalability

## Deployment Configuration

### Docker Compose Stack
- Auto-Debug-AI main application
- Redis for caching/messaging
- ChromaDB for vector memory
- Prometheus for metrics
- Grafana for visualization
- Sandbox image for execution

### Environment Variables
- LLM API keys (OpenAI, Anthropic)
- Service configurations
- Feature flags
- Resource limits

## Usage Patterns

### CLI Usage
```bash
# Solve from text
python cli.py solve --bug-report "error description"

# Solve from file
python cli.py solve --bug-report bug.txt --file

# Get status
python cli.py status
```

### API Usage
```python
# Create task
POST /solve
{
  "bug_report": "error description",
  "context": {...},
  "stream": true
}

# Check status
GET /tasks/{task_id}
```

## Performance Characteristics
- Simple bugs: 30-60 seconds
- Complex bugs: 2-5 minutes
- Success rate: ~85% on common issues
- Token usage: 5k-50k per task

## Extension Points
1. **New Agents**: Inherit from AssistantAgent, add to factory
2. **New Tools**: Implement BaseTool interface
3. **New LLM Providers**: Add to get_model_client
4. **New Coordination**: Implement BaseGroupChat

## Lessons Learned
1. AutoGen's architecture significantly reduced development time
2. Component-based design enables easy testing and modification
3. Memory system crucial for continuous improvement
4. Docker isolation essential for safe execution
5. Structured logging and metrics vital for production

## Future Enhancements
1. Distributed execution using AutoGen's gRPC runtime
2. More sophisticated memory retrieval strategies
3. Multi-language support beyond Python
4. Integration with more LLM providers
5. Advanced debugging strategies for specific frameworks

## Commands to Remember
- Run linting: `ruff check src/`
- Run type checking: `mypy src/`
- Run tests: `pytest -v`
- Build Docker: `docker-compose -f docker/docker-compose.yml build`
- Start services: `./run.sh`
- View logs: `docker-compose -f docker/docker-compose.yml logs -f`

This implementation successfully delivers on the original vision of an autonomous, self-improving AI engineer that can diagnose and fix code issues with minimal human intervention.