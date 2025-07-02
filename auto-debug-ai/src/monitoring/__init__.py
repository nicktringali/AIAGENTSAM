"""Monitoring and observability for Auto-Debug-AI."""

import time
from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import json

from prometheus_client import Counter, Histogram, Gauge, Info
from opentelemetry import trace, metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
import structlog

from ..config import settings


# Prometheus metrics
task_counter = Counter(
    'auto_debug_tasks_total',
    'Total number of debug tasks',
    ['status', 'agent']
)

task_duration_histogram = Histogram(
    'auto_debug_task_duration_seconds',
    'Task execution duration in seconds',
    ['status']
)

agent_calls_counter = Counter(
    'auto_debug_agent_calls_total',
    'Total number of agent calls',
    ['agent', 'status']
)

llm_tokens_counter = Counter(
    'auto_debug_llm_tokens_total',
    'Total LLM tokens used',
    ['model', 'type']  # type: prompt or completion
)

active_tasks_gauge = Gauge(
    'auto_debug_active_tasks',
    'Number of currently active tasks'
)

memory_entries_gauge = Gauge(
    'auto_debug_memory_entries',
    'Number of entries in memory system'
)

system_info = Info(
    'auto_debug_system',
    'System information'
)


class MetricsCollector:
    """Collects and manages metrics for the system."""
    
    def __init__(self):
        self.logger = structlog.get_logger()
        self.task_metrics = defaultdict(dict)
        self.agent_metrics = defaultdict(lambda: defaultdict(int))
        
        # Initialize system info
        system_info.info({
            'version': '0.1.0',
            'coordination_mode': settings.team.coordination_mode,
            'memory_enabled': str(settings.enable_memory),
            'max_iterations': str(settings.team.max_rounds)
        })
        
        # Setup OpenTelemetry if enabled
        if settings.enable_telemetry:
            self._setup_telemetry()
    
    def _setup_telemetry(self):
        """Setup OpenTelemetry providers."""
        # Setup tracing
        trace.set_tracer_provider(TracerProvider())
        self.tracer = trace.get_tracer(__name__)
        
        # Setup metrics
        reader = PrometheusMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        metrics.set_meter_provider(provider)
        self.meter = metrics.get_meter(__name__)
    
    def record_task_start(self, task_id: str):
        """Record the start of a task."""
        self.task_metrics[task_id] = {
            'start_time': time.time(),
            'status': 'in_progress'
        }
        active_tasks_gauge.inc()
        task_counter.labels(status='started', agent='system').inc()
        
        self.logger.info(
            "task_started",
            task_id=task_id,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def record_task_completion(
        self,
        task_id: str,
        success: bool,
        duration: Optional[float] = None
    ):
        """Record task completion."""
        if task_id not in self.task_metrics:
            self.logger.warning("task_not_found", task_id=task_id)
            return
        
        # Calculate duration if not provided
        if duration is None:
            start_time = self.task_metrics[task_id].get('start_time', time.time())
            duration = time.time() - start_time
        
        status = 'success' if success else 'failure'
        self.task_metrics[task_id]['status'] = status
        self.task_metrics[task_id]['duration'] = duration
        self.task_metrics[task_id]['end_time'] = time.time()
        
        # Update metrics
        active_tasks_gauge.dec()
        task_counter.labels(status=status, agent='system').inc()
        task_duration_histogram.labels(status=status).observe(duration)
        
        self.logger.info(
            "task_completed",
            task_id=task_id,
            status=status,
            duration=duration,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def record_task_failure(self, task_id: str, error: str):
        """Record task failure."""
        self.record_task_completion(task_id, success=False)
        
        self.logger.error(
            "task_failed",
            task_id=task_id,
            error=error,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def record_agent_call(
        self,
        agent_name: str,
        success: bool,
        duration: float,
        tokens_used: Optional[Dict[str, int]] = None
    ):
        """Record an agent call."""
        status = 'success' if success else 'failure'
        
        # Update call metrics
        agent_calls_counter.labels(agent=agent_name, status=status).inc()
        self.agent_metrics[agent_name]['calls'] += 1
        self.agent_metrics[agent_name]['total_duration'] += duration
        
        # Update token metrics if provided
        if tokens_used:
            model = tokens_used.get('model', 'unknown')
            if 'prompt_tokens' in tokens_used:
                llm_tokens_counter.labels(
                    model=model,
                    type='prompt'
                ).inc(tokens_used['prompt_tokens'])
                
            if 'completion_tokens' in tokens_used:
                llm_tokens_counter.labels(
                    model=model,
                    type='completion'
                ).inc(tokens_used['completion_tokens'])
            
            self.agent_metrics[agent_name]['total_tokens'] += tokens_used.get('total_tokens', 0)
        
        self.logger.info(
            "agent_call",
            agent=agent_name,
            status=status,
            duration=duration,
            tokens=tokens_used
        )
    
    def update_memory_count(self, count: int):
        """Update memory entries count."""
        memory_entries_gauge.set(count)
    
    def get_task_metrics(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for a specific task or all tasks."""
        if task_id:
            return self.task_metrics.get(task_id, {})
        
        return dict(self.task_metrics)
    
    def get_agent_metrics(self, agent_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for a specific agent or all agents."""
        if agent_name:
            metrics = self.agent_metrics.get(agent_name, {})
            if metrics and metrics.get('calls', 0) > 0:
                metrics['avg_duration'] = metrics['total_duration'] / metrics['calls']
                metrics['avg_tokens'] = metrics.get('total_tokens', 0) / metrics['calls']
            return dict(metrics)
        
        # Calculate averages for all agents
        all_metrics = {}
        for name, metrics in self.agent_metrics.items():
            agent_data = dict(metrics)
            if agent_data.get('calls', 0) > 0:
                agent_data['avg_duration'] = agent_data['total_duration'] / agent_data['calls']
                agent_data['avg_tokens'] = agent_data.get('total_tokens', 0) / agent_data['calls']
            all_metrics[name] = agent_data
        
        return all_metrics
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system metrics."""
        total_tasks = len(self.task_metrics)
        successful_tasks = sum(
            1 for task in self.task_metrics.values()
            if task.get('status') == 'success'
        )
        
        return {
            'total_tasks': total_tasks,
            'successful_tasks': successful_tasks,
            'success_rate': successful_tasks / total_tasks if total_tasks > 0 else 0,
            'active_tasks': int(active_tasks_gauge._value.get()),
            'total_agent_calls': sum(
                metrics.get('calls', 0)
                for metrics in self.agent_metrics.values()
            ),
            'total_tokens_used': sum(
                metrics.get('total_tokens', 0)
                for metrics in self.agent_metrics.values()
            )
        }
    
    def export_metrics(self, format: str = 'json') -> str:
        """Export all metrics in specified format."""
        all_metrics = {
            'system': self.get_system_metrics(),
            'tasks': self.get_task_metrics(),
            'agents': self.get_agent_metrics(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if format == 'json':
            return json.dumps(all_metrics, indent=2)
        else:
            # Add other formats as needed
            return str(all_metrics)