"""
Syllabus Loader and Matcher
Loads syllabus JSON and provides utilities to match PDF content with syllabus topics
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from app.tools.utils import get_logger

logger = get_logger("SyllabusLoader")

class SyllabusLoader:
    def __init__(self, syllabus_path: Optional[str] = None):
        if syllabus_path is None:
            syllabus_path = str(Path(__file__).parent / "syllabus.json")
        
        self.syllabus_path = Path(syllabus_path)
        self.syllabus_data = self._load_syllabus()
        
    def _load_syllabus(self) -> Dict[str, Any]:
        """Load syllabus from JSON file"""
        try:
            with open(self.syllabus_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded syllabus: {data.get('course_name', 'Unknown')}")
                return data
        except Exception as e:
            logger.error(f"Failed to load syllabus: {e}")
            return {}
    
    def get_unit_by_number(self, unit_number: int) -> Optional[Dict[str, Any]]:
        """Get unit data by unit number"""
        units = self.syllabus_data.get('units', [])
        for unit in units:
            if unit.get('unit_number') == unit_number:
                return unit
        return None
    
    def get_all_units(self) -> List[Dict[str, Any]]:
        """Get all units"""
        return self.syllabus_data.get('units', [])
    
    def get_unit_topics(self, unit_number: int) -> List[Dict[str, Any]]:
        """Get topics for a specific unit"""
        unit = self.get_unit_by_number(unit_number)
        return unit.get('topics', []) if unit else []
    
    def extract_all_topic_keywords(self, unit_number: int) -> List[str]:
        """Extract all topic names and subtopics as keywords for a unit"""
        topics = self.get_unit_topics(unit_number)
        keywords = []
        
        for topic in topics:
            # Add main topic name
            keywords.append(topic['name'])
            
            # Add all subtopics
            for subtopic in topic.get('subtopics', []):
                keywords.append(subtopic)
        
        return keywords
    
    def match_unit_for_pdf(self, pdf_filename: str) -> Optional[int]:
        """
        Try to determine which unit a PDF belongs to based on filename
        Returns unit number if match found, None otherwise
        """
        filename_lower = pdf_filename.lower()
        
        # Common patterns: "unit-1", "unit 1", "unit1", "u1", "aiml_unit-1.pdf"
        for unit in self.get_all_units():
            unit_num = unit['unit_number']
            patterns = [
                f"unit-{unit_num}",
                f"unit {unit_num}",
                f"unit{unit_num}",
                f"u{unit_num}",
                f"u-{unit_num}"
            ]
            
            if any(pattern in filename_lower for pattern in patterns):
                logger.info(f"Matched PDF '{pdf_filename}' to Unit {unit_num}")
                return unit_num
        
        logger.warning(f"Could not determine unit for PDF: {pdf_filename}")
        return None
    
    def get_course_info(self) -> Dict[str, Any]:
        """Get course metadata"""
        return {
            'name': self.syllabus_data.get('course_name', ''),
            'code': self.syllabus_data.get('course_code', ''),
            'semester': self.syllabus_data.get('semester', ''),
            'category': self.syllabus_data.get('category', '')
        }
    
    def get_co_mapping(self, unit_number: int) -> List[str]:
        """Get CO mapping for a unit"""
        unit = self.get_unit_by_number(unit_number)
        return unit.get('co_mapping', []) if unit else []
    
    def get_bloom_levels(self, unit_number: int) -> List[str]:
        """Get Bloom levels for a unit"""
        unit = self.get_unit_by_number(unit_number)
        return unit.get('bloom_levels', []) if unit else []

# Singleton instance
_syllabus_loader = None

def get_syllabus_loader() -> SyllabusLoader:
    """Get singleton syllabus loader instance"""
    global _syllabus_loader
    if _syllabus_loader is None:
        _syllabus_loader = SyllabusLoader()
    return _syllabus_loader
