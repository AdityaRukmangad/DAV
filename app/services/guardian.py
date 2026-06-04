"""
Guardian: Lightweight Syllabus Validator (Step 5)

The Guardian validates generated questions against the course syllabus.
It checks:
1. Topic presence in syllabus
2. Unit alignment
3. Allows ONE regeneration attempt if validation fails

Config: ENABLE_GUARDIAN (default: false) for backward compatibility
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple
from difflib import SequenceMatcher
from app.tools.utils import get_logger

logger = get_logger("Guardian")

# Path to syllabus config
SYLLABUS_CONFIG_PATH = Path("config/syllabus.yaml")

class SyllabusConfig:
    """Syllabus configuration loaded from YAML"""

    def __init__(self, config_path: Path = SYLLABUS_CONFIG_PATH):
        self.config_path = config_path
        self.enabled = False
        self.units = []
        self.validation_settings = {}
        self.course_info = {}
        self.load_config()

    def load_config(self):
        """Load syllabus configuration from YAML file"""
        if not self.config_path.exists():
            logger.warning(f"Syllabus config not found at {self.config_path}. Guardian disabled.")
            return

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            self.enabled = config.get('enabled', False)
            self.units = config.get('units', [])
            self.validation_settings = config.get('validation', {})
            self.course_info = config.get('course', {})

            if self.enabled:
                logger.info(f"Guardian enabled for course: {self.course_info.get('name', 'Unknown')}")
                logger.info(f"Loaded {len(self.units)} units from syllabus")
        except Exception as e:
            logger.error(f"Failed to load syllabus config: {e}")
            self.enabled = False

    def get_all_topics(self) -> list:
        """Get flattened list of all topics from all units"""
        topics = []
        for unit in self.units:
            topics.extend(unit.get('topics', []))
        return topics

    def find_topic_unit(self, topic: str) -> Optional[int]:
        """Find which unit a topic belongs to"""
        topic_lower = topic.lower()
        for unit in self.units:
            for unit_topic in unit.get('topics', []):
                if self._is_similar(topic_lower, unit_topic.lower()):
                    return unit.get('unit')
        return None


    def _is_similar(self, text1: str, text2: str, threshold: float = 0.6) -> bool:
        """Check if two texts are similar using fuzzy matching"""
        # Exact match
        if text1 == text2:
            return True

        # Substring match
        if text1 in text2 or text2 in text1:
            return True

        # Sequence similarity
        ratio = SequenceMatcher(None, text1, text2).ratio()
        if ratio >= threshold:
            return True

        # Token-based Jaccard similarity
        tokens1 = set(text1.split())
        tokens2 = set(text2.split())
        if tokens1 and tokens2:
            intersection = len(tokens1 & tokens2)
            union = len(tokens1 | tokens2)
            jaccard = intersection / union if union > 0 else 0
            if jaccard >= threshold:
                return True

        return False


class Guardian:
    """
    Guardian Validator: Checks if questions align with syllabus
    """

    def __init__(self, config: Optional[SyllabusConfig] = None):
        self.config = config or SyllabusConfig()
        self.logger = get_logger("Guardian")

    def is_enabled(self) -> bool:
        """Check if Guardian validation is enabled"""
        return self.config.enabled

    def validate_topic(self, topic: str, bloom_level: Optional[int] = None) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Validate if a topic is in the syllabus.

        Args:
            topic: The topic to validate
            bloom_level: Bloom's taxonomy level (used for stricter threshold on high-level questions)

        Returns:
            Tuple of (is_valid, reason, unit_number)
            - is_valid: True if topic is in syllabus
            - reason: Explanation if invalid
            - unit_number: Which unit the topic belongs to (if valid)
        """
        if not self.is_enabled():
            # Guardian disabled, pass validation
            return True, None, None

        topic_lower = topic.lower()
        all_topics = self.config.get_all_topics()

        # Determine threshold based on Bloom level
        # Higher Bloom = stricter threshold to prevent creative tangents
        if bloom_level and bloom_level >= 5:
            threshold = self.config.validation_settings.get('strict_threshold', 0.8)
        else:
            threshold = self.config.validation_settings.get('similarity_threshold', 0.6)

        # Check against all syllabus topics
        for syllabus_topic in all_topics:
            syllabus_topic_lower = syllabus_topic.lower()

            # Use config's similarity method
            if self.config._is_similar(topic_lower, syllabus_topic_lower, threshold):
                # Find unit
                unit_num = self.config.find_topic_unit(topic)
                self.logger.info(f"✓ Topic '{topic}' validated (matched: '{syllabus_topic}', unit: {unit_num})")
                return True, None, unit_num

        # Topic not found in syllabus
        reason = f"Topic '{topic}' not found in course syllabus. Please choose a topic from the defined units."
        self.logger.warning(f"✗ {reason}")

        # Suggest similar topics
        suggestions = self._find_similar_topics(topic, all_topics, limit=3)
        if suggestions:
            reason += f" Similar topics: {', '.join(suggestions)}"

        return False, reason, None

    def _find_similar_topics(self, topic: str, syllabus_topics: list, limit: int = 3) -> list:
        """Find similar topics in syllabus for suggestions"""
        topic_lower = topic.lower()
        similarities = []

        for syl_topic in syllabus_topics:
            ratio = SequenceMatcher(None, topic_lower, syl_topic.lower()).ratio()
            similarities.append((syl_topic, ratio))

        # Sort by similarity and return top N
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [topic for topic, ratio in similarities[:limit] if ratio > 0.3]


# Singleton instance
_guardian_instance = None

def get_guardian() -> Guardian:
    """Get singleton Guardian instance"""
    global _guardian_instance
    if _guardian_instance is None:
        _guardian_instance = Guardian()
    return _guardian_instance
