"""
Guardian: Lightweight Syllabus Validator (Step 5)

The Guardian validates generated questions against the course syllabus.
It checks:
1. Topic presence in syllabus
2. Unit alignment
3. Allows ONE regeneration attempt if validation fails

Reads the SAME syllabus (app/config/syllabus.json) used everywhere else in the
app (topic picker, PDF-to-unit matching) via SyllabusLoader — previously this
read a separate, stale config/syllabus.yaml with different units/topics, which
is why generated questions never matched a real unit and always fell back to
Unit 1.

Config: GUARDIAN_ENABLED env var (default: true) for strict validation.
Unit resolution (find_topic_unit) always runs regardless of this flag, since
it's just a syllabus lookup and analytics/unit-tagging depend on it.
"""

import os
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
from app.tools.utils import get_logger
from app.config.syllabus_loader import get_syllabus_loader

logger = get_logger("Guardian")


class SyllabusConfig:
    """Adapts SyllabusLoader (app/config/syllabus.json) to Guardian's needs."""

    def __init__(self):
        self.loader = get_syllabus_loader()
        self.enabled = os.getenv("GUARDIAN_ENABLED", "true").lower() == "true"
        self.units = self.loader.get_all_units()
        self.validation_settings = {
            "similarity_threshold": 0.5,
            "strict_threshold": 0.75,
        }
        self.course_info = self.loader.get_course_info()

        if self.enabled:
            logger.info(f"Guardian enabled for course: {self.course_info.get('name', 'Unknown')}")
            logger.info(f"Loaded {len(self.units)} units from syllabus.json")

    def get_all_topics(self) -> List[str]:
        """Get flattened list of all topic names + subtopics from all units"""
        topics = []
        for unit in self.units:
            topics.extend(self.loader.extract_all_topic_keywords(unit.get("unit_number")))
        return topics

    def find_topic_unit(self, topic: str) -> Optional[int]:
        """Find which unit a topic belongs to"""
        topic_lower = topic.lower()
        best_unit, best_score = None, 0.0
        for unit in self.units:
            unit_num = unit.get("unit_number")
            keywords = self.loader.extract_all_topic_keywords(unit_num)
            for kw in keywords:
                if self._is_similar(topic_lower, kw.lower()):
                    score = SequenceMatcher(None, topic_lower, kw.lower()).ratio()
                    if score > best_score:
                        best_unit, best_score = unit_num, score
        return best_unit

    def _is_similar(self, text1: str, text2: str, threshold: float = 0.5) -> bool:
        """Check if two texts are similar using fuzzy matching"""
        if text1 == text2:
            return True

        if text1 in text2 or text2 in text1:
            return True

        ratio = SequenceMatcher(None, text1, text2).ratio()
        if ratio >= threshold:
            return True

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
        unit_num = self.config.find_topic_unit(topic)

        if not self.is_enabled():
            # Guardian validation disabled, pass but still report resolved unit
            return True, None, unit_num

        topic_lower = topic.lower()
        all_topics = self.config.get_all_topics()

        if bloom_level and bloom_level >= 5:
            threshold = self.config.validation_settings.get("strict_threshold", 0.75)
        else:
            threshold = self.config.validation_settings.get("similarity_threshold", 0.5)

        for syllabus_topic in all_topics:
            if self.config._is_similar(topic_lower, syllabus_topic.lower(), threshold):
                self.logger.info(f"✓ Topic '{topic}' validated (matched: '{syllabus_topic}', unit: {unit_num})")
                return True, None, unit_num

        reason = f"Topic '{topic}' not found in course syllabus. Please choose a topic from the defined units."
        self.logger.warning(f"✗ {reason}")

        suggestions = self._find_similar_topics(topic, all_topics, limit=3)
        if suggestions:
            reason += f" Similar topics: {', '.join(suggestions)}"

        return False, reason, unit_num

    def _find_similar_topics(self, topic: str, syllabus_topics: List[str], limit: int = 3) -> List[str]:
        """Find similar topics in syllabus for suggestions"""
        topic_lower = topic.lower()
        similarities = []

        for syl_topic in syllabus_topics:
            ratio = SequenceMatcher(None, topic_lower, syl_topic.lower()).ratio()
            similarities.append((syl_topic, ratio))

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
