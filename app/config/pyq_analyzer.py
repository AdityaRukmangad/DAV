"""
Previous Year Question Pattern Analyzer
Analyzes historical question papers to learn patterns for CO, marks, difficulty, and question types
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
from app.tools.utils import get_logger

logger = get_logger("PYQAnalyzer")

class PreviousYearQuestionAnalyzer:
    def __init__(self, pyq_directory: Optional[str] = None):
        if pyq_directory is None:
            pyq_directory = str(Path(__file__).parent.parent.parent / "data" / "previous_year_papers")
        
        self.pyq_directory = Path(pyq_directory)
        self.patterns = self._analyze_all_papers()
        
    def _analyze_all_papers(self) -> Dict[str, Any]:
        """Analyze all previous year papers and extract patterns"""
        patterns = {
            'by_marks': defaultdict(lambda: {'types': defaultdict(int), 'difficulty': defaultdict(int), 'avg_length': []}),
            'by_co': defaultdict(lambda: {'marks_distribution': defaultdict(int), 'question_types': defaultdict(int)}),
            'by_topic': defaultdict(lambda: {'typical_marks': [], 'typical_type': defaultdict(int)}),
            'by_difficulty': defaultdict(lambda: {'marks': defaultdict(int), 'types': defaultdict(int), 'avg_sentences': []}),
            'total_papers': 0,
            'total_questions': 0
        }
        
        if not self.pyq_directory.exists():
            logger.warning(f"PYQ directory not found: {self.pyq_directory}")
            return patterns
        
        # Load all JSON files
        json_files = list(self.pyq_directory.glob("*.json"))
        
        if not json_files:
            logger.warning("No previous year question papers found")
            return patterns
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    paper = json.load(f)
                    patterns['total_papers'] += 1
                    
                    for q in paper.get('questions', []):
                        patterns['total_questions'] += 1
                        marks = q.get('marks', 0)
                        q_type = q.get('question_type', 'short')
                        difficulty = q.get('difficulty', 'Medium')
                        topic = q.get('topic', '')
                        co_list = q.get('co_mapping', [])
                        answer_length = q.get('expected_answer_length', '')
                        
                        # Pattern by marks
                        patterns['by_marks'][marks]['types'][q_type] += 1
                        patterns['by_marks'][marks]['difficulty'][difficulty] += 1
                        if answer_length:
                            patterns['by_marks'][marks]['avg_length'].append(answer_length)
                        
                        # Pattern by CO
                        for co in co_list:
                            patterns['by_co'][co]['marks_distribution'][marks] += 1
                            patterns['by_co'][co]['question_types'][q_type] += 1
                        
                        # Pattern by topic
                        if topic:
                            patterns['by_topic'][topic]['typical_marks'].append(marks)
                            patterns['by_topic'][topic]['typical_type'][q_type] += 1
                        
                        # Pattern by difficulty
                        patterns['by_difficulty'][difficulty]['marks'][marks] += 1
                        patterns['by_difficulty'][difficulty]['types'][q_type] += 1
                        
                        # Extract sentence count from answer_length like "2-3 sentences"
                        if 'sentence' in answer_length.lower():
                            try:
                                nums = [int(s) for s in answer_length.split() if s.isdigit()]
                                if nums:
                                    patterns['by_difficulty'][difficulty]['avg_sentences'].append(sum(nums) / len(nums))
                            except:
                                pass
                
                logger.info(f"Loaded paper: {json_file.name}")
                        
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")
        
        logger.info(f"Analyzed {patterns['total_papers']} papers with {patterns['total_questions']} questions")
        return patterns
    
    def get_typical_difficulty_for_marks(self, marks: int, question_type: str) -> str:
        """Get most common difficulty level for given marks and type"""
        if marks not in self.patterns['by_marks']:
            # Default fallback
            if marks <= 2:
                return 'Easy'
            elif marks <= 5:
                return 'Medium'
            else:
                return 'Hard'
        
        difficulty_counts = self.patterns['by_marks'][marks]['difficulty']
        if not difficulty_counts:
            return 'Medium'
        
        return max(difficulty_counts.items(), key=lambda x: x[1])[0]
    
    def get_typical_question_type_for_co(self, co: str) -> str:
        """Get most common question type for a CO"""
        if co not in self.patterns['by_co']:
            return 'short'
        
        type_counts = self.patterns['by_co'][co]['question_types']
        if not type_counts:
            return 'short'
        
        return max(type_counts.items(), key=lambda x: x[1])[0]
    
    def get_expected_answer_length(self, question_type: str, difficulty: str, marks: int) -> str:
        """Get expected answer length based on historical patterns"""
        # Check if we have data for this difficulty
        if difficulty in self.patterns['by_difficulty']:
            avg_sentences = self.patterns['by_difficulty'][difficulty]['avg_sentences']
            if avg_sentences:
                avg = sum(avg_sentences) / len(avg_sentences)
                return f"{int(avg)}-{int(avg)+1} sentences"
        
        # Fallback to guidelines
        if question_type == 'short':
            if difficulty == 'Easy':
                return "2-3 sentences"
            elif difficulty == 'Medium':
                return "3-4 sentences"
            else:
                return "4-5 sentences"
        elif question_type == 'long':
            if difficulty == 'Easy':
                return "5-8 sentences"
            elif difficulty == 'Medium':
                return "8-12 sentences"
            else:
                return "12-15 sentences"
        elif question_type == 'mcq':
            return "Single letter answer"
        else:  # numerical
            return f"{marks} step calculation"
    
    def get_generation_hints(self, marks: int, question_type: str, co: str, difficulty: str) -> Dict[str, Any]:
        """Get comprehensive hints for question generation based on PYQ patterns"""
        hints = {
            'expected_length': self.get_expected_answer_length(question_type, difficulty, marks),
            'typical_difficulty': self.get_typical_difficulty_for_marks(marks, question_type),
            'has_pyq_data': self.patterns['total_questions'] > 0,
            'co_typical_marks': [],
            'style_notes': []
        }
        
        # Get typical marks for this CO
        if co in self.patterns['by_co']:
            marks_dist = self.patterns['by_co'][co]['marks_distribution']
            if marks_dist:
                hints['co_typical_marks'] = sorted(marks_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Add style notes based on patterns
        if marks <= 2:
            hints['style_notes'].append("Keep question very concise and focused on single concept")
            hints['style_notes'].append("Answer should be definitive, not require elaboration")
        elif marks <= 5:
            hints['style_notes'].append("Question can have brief comparison or explanation")
            hints['style_notes'].append("Answer should include reasoning but remain concise")
        else:
            hints['style_notes'].append("Multi-part question acceptable")
            hints['style_notes'].append("Detailed comprehensive answer expected")
        
        return hints

# Singleton instance
_pyq_analyzer = None

def get_pyq_analyzer() -> PreviousYearQuestionAnalyzer:
    """Get singleton PYQ analyzer instance"""
    global _pyq_analyzer
    if _pyq_analyzer is None:
        _pyq_analyzer = PreviousYearQuestionAnalyzer()
    return _pyq_analyzer
