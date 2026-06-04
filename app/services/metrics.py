"""
Module: app/services/metrics.py
Purpose: Observability and metrics for the question generation engine.
Tracks timing, success rates, and provides insights for debugging.
"""

import time
import functools
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from threading import Lock

from app.tools.utils import get_logger

logger = get_logger("Metrics")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class NodeExecution:
    """Record of a single node execution"""
    node_name: str
    start_time: float
    end_time: float
    success: bool
    error: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


@dataclass
class GenerationRun:
    """Record of a complete question generation run"""
    run_id: str
    topic: str
    difficulty: str
    question_type: Optional[str]
    start_time: float
    end_time: Optional[float] = None
    success: bool = False
    path_taken: List[str] = field(default_factory=list)  # e.g., ["scout", "theory_author", "reviewer"]
    node_executions: List[NodeExecution] = field(default_factory=list)
    final_score: Optional[int] = None
    error: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0

    @property
    def slowest_node(self) -> Optional[str]:
        if not self.node_executions:
            return None
        return max(self.node_executions, key=lambda x: x.duration_ms).node_name


# =============================================================================
# METRICS COLLECTOR
# =============================================================================

class MetricsCollector:
    """
    Singleton metrics collector for the question generation engine.
    Thread-safe for concurrent generation.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._runs: List[GenerationRun] = []
        self._current_runs: Dict[str, GenerationRun] = {}  # run_id -> run
        self._node_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total_calls": 0,
            "total_time_ms": 0,
            "successes": 0,
            "failures": 0
        })
        self._max_history = 1000  # Keep last N runs
        self._lock = Lock()

        logger.info("[Metrics] Collector initialized")

    # -------------------------------------------------------------------------
    # RUN TRACKING
    # -------------------------------------------------------------------------

    def start_run(self, run_id: str, topic: str, difficulty: str,
                  question_type: Optional[str] = None) -> None:
        """Start tracking a new generation run"""
        with self._lock:
            run = GenerationRun(
                run_id=run_id,
                topic=topic,
                difficulty=difficulty,
                question_type=question_type,
                start_time=time.time()
            )
            self._current_runs[run_id] = run
            logger.debug(f"[Metrics] Started run {run_id[:8]}...")

    def end_run(self, run_id: str, success: bool,
                final_score: Optional[int] = None, error: Optional[str] = None) -> None:
        """Complete a generation run"""
        with self._lock:
            if run_id not in self._current_runs:
                logger.warning(f"[Metrics] Unknown run_id: {run_id}")
                return

            run = self._current_runs.pop(run_id)
            run.end_time = time.time()
            run.success = success
            run.final_score = final_score
            run.error = error

            self._runs.append(run)

            # Trim history if needed
            if len(self._runs) > self._max_history:
                self._runs = self._runs[-self._max_history:]

            status = "SUCCESS" if success else "FAILED"
            logger.info(f"[Metrics] Run {run_id[:8]} {status} in {run.duration_ms:.0f}ms "
                       f"(path: {' -> '.join(run.path_taken)})")

    def record_node(self, run_id: str, node_name: str, duration_ms: float,
                    success: bool, error: Optional[str] = None) -> None:
        """Record a node execution within a run"""
        with self._lock:
            # Update global node stats
            stats = self._node_stats[node_name]
            stats["total_calls"] += 1
            stats["total_time_ms"] += duration_ms
            if success:
                stats["successes"] += 1
            else:
                stats["failures"] += 1

            # Update run-specific tracking
            if run_id in self._current_runs:
                run = self._current_runs[run_id]
                run.path_taken.append(node_name)
                run.node_executions.append(NodeExecution(
                    node_name=node_name,
                    start_time=time.time() - duration_ms/1000,
                    end_time=time.time(),
                    success=success,
                    error=error
                ))

    # -------------------------------------------------------------------------
    # STATISTICS
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Get comprehensive statistics"""
        with self._lock:
            if not self._runs:
                return {"message": "No runs recorded yet"}

            total_runs = len(self._runs)
            successful = sum(1 for r in self._runs if r.success)
            failed = total_runs - successful

            durations = [r.duration_ms for r in self._runs if r.end_time]
            avg_duration = sum(durations) / len(durations) if durations else 0

            # Path analysis
            path_counts = defaultdict(int)
            for run in self._runs:
                path_key = " -> ".join(run.path_taken)
                path_counts[path_key] += 1

            # Most common paths
            common_paths = sorted(path_counts.items(), key=lambda x: -x[1])[:5]

            # Node performance
            node_perf = {}
            for node, stats in self._node_stats.items():
                if stats["total_calls"] > 0:
                    node_perf[node] = {
                        "calls": stats["total_calls"],
                        "avg_ms": round(stats["total_time_ms"] / stats["total_calls"], 1),
                        "success_rate": round(stats["successes"] / stats["total_calls"] * 100, 1)
                    }

            # Sort by avg time (slowest first)
            node_perf = dict(sorted(node_perf.items(),
                                    key=lambda x: -x[1]["avg_ms"]))

            return {
                "summary": {
                    "total_runs": total_runs,
                    "successful": successful,
                    "failed": failed,
                    "success_rate": round(successful / total_runs * 100, 1),
                    "avg_duration_ms": round(avg_duration, 0),
                },
                "node_performance": node_perf,
                "common_paths": common_paths,
                "recent_errors": [
                    {"topic": r.topic, "error": r.error[:100] if r.error else None}
                    for r in self._runs[-10:] if not r.success and r.error
                ]
            }

    def get_node_stats(self, node_name: str) -> Dict:
        """Get stats for a specific node"""
        with self._lock:
            stats = self._node_stats.get(node_name)
            if not stats or stats["total_calls"] == 0:
                return {"message": f"No data for node: {node_name}"}

            return {
                "node": node_name,
                "total_calls": stats["total_calls"],
                "avg_duration_ms": round(stats["total_time_ms"] / stats["total_calls"], 1),
                "success_rate": round(stats["successes"] / stats["total_calls"] * 100, 1),
                "failure_count": stats["failures"]
            }

    def get_slow_runs(self, threshold_ms: float = 30000) -> List[Dict]:
        """Get runs that exceeded a duration threshold"""
        with self._lock:
            slow = [r for r in self._runs if r.duration_ms > threshold_ms]
            return [
                {
                    "run_id": r.run_id[:8],
                    "topic": r.topic,
                    "duration_ms": round(r.duration_ms, 0),
                    "slowest_node": r.slowest_node,
                    "path": r.path_taken
                }
                for r in slow[-20:]  # Last 20 slow runs
            ]

    def reset(self) -> None:
        """Reset all metrics (useful for testing)"""
        with self._lock:
            self._runs = []
            self._current_runs = {}
            self._node_stats = defaultdict(lambda: {
                "total_calls": 0,
                "total_time_ms": 0,
                "successes": 0,
                "failures": 0
            })
            logger.info("[Metrics] Reset complete")


