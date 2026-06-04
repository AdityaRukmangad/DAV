"""
Module: app/config/loader.py
Purpose: Load and manage configuration from YAML files.
Provides cached access to prompts, tags, and other config.
"""

import os
import yaml
from typing import Dict, List, Optional, Any
from pathlib import Path
from functools import lru_cache

from app.tools.utils import get_logger

logger = get_logger("ConfigLoader")

CONFIG_DIR = Path(__file__).parent


# =============================================================================
# PROMPT LOADER
# =============================================================================

class PromptLoader:
    """Load and cache prompts from YAML configuration"""

    _instance = None
    _prompts: Dict = None
    _tags: Dict = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._prompts is None:
            self._load_prompts()
        if self._tags is None:
            self._load_tags()

    def _load_prompts(self) -> None:
        """Load prompts from YAML file"""
        prompts_file = CONFIG_DIR / "prompts.yaml"
        try:
            with open(prompts_file, 'r') as f:
                self._prompts = yaml.safe_load(f)
            logger.info(f"[Config] Loaded prompts from {prompts_file}")
        except Exception as e:
            logger.error(f"[Config] Failed to load prompts: {e}")
            self._prompts = {}

    def _load_tags(self) -> None:
        """Load tags from YAML file"""
        tags_file = CONFIG_DIR / "tags.yaml"
        try:
            with open(tags_file, 'r') as f:
                raw_tags = yaml.safe_load(f)

            # Flatten all category tags into single dict
            self._tags = {}
            self._generic_patterns = {}

            for category, tags in raw_tags.items():
                if category == "generic_patterns":
                    self._generic_patterns = tags
                elif isinstance(tags, dict):
                    self._tags.update(tags)

            logger.info(f"[Config] Loaded {len(self._tags)} tag patterns")
        except Exception as e:
            logger.error(f"[Config] Failed to load tags: {e}")
            self._tags = {}
            self._generic_patterns = {}

    def reload(self) -> None:
        """Force reload of all config files"""
        self._load_prompts()
        self._load_tags()
        logger.info("[Config] Configuration reloaded")

    # -------------------------------------------------------------------------
    # PROMPTS
    # -------------------------------------------------------------------------

    def get_format_instruction(self, question_type: str) -> str:
        """Get format instruction for a question type"""
        instructions = self._prompts.get("format_instructions", {})
        return instructions.get(question_type, instructions.get("default", ""))

    def get_formatting_requirements(self) -> str:
        """Get general formatting requirements"""
        return self._prompts.get("formatting_requirements", "")

    def get_prompt(self, prompt_name: str, part: str = "system") -> str:
        """
        Get a prompt template by name.

        Args:
            prompt_name: e.g., "theory_question", "code_generation"
            part: "system" or "human"
        """
        prompt_config = self._prompts.get(prompt_name, {})
        return prompt_config.get(part, "")

    def get_question_template(self, question_type: str) -> str:
        """Get the question template for a type"""
        templates = self._prompts.get("question_templates", {})
        return templates.get(question_type, templates.get("short", ""))

    def format_prompt(self, prompt_name: str, part: str = "system", **kwargs) -> str:
        """
        Get a prompt and format it with provided variables.

        Args:
            prompt_name: e.g., "theory_question"
            part: "system" or "human"
            **kwargs: Variables to substitute (topic, difficulty, context, etc.)
        """
        template = self.get_prompt(prompt_name, part)
        if not template:
            return ""

        # Add common variables if not provided
        if "formatting_requirements" not in kwargs:
            kwargs["formatting_requirements"] = self.get_formatting_requirements()

        if "format_instruction" not in kwargs and "question_type" in kwargs:
            kwargs["format_instruction"] = self.get_format_instruction(kwargs["question_type"])

        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"[Config] Missing variable in prompt {prompt_name}: {e}")
            return template

    # -------------------------------------------------------------------------
    # TAGS
    # -------------------------------------------------------------------------

    def get_tags_for_topic(self, topic: str) -> List[str]:
        """Get matching tags for a topic"""
        topic_lower = topic.lower()
        tags = set()

        # Match against known patterns
        for keyword, keyword_tags in self._tags.items():
            if keyword in topic_lower:
                if isinstance(keyword_tags, list):
                    tags.update(keyword_tags)

        # Apply generic patterns
        for pattern, pattern_tags in self._generic_patterns.items():
            if pattern in topic_lower:
                if isinstance(pattern_tags, list):
                    tags.update(pattern_tags)

        return sorted(list(tags))

    def get_all_tags(self) -> Dict[str, List[str]]:
        """Get all configured tags"""
        return self._tags.copy()


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get the singleton prompt loader"""
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader


def get_format_instruction(question_type: str) -> str:
    """Convenience function to get format instruction"""
    return get_prompt_loader().get_format_instruction(question_type)


def get_prompt(prompt_name: str, part: str = "system", **kwargs) -> str:
    """Convenience function to get and format a prompt"""
    return get_prompt_loader().format_prompt(prompt_name, part, **kwargs)


def get_tags(topic: str) -> List[str]:
    """Convenience function to get tags for a topic"""
    return get_prompt_loader().get_tags_for_topic(topic)


def reload_config() -> None:
    """Reload all configuration files"""
    get_prompt_loader().reload()
