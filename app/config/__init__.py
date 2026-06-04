"""
Configuration module for the question engine.
Provides access to prompts, tags, and other configuration.
"""

from app.config.loader import (
    get_prompt_loader,
    get_format_instruction,
    get_prompt,
    get_tags,
    reload_config,
    PromptLoader
)

__all__ = [
    "get_prompt_loader",
    "get_format_instruction",
    "get_prompt",
    "get_tags",
    "reload_config",
    "PromptLoader"
]