# =============================================================================
# DECORATORS
# =============================================================================

def get_metrics() -> MetricsCollector:
    """Get the singleton metrics collector"""
    return MetricsCollector()


def timed_node(node_name: str):
    """
    Decorator to automatically time and track a graph node function.

    Usage:
        @timed_node("scout")
        def check_sources(state: AgentState) -> Dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(state, *args, **kwargs):
            metrics = get_metrics()
            run_id = state.get("_run_id", "unknown")

            start = time.time()
            error = None
            success = True

            try:
                result = func(state, *args, **kwargs)
                # Check if result indicates failure
                if isinstance(result, dict):
                    if result.get("use_fallback") or result.get("verification_error"):
                        success = False
                        error = result.get("verification_error", "fallback triggered")
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration_ms = (time.time() - start) * 1000
                metrics.record_node(run_id, node_name, duration_ms, success, error)

                level = "DEBUG" if success else "WARNING"
                logger.log(
                    getattr(logger, level.lower(), logger.debug).__self__.level,
                    f"[{node_name}] {duration_ms:.0f}ms {'OK' if success else 'FAIL'}"
                )

        return wrapper
    return decorator


def timed(name: str = None):
    """
    Simple timing decorator for any function.

    Usage:
        @timed("pdf_search")
        def search_pdf(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        label = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration_ms = (time.time() - start) * 1000
                logger.debug(f"[Timer] {label}: {duration_ms:.0f}ms")

        return wrapper
    return decorator


# =============================================================================
# CONTEXT MANAGER
# =============================================================================

class track_generation:
    """
    Context manager to track a complete generation run.

    Usage:
        with track_generation(topic, difficulty, question_type) as run_id:
            result = graph.invoke(state)
        # Automatically records success/failure
    """

    def __init__(self, topic: str, difficulty: str, question_type: Optional[str] = None):
        self.topic = topic
        self.difficulty = difficulty
        self.question_type = question_type
        self.run_id = f"{int(time.time() * 1000)}-{hash(topic) % 10000:04d}"
        self.metrics = get_metrics()
        self._result = None
        self._error = None

    def __enter__(self) -> str:
        self.metrics.start_run(
            self.run_id,
            self.topic,
            self.difficulty,
            self.question_type
        )
        return self.run_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None and self._error is None
        error = str(exc_val) if exc_val else self._error

        score = None
        if self._result and isinstance(self._result, dict):
            score = self._result.get("quality_score")

        self.metrics.end_run(self.run_id, success, score, error)
        return False  # Don't suppress exceptions

    def set_result(self, result: Any) -> None:
        """Set the generation result for score extraction"""
        self._result = result

    def set_error(self, error: str) -> None:
        """Set an error that occurred during generation"""
        self._error = error
