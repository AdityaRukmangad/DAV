
import logging
import logging.handlers
import sys
import os
import json
import time
import functools
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogFormat(Enum):
    STANDARD = "standard"
    JSON = "json"
    DETAILED = "detailed"


@dataclass
class LoggingConfig:
    log_level: str = "INFO"
    log_format: str = "standard"
    log_to_file: bool = True
    log_directory: str = "logs"
    max_file_size_mb: int = 10
    backup_count: int = 5
    enable_console: bool = True
    enable_json: bool = False
    
    @classmethod
    def from_environment(cls) -> 'LoggingConfig':
        return cls(
            log_level=os.getenv("HQGE_LOG_LEVEL", "INFO"),
            log_format=os.getenv("HQGE_LOG_FORMAT", "standard"),
            log_to_file=os.getenv("HQGE_LOG_TO_FILE", "true").lower() == "true",
            log_directory=os.getenv("HQGE_LOG_DIR", "logs"),
            max_file_size_mb=int(os.getenv("HQGE_LOG_MAX_SIZE_MB", "10")),
            backup_count=int(os.getenv("HQGE_LOG_BACKUP_COUNT", "5")),
            enable_console=os.getenv("HQGE_LOG_CONSOLE", "true").lower() == "true",
            enable_json=os.getenv("HQGE_LOG_JSON", "false").lower() == "true"
        )


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if hasattr(record, 'correlation_id'):
            log_data["correlation_id"] = record.correlation_id
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class DetailedFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base_format = (
            "%(asctime)s | %(levelname)-8s | %(name)-30s | "
            "%(module)-20s:%(funcName)-20s:%(lineno)-4d | "
            "%(message)s"
        )
        
        if hasattr(record, 'correlation_id'):
            base_format = f"[%(correlation_id)s] {base_format}"
        
        formatter = logging.Formatter(base_format)
        return formatter.format(record)


class CorrelationFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.correlation_id: Optional[str] = None
    
    def set_correlation_id(self, correlation_id: str):
        self.correlation_id = correlation_id
    
    def clear_correlation_id(self):
        self.correlation_id = None
    
    def filter(self, record: logging.LogRecord) -> bool:
        if self.correlation_id:
            record.correlation_id = self.correlation_id
        return True


class PerformanceMetrics:
    def __init__(self):
        self.metrics: Dict[str, list] = {}
        self.counters: Dict[str, int] = {}
        self.logger = None
    
    def record_execution_time(self, operation: str, duration_ms: float):
        if operation not in self.metrics:
            self.metrics[operation] = []
        
        self.metrics[operation].append(duration_ms)
        
        if len(self.metrics[operation]) > 1000:
            self.metrics[operation] = self.metrics[operation][-1000:]
    
    def increment_counter(self, counter_name: str, amount: int = 1):
        if counter_name not in self.counters:
            self.counters[counter_name] = 0
        self.counters[counter_name] += amount
    
    def get_statistics(self, operation: str) -> Optional[Dict[str, float]]:
        if operation not in self.metrics or not self.metrics[operation]:
            return None
        
        times = self.metrics[operation]
        sorted_times = sorted(times)
        
        return {
            "count": len(times),
            "mean_ms": sum(times) / len(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "p50_ms": sorted_times[int(len(sorted_times) * 0.50)],
            "p95_ms": sorted_times[int(len(sorted_times) * 0.95)],
            "p99_ms": sorted_times[int(len(sorted_times) * 0.99)]
        }
    
    def reset(self):
        self.metrics.clear()
        self.counters.clear()


_global_metrics = PerformanceMetrics()


def get_metrics() -> PerformanceMetrics:
    return _global_metrics


class LoggerManager:
    _initialized = False
    _config: Optional[LoggingConfig] = None
    _correlation_filter: Optional[CorrelationFilter] = None
    _loggers: Dict[str, logging.Logger] = {}
    
    @classmethod
    def initialize(cls, config: Optional[LoggingConfig] = None):
        if cls._initialized:
            return
        
        cls._config = config or LoggingConfig.from_environment()
        cls._correlation_filter = CorrelationFilter()
        
        if cls._config.log_to_file:
            cls._setup_log_directory()
        
        cls._initialized = True
    
    @classmethod
    def _setup_log_directory(cls):
        log_path = Path(cls._config.log_directory)
        log_path.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        if not cls._initialized:
            cls.initialize()
        
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(name)
        
        if logger.handlers:
            cls._loggers[name] = logger
            return logger
        
        logger.setLevel(getattr(logging, cls._config.log_level))
        
        if cls._config.enable_console:
            cls._add_console_handler(logger)
        
        if cls._config.log_to_file:
            cls._add_file_handler(logger, name)
        
        if cls._correlation_filter:
            logger.addFilter(cls._correlation_filter)
        
        logger.propagate = False
        
        cls._loggers[name] = logger
        return logger
    
    @classmethod
    def _add_console_handler(cls, logger: logging.Logger):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, cls._config.log_level))
        
        if cls._config.enable_json:
            formatter = JSONFormatter()
        elif cls._config.log_format == "detailed":
            formatter = DetailedFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    @classmethod
    def _add_file_handler(cls, logger: logging.Logger, name: str):
        safe_name = name.replace('/', '_').replace('\\', '_')
        log_file = Path(cls._config.log_directory) / f"{safe_name}.log"
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=cls._config.max_file_size_mb * 1024 * 1024,
            backupCount=cls._config.backup_count,
            encoding='utf-8'
        )
        
        file_handler.setLevel(getattr(logging, cls._config.log_level))
        
        if cls._config.enable_json:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(module)s:%(funcName)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    @classmethod
    def set_correlation_id(cls, correlation_id: str):
        if cls._correlation_filter:
            cls._correlation_filter.set_correlation_id(correlation_id)
    
    @classmethod
    def clear_correlation_id(cls):
        if cls._correlation_filter:
            cls._correlation_filter.clear_correlation_id()


def get_logger(name: str) -> logging.Logger:
    return LoggerManager.get_logger(name)


def timed_execution(operation_name: Optional[str] = None):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            logger = get_logger(func.__module__)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.debug(f"Executed {name} in {duration_ms:.2f}ms")
                _global_metrics.record_execution_time(name, duration_ms)
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(f"Failed {name} after {duration_ms:.2f}ms: {str(e)}")
                _global_metrics.increment_counter(f"{name}.errors")
                raise
        
        return wrapper
    return decorator


def log_function_call(logger: Optional[logging.Logger] = None):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_logger = logger or get_logger(func.__module__)
            
            func_logger.debug(f"Calling {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                func_logger.debug(f"Completed {func.__name__} successfully")
                return result
            except Exception as e:
                func_logger.error(f"Exception in {func.__name__}: {type(e).__name__}: {str(e)}")
                raise
        
        return wrapper
    return decorator


def initialize_logging(config: Optional[LoggingConfig] = None):
    LoggerManager.initialize(config)


def set_correlation_id(correlation_id: str):
    LoggerManager.set_correlation_id(correlation_id)


def clear_correlation_id():
    LoggerManager.clear_correlation_id()