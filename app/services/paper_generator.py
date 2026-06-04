"""
Module: app/services/paper_generator.py
Purpose: Question Paper Generator with customizable templates.
Features:
- Custom templates with topic selection
- Marks allocation (total and part-wise)
- Multiple question types
- Generate unique questions per topic
"""

import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import hashlib

from app.services.graph_agent import run_agent
from app.tools.utils import get_logger

logger = get_logger("PaperGenerator")

# Storage paths
TEMPLATES_DIR = Path("data/paper_templates")
PAPERS_DIR = Path("data/generated_papers")
try:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    pass  # Directories already exist


@dataclass
class QuestionPart:
    """A single part of a question (e.g., Part a, Part b)"""
    part_label: str  # "a", "b", "c"
    description: str  # What this part asks
    marks: int


# Bloom's Taxonomy levels with descriptions for question generation
BLOOMS_TAXONOMY = {
    "remember": {
        "level": 1,
        "verbs": ["define", "list", "recall", "identify", "name", "state"],
        "description": "Recall facts, terms, basic concepts, or answers",
        "prompt": "Create a question that tests RECALL of facts or definitions. Students should retrieve information from memory."
    },
    "understand": {
        "level": 2,
        "verbs": ["explain", "describe", "summarize", "interpret", "classify"],
        "description": "Demonstrate understanding of facts and ideas",
        "prompt": "Create a question that tests UNDERSTANDING. Students should explain ideas or concepts in their own words."
    },
    "apply": {
        "level": 3,
        "verbs": ["apply", "solve", "use", "demonstrate", "calculate", "compute"],
        "description": "Apply knowledge to new situations",
        "prompt": "Create a question that requires APPLYING knowledge. Students should use learned concepts to solve new problems."
    },
    "analyze": {
        "level": 4,
        "verbs": ["analyze", "compare", "contrast", "differentiate", "examine"],
        "description": "Break information into parts to explore relationships",
        "prompt": "Create a question that requires ANALYSIS. Students should break down information, identify patterns, or compare components."
    },
    "evaluate": {
        "level": 5,
        "verbs": ["evaluate", "justify", "critique", "judge", "assess", "argue"],
        "description": "Justify a decision or course of action",
        "prompt": "Create a question that requires EVALUATION. Students should make judgments, justify decisions, or critique approaches."
    },
    "create": {
        "level": 6,
        "verbs": ["create", "design", "construct", "develop", "propose", "formulate"],
        "description": "Create new work or propose solutions",
        "prompt": "Create a question that requires CREATION. Students should design, develop, or propose novel solutions."
    }
}


@dataclass
class QuestionSpec:
    """Specification for a question to generate"""
    topic: str  # e.g., "DFS algorithm"
    question_type: str  # "trace", "pseudo-code", "calculation", "theory", "mcq"
    total_marks: int
    difficulty: str  # "Easy", "Medium", "Hard"
    parts: List[QuestionPart] = field(default_factory=list)
    count: int = 1  # How many unique questions to generate for this spec
    keywords: List[str] = field(default_factory=list)  # Additional keywords like "pseudo-code"
    bloom_level: str = ""  # Bloom's taxonomy level: remember, understand, apply, analyze, evaluate, create

    def get_prompt(self) -> str:
        """Build the generation prompt from spec"""
        prompt_parts = [self.topic]

        # Add Bloom's taxonomy instruction if specified
        if self.bloom_level and self.bloom_level.lower() in BLOOMS_TAXONOMY:
            bloom = BLOOMS_TAXONOMY[self.bloom_level.lower()]
            prompt_parts.append(f"[Cognitive Level: {self.bloom_level.upper()} - {bloom['prompt']}]")

        # Add question type context
        type_prompts = {
            "trace": "trace through the algorithm step by step",
            "pseudo-code": "based on the pseudo-code algorithm",
            "calculation": "calculation problem with numerical answer",
            "theory": "theoretical concepts and definitions",
            "mcq": "multiple choice question",
            "comparison": "compare and contrast",
        }
        if self.question_type in type_prompts:
            prompt_parts.append(type_prompts[self.question_type])

        # Add keywords
        prompt_parts.extend(self.keywords)

        return " ".join(prompt_parts)


@dataclass
class PaperSection:
    """A section of the paper (e.g., Section A - Short Answer)"""
    name: str  # "Section A"
    title: str  # "Short Answer Questions"
    instructions: str  # "Answer ALL questions"
    questions: List[QuestionSpec] = field(default_factory=list)

    @property
    def total_marks(self) -> int:
        return sum(q.total_marks * q.count for q in self.questions)


@dataclass
class PaperTemplate:
    """Template for generating a question paper"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Untitled Paper"
    subject: str = ""
    duration_minutes: int = 180
    total_marks: int = 100
    instructions: List[str] = field(default_factory=list)
    sections: List[PaperSection] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'PaperTemplate':
        sections = []
        for s in data.get('sections', []):
            questions = []
            for q in s.get('questions', []):
                parts = [QuestionPart(**p) for p in q.get('parts', [])]
                q_copy = {k: v for k, v in q.items() if k != 'parts'}
                questions.append(QuestionSpec(**q_copy, parts=parts))
            s_copy = {k: v for k, v in s.items() if k != 'questions'}
            sections.append(PaperSection(**s_copy, questions=questions))

        data_copy = {k: v for k, v in data.items() if k != 'sections'}
        return cls(**data_copy, sections=sections)


@dataclass
class GeneratedQuestion:
    """A generated question with all details"""
    question_number: int
    part_of_section: str
    topic: str
    question_type: str
    difficulty: str
    marks: int
    parts_marks: List[Dict]  # [{"part": "a", "marks": 2}, ...]
    question_text: str
    answer: str
    explanation: str
    verification_code: Optional[str] = None


@dataclass
class GeneratedPaper:
    """A fully generated question paper"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    template_id: str = ""
    template_name: str = ""
    subject: str = ""
    duration_minutes: int = 180
    total_marks: int = 100
    instructions: List[str] = field(default_factory=list)
    sections: List[Dict] = field(default_factory=list)  # Contains section info + questions
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_stats: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class PaperGeneratorService:
    """Service for generating question papers from templates"""

    def __init__(self):
        self.templates_file = TEMPLATES_DIR / "templates.json"
        self._ensure_templates_file()

    def _ensure_templates_file(self):
        if not self.templates_file.exists():
            self.templates_file.write_text("[]")

    # ========== TEMPLATE MANAGEMENT ==========

    def save_template(self, template: PaperTemplate) -> str:
        """Save a template and return its ID"""
        templates = self._load_templates()

        # Update existing or add new
        existing_idx = next((i for i, t in enumerate(templates) if t['id'] == template.id), None)
        if existing_idx is not None:
            templates[existing_idx] = template.to_dict()
        else:
            templates.append(template.to_dict())

        self.templates_file.write_text(json.dumps(templates, indent=2))
        logger.info(f"Saved template: {template.name} (ID: {template.id})")
        return template.id

    def get_template(self, template_id: str) -> Optional[PaperTemplate]:
        """Get a template by ID"""
        templates = self._load_templates()
        for t in templates:
            if t['id'] == template_id:
                return PaperTemplate.from_dict(t)
        return None

    def list_templates(self) -> List[Dict]:
        """List all templates (summary only)"""
        templates = self._load_templates()
        return [{
            'id': t['id'],
            'name': t['name'],
            'subject': t.get('subject', ''),
            'total_marks': t.get('total_marks', 0),
            'sections_count': len(t.get('sections', [])),
            'created_at': t.get('created_at', '')
        } for t in templates]

    def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        templates = self._load_templates()
        new_templates = [t for t in templates if t['id'] != template_id]
        if len(new_templates) < len(templates):
            self.templates_file.write_text(json.dumps(new_templates, indent=2))
            return True
        return False

    def _load_templates(self) -> List[Dict]:
        try:
            return json.loads(self.templates_file.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    # ========== PAPER GENERATION ==========

    def generate_paper(self, template_id: str, parallel: bool = True) -> GeneratedPaper:
        """Generate a full question paper from a template with enhanced deduplication"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        logger.info(f"Generating paper from template: {template.name}")

        paper = GeneratedPaper(
            template_id=template.id,
            template_name=template.name,
            subject=template.subject,
            duration_minutes=template.duration_minutes,
            total_marks=template.total_marks,
            instructions=template.instructions
        )

        # Enhanced tracking for duplicate prevention
        question_hash_set = set()  # Store hash of question content to detect duplicates
        used_cache_ids = set()  # Track which cached questions have been used
        hash_lock = threading.Lock()  # Thread-safe operations on sets
        dedup_stats = {'duplicates_detected': 0, 'retries_performed': 0, 'cache_reuse_prevented': 0}

        # Collect ALL question tasks across ALL sections first
        all_tasks = []  # (section_idx, question_number, spec, section_name)
        for section_idx, section in enumerate(template.sections):
            question_number = 1
            for spec in section.questions:
                for i in range(spec.count):
                    all_tasks.append((section_idx, question_number + i, spec, section.name))
                question_number += spec.count

        total_questions = len(all_tasks)
        logger.info(f"Generating {total_questions} questions in parallel with enhanced deduplication...")

        # Generate ALL questions in parallel
        results = {}  # (section_idx, question_number) -> GeneratedQuestion

        if parallel and total_questions > 1:
            # Use 5 parallel workers for faster generation with GPT-4o
            with ThreadPoolExecutor(max_workers=min(5, total_questions)) as executor:
                futures = {
                    executor.submit(
                        self._generate_single_question_with_dedup,
                        task[1],  # question_number
                        task[2].get_prompt(),  # prompt
                        task[2],  # spec
                        task[3],  # section_name
                        question_hash_set,  # pass the dedup set
                        used_cache_ids,  # pass used cache tracking
                        hash_lock,  # pass thread lock
                        dedup_stats  # pass stats dict
                    ): (task[0], task[1], task[2], task[3])  # (section_idx, q_num, spec, section_name)
                    for task in all_tasks
                }

                for future in as_completed(futures):
                    section_idx, q_num, spec, section_name = futures[future]
                    try:
                        q = future.result()
                        results[(section_idx, q_num)] = q
                    except Exception as e:
                        logger.error(f"Question {q_num} generation failed: {e}")
                        results[(section_idx, q_num)] = self._create_failed_question(
                            q_num, spec, section_name, str(e)
                        )
        else:
            # Sequential fallback
            for task in all_tasks:
                section_idx, q_num, spec, section_name = task
                try:
                    q = self._generate_single_question_with_dedup(
                        q_num, spec.get_prompt(), spec, section_name,
                        question_hash_set, used_cache_ids, hash_lock, dedup_stats
                    )
                    results[(section_idx, q_num)] = q
                except Exception as e:
                    logger.error(f"Question {q_num} generation failed: {e}")
                    results[(section_idx, q_num)] = self._create_failed_question(q_num, spec, section_name, str(e))

        # Organize results back into sections
        successful = 0
        failed = 0

        for section_idx, section in enumerate(template.sections):
            section_data = {
                'name': section.name,
                'title': section.title,
                'instructions': section.instructions,
                'questions': []
            }

            # Get questions for this section, sorted by question number
            section_questions = [
                (q_num, results[(s_idx, q_num)])
                for (s_idx, q_num), q in results.items()
                if s_idx == section_idx
            ]
            section_questions.sort(key=lambda x: x[0])

            for _, q in section_questions:
                section_data['questions'].append(asdict(q))
                if q.question_text and not q.question_text.startswith('[GENERATION FAILED'):
                    successful += 1
                else:
                    failed += 1

            paper.sections.append(section_data)

        # Calculate actual total marks from generated questions
        actual_total_marks = 0
        for section in paper.sections:
            for q in section.get('questions', []):
                actual_total_marks += q.get('marks', 0)
        paper.total_marks = actual_total_marks

        paper.generation_stats = {
            'total_questions': total_questions,
            'successful': successful,
            'failed': failed,
            'duplicates_detected': dedup_stats['duplicates_detected'],
            'retries_performed': dedup_stats['retries_performed'],
            'cache_reuse_prevented': dedup_stats['cache_reuse_prevented']
        }

        # Save the generated paper
        self._save_paper(paper)

        logger.info(f"Paper generated: {successful}/{total_questions} questions successful")
        logger.info(f"Deduplication stats: {dedup_stats['duplicates_detected']} duplicates detected, "
                   f"{dedup_stats['retries_performed']} retries performed, "
                   f"{dedup_stats['cache_reuse_prevented']} cache reuses prevented")
        return paper

    def _generate_questions_for_spec(
        self,
        spec: QuestionSpec,
        section_name: str,
        start_number: int,
        parallel: bool = True
    ) -> List[GeneratedQuestion]:
        """Generate multiple unique questions for a single spec using parallel instances"""
        questions = []

        # Build base prompt - keep it simple, let model variation handle uniqueness
        base_prompt = spec.get_prompt()

        # Generate 'count' questions - same prompt, parallel execution gives natural variety
        generation_tasks = [(start_number + i, base_prompt, spec) for i in range(spec.count)]

        if parallel and len(generation_tasks) > 1:
            # Generate in parallel
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._generate_single_question, num, prompt, spec, section_name): num
                    for num, prompt, spec in generation_tasks
                }
                for future in as_completed(futures):
                    try:
                        q = future.result()
                        questions.append(q)
                    except Exception as e:
                        logger.error(f"Question generation failed: {e}")
                        num = futures[future]
                        questions.append(self._create_failed_question(num, spec, section_name, str(e)))
        else:
            # Generate sequentially
            for num, prompt, spec in generation_tasks:
                try:
                    q = self._generate_single_question(num, prompt, spec, section_name)
                    questions.append(q)
                except Exception as e:
                    logger.error(f"Question generation failed: {e}")
                    questions.append(self._create_failed_question(num, spec, section_name, str(e)))

        return sorted(questions, key=lambda x: x.question_number)

    def _generate_single_question(
        self,
        question_number: int,
        prompt: str,
        spec: QuestionSpec,
        section_name: str
    ) -> GeneratedQuestion:
        """Generate a single question using the graph agent"""
        logger.info(f"Generating Q{question_number}: {prompt[:50]}...")

        # Call the existing graph agent
        result = run_agent(prompt, spec.difficulty)

        if not result or 'error' in result:
            raise Exception(result.get('error', 'Unknown generation error'))

        # Build parts marks
        parts_marks = []
        if spec.parts:
            for p in spec.parts:
                parts_marks.append({"part": p.part_label, "marks": p.marks, "description": p.description})
        else:
            # No explicit parts - single question
            parts_marks = [{"part": "", "marks": spec.total_marks, "description": ""}]

        # Format question text with marks
        question_text = result.get('question', '')
        if spec.parts and len(spec.parts) > 1:
            # Multi-part question - add marks to each part if not already there
            question_text = self._format_multipart_question(question_text, spec.parts)

        return GeneratedQuestion(
            question_number=question_number,
            part_of_section=section_name,
            topic=spec.topic,
            question_type=spec.question_type,
            difficulty=spec.difficulty,
            marks=spec.total_marks,
            parts_marks=parts_marks,
            question_text=question_text,
            answer=result.get('answer', ''),
            explanation=result.get('explanation', ''),
            verification_code=result.get('verification_code')
        )

    def _compute_question_hash(self, question_text: str, answer: str, topic: str) -> str:
        """
        Compute a robust hash for a question to detect duplicates.
        Uses full question text + answer + topic for better uniqueness.
        """
        # Normalize text: lowercase, strip, remove extra whitespace
        def normalize(text: str) -> str:
            return ' '.join(text.lower().strip().split())

        # Use full question text (not just first 100 chars) + answer for better detection
        normalized_q = normalize(question_text)
        normalized_a = normalize(answer)
        normalized_topic = normalize(topic)

        # Create composite key with all components
        composite_key = f"{normalized_topic}|{normalized_q}|{normalized_a}"

        # Use SHA256 for better collision resistance than MD5
        return hashlib.sha256(composite_key.encode('utf-8')).hexdigest()

    def _generate_single_question_with_dedup(
        self,
        question_number: int,
        prompt: str,
        spec: QuestionSpec,
        section_name: str,
        question_hash_set: Set[str],
        used_cache_ids: Set[str],
        hash_lock: threading.Lock,
        dedup_stats: Dict,
        max_retries: int = 5
    ) -> GeneratedQuestion:
        """
        Generate a single question with enhanced deduplication.

        Features:
        - Thread-safe set operations with locking
        - Robust hash using full question + answer text
        - Cache tracking to prevent reusing same cached question
        - Progressive retry strategy with varied prompts and temperature
        - Detailed logging and statistics
        """
        logger.info(f"Generating Q{question_number}: {prompt[:50]}... (with enhanced dedup)")

        # Variation prompts for retries to encourage diversity
        variation_prompts = [
            "",  # First attempt - no modification
            "\n[IMPORTANT: Generate a COMPLETELY DIFFERENT question. Use different examples, scenarios, or perspectives.]",
            "\n[CRITICAL: This is retry #{attempt}. Generate a UNIQUE question with different focus. Consider: different application, different dataset, different approach, or different angle on the same topic.]",
            "\n[URGENT: Previous attempts generated duplicates. Create a FRESH question with novel aspects. Change the problem setup, context, or ask about a different sub-concept within this topic.]",
            "\n[FINAL ATTEMPT: Generate a maximally different question. Use alternative terminology, different difficulty emphasis, or focus on a complementary aspect of the topic.]"
        ]

        best_attempt = None  # Track best attempt in case all retries fail

        for attempt in range(max_retries):
            try:
                # Progressive variation: add retry prompt and adjust parameters
                current_prompt = prompt
                if attempt > 0:
                    variation_text = variation_prompts[min(attempt, len(variation_prompts) - 1)]
                    current_prompt = f"{prompt}{variation_text.format(attempt=attempt)}"

                # Pass used_cache_ids to agent to prevent cache reuse
                result = run_agent(
                    current_prompt,
                    spec.difficulty,
                    used_cache_ids=used_cache_ids,  # Pass to agent to prevent cache reuse
                    temperature_boost=0.1 * attempt  # Increase temperature on retries (0.0, 0.1, 0.2, ...)
                )

                if not result or 'error' in result:
                    raise Exception(result.get('error', 'Unknown generation error'))

                question_text = result.get('question', '')
                answer_text = result.get('answer', '')

                # Update used_cache_ids from agent result (deduplication tracking)
                returned_cache_ids = result.get('used_cache_ids', [])
                if returned_cache_ids:
                    for cache_id in returned_cache_ids:
                        used_cache_ids.add(cache_id)
                    logger.info(f"Updated used_cache_ids with {len(returned_cache_ids)} IDs from agent result")

                # Compute robust hash
                question_hash = self._compute_question_hash(question_text, answer_text, spec.topic)

                # Check for cache reuse (if this came from cache, track it)
                from_cache = result.get('from_cache', False)
                cache_id = result.get('cache_id')  # Agent should provide cache ID if from cache

                # Thread-safe duplicate check
                with hash_lock:
                    is_duplicate = question_hash in question_hash_set
                    cache_already_used = cache_id and cache_id in used_cache_ids

                    if is_duplicate or cache_already_used:
                        dedup_stats['duplicates_detected'] += 1
                        if cache_already_used:
                            dedup_stats['cache_reuse_prevented'] += 1
                            logger.warning(f"Q{question_number}: Cached question #{cache_id} already used in this paper (attempt {attempt + 1}/{max_retries})")
                        else:
                            logger.warning(f"Q{question_number}: Duplicate question detected (attempt {attempt + 1}/{max_retries})")

                        if attempt < max_retries - 1:
                            # Track retry
                            dedup_stats['retries_performed'] += 1
                            # Store this as best attempt in case we run out of retries
                            if not best_attempt:
                                best_attempt = (result, question_hash, cache_id)
                            continue  # Retry
                        else:
                            # Last attempt failed - use best attempt with warning
                            logger.error(f"Q{question_number}: All {max_retries} attempts produced duplicates. Using last attempt with duplicate flag.")
                            # Don't add to sets - let it be marked as potential duplicate
                            if best_attempt:
                                result, question_hash, cache_id = best_attempt
                                question_text = result.get('question', '')
                                answer_text = result.get('answer', '')

                    # Not a duplicate - accept this question
                    question_hash_set.add(question_hash)
                    if cache_id:
                        used_cache_ids.add(cache_id)

                # Build parts marks
                parts_marks = []
                if spec.parts:
                    for p in spec.parts:
                        parts_marks.append({"part": p.part_label, "marks": p.marks, "description": p.description})
                else:
                    parts_marks = [{"part": "", "marks": spec.total_marks, "description": ""}]

                # Format question text with marks
                if spec.parts and len(spec.parts) > 1:
                    question_text = self._format_multipart_question(question_text, spec.parts)

                # Log success
                if attempt == 0:
                    logger.info(f"Q{question_number} generated successfully on first attempt (unique)")
                else:
                    logger.info(f"Q{question_number} generated successfully after {attempt + 1} attempts (unique)")

                return GeneratedQuestion(
                    question_number=question_number,
                    part_of_section=section_name,
                    topic=spec.topic,
                    question_type=spec.question_type,
                    difficulty=spec.difficulty,
                    marks=spec.total_marks,
                    parts_marks=parts_marks,
                    question_text=question_text,
                    answer=answer_text,
                    explanation=result.get('explanation', ''),
                    verification_code=result.get('verification_code')
                )

            except Exception as e:
                logger.error(f"Q{question_number} attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise  # Re-raise on last attempt

        # Should not reach here, but if it does, raise an error
        raise Exception(f"Q{question_number} could not be generated after {max_retries} attempts")

    def _format_multipart_question(self, question_text: str, parts: List[QuestionPart]) -> str:
        """Add marks allocation to multi-part questions"""
        # Check if question already has part markers
        has_parts = any(f"({p.part_label})" in question_text.lower() or
                       f"part {p.part_label}" in question_text.lower()
                       for p in parts)

        if has_parts:
            # Just add marks annotations
            for p in parts:
                patterns = [f"({p.part_label})", f"Part {p.part_label}", f"part {p.part_label}"]
                for pattern in patterns:
                    if pattern in question_text:
                        question_text = question_text.replace(
                            pattern,
                            f"{pattern} [{p.marks} marks]"
                        )
                        break
        return question_text

    def _create_failed_question(
        self,
        question_number: int,
        spec: QuestionSpec,
        section_name: str,
        error: str
    ) -> GeneratedQuestion:
        """Create a placeholder for a failed question"""
        return GeneratedQuestion(
            question_number=question_number,
            part_of_section=section_name,
            topic=spec.topic,
            question_type=spec.question_type,
            difficulty=spec.difficulty,
            marks=spec.total_marks,
            parts_marks=[{"part": "", "marks": spec.total_marks}],
            question_text=f"[GENERATION FAILED: {error}]",
            answer="",
            explanation=""
        )

    def _save_paper(self, paper: GeneratedPaper):
        """Save a generated paper"""
        paper_file = PAPERS_DIR / f"paper_{paper.id}.json"
        paper_file.write_text(json.dumps(paper.to_dict(), indent=2))
        logger.info(f"Paper saved: {paper_file}")

    def get_paper(self, paper_id: str) -> Optional[Dict]:
        """Get a generated paper by ID"""
        paper_file = PAPERS_DIR / f"paper_{paper_id}.json"
        if paper_file.exists():
            return json.loads(paper_file.read_text())
        return None

    def list_papers(self) -> List[Dict]:
        """List all generated papers with full data for frontend display"""
        papers = []
        for f in PAPERS_DIR.glob("paper_*.json"):
            try:
                data = json.loads(f.read_text())
                # Return full paper data with field name mapping for frontend
                papers.append({
                    'paper_id': data['id'],  # Frontend expects paper_id
                    'title': data.get('template_name', 'Untitled Paper'),  # Frontend expects title
                    'subject': data.get('subject', ''),
                    'duration_minutes': data.get('duration_minutes', 180),
                    'total_marks': data.get('total_marks', 0),
                    'instructions': data.get('instructions', []),
                    'sections': data.get('sections', []),  # Include sections for question count
                    'generated_at': data.get('generated_at', ''),
                    'stats': data.get('generation_stats', {})
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sorted(papers, key=lambda x: x.get('generated_at', ''), reverse=True)

    # ========== PAPER EXPORT ==========

    def export_paper_markdown(self, paper_id: str) -> str:
        """Export a paper as formatted markdown"""
        paper = self.get_paper(paper_id)
        if not paper:
            return ""

        lines = []
        lines.append(f"# {paper.get('subject', 'Question Paper')}")
        lines.append(f"**Duration:** {paper.get('duration_minutes', 180)} minutes")
        lines.append(f"**Total Marks:** {paper.get('total_marks', 100)}")
        lines.append("")

        # Instructions
        if paper.get('instructions'):
            lines.append("## Instructions")
            for inst in paper['instructions']:
                lines.append(f"- {inst}")
            lines.append("")

        # Sections
        for section in paper.get('sections', []):
            lines.append(f"## {section['name']}: {section['title']}")
            if section.get('instructions'):
                lines.append(f"*{section['instructions']}*")
            lines.append("")

            for q in section.get('questions', []):
                marks_str = f"[{q['marks']} marks]"
                lines.append(f"**Q{q['question_number']}.** {marks_str}")
                lines.append("")
                lines.append(q['question_text'])
                lines.append("")

        return "\n".join(lines)

    def export_paper_with_answers(self, paper_id: str) -> str:
        """Export paper with answer key"""
        paper = self.get_paper(paper_id)
        if not paper:
            return ""

        lines = []
        lines.append(f"# {paper.get('subject', 'Question Paper')} - ANSWER KEY")
        lines.append("")

        for section in paper.get('sections', []):
            lines.append(f"## {section['name']}")
            lines.append("")

            for q in section.get('questions', []):
                lines.append(f"**Q{q['question_number']}. [{q['marks']} marks]**")
                lines.append(f"Topic: {q['topic']} | Type: {q['question_type']} | Difficulty: {q['difficulty']}")
                lines.append("")
                lines.append("**Question:**")
                lines.append(q['question_text'])
                lines.append("")
                lines.append("**Answer:**")
                lines.append(q['answer'])
                lines.append("")
                if q.get('explanation'):
                    lines.append("**Explanation:**")
                    lines.append(q['explanation'])
                    lines.append("")
                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def _load_pdf_template_config(self) -> Dict:
        """Load PDF template configuration from YAML file"""
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "pdf_template.yaml"
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load PDF template config: {e}")
        return {}

    def export_paper_pdf(self, paper_id: str, with_answers: bool = False,
                         course_code: str = "", semester: str = "",
                         academic_year: str = "", ug_pg: str = "",
                         faculty: str = "", department: str = "",
                         logo_path: str = None) -> Optional[bytes]:
        """
        Export paper as professional academic PDF format.

        Args:
            paper_id: The paper ID to export
            with_answers: Include answers (for answer key/scheme)
            course_code: Course code (e.g., "IS353IA")
            semester: Semester number (e.g., "V")
            academic_year: Academic year (e.g., "2024-2025")
            ug_pg: UG or PG
            faculty: Faculty names
            department: Department name
            logo_path: Optional path to institution logo
        """
        try:
            from fpdf import FPDF
            from fpdf.enums import XPos, YPos
        except ImportError:
            logger.error("fpdf2 not installed. Install with: pip install fpdf2")
            return None

        paper = self.get_paper(paper_id)
        if not paper:
            logger.error(f"Paper {paper_id} not found for PDF export")
            return None

        # Load template config for defaults
        config = self._load_pdf_template_config()
        defaults = config.get('defaults', {})
        institution = config.get('institution', {})
        colors = config.get('colors', {})
        labels = config.get('labels', {})

        # Apply defaults from config if not provided
        if not semester:
            semester = defaults.get('semester', 'V')
        if not academic_year:
            academic_year = defaults.get('academic_year', '2024-2025')
        if not ug_pg:
            ug_pg = defaults.get('ug_pg', 'UG')
        if not faculty:
            faculty = defaults.get('faculty', 'Course Faculty')
        if not department:
            department = institution.get('department', 'DEPARTMENT OF INFORMATION SCIENCE AND ENGINEERING')

        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            page_width = pdf.w - pdf.l_margin - pdf.r_margin
            left_margin = pdf.l_margin

            # ============ LOGO PLACEHOLDER AREA ============
            # Leave 25mm at top for logo
            pdf.set_y(10)
            logo_text = institution.get('logo_placeholder', '[Institution Logo]')
            pdf.set_font("Helvetica", "I", 8)
            placeholder_color = colors.get('placeholder', [150, 150, 150])
            pdf.set_text_color(*placeholder_color)
            pdf.cell(0, 5, logo_text, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(15)  # Space for logo

            # ============ ACADEMIC YEAR HEADER ============
            pdf.set_font("Helvetica", "B", 11)
            odd_even = "Odd Sem" if semester in ["I", "III", "V", "VII"] else "Even Sem"
            pdf.cell(0, 6, f"Academic year {academic_year} ({odd_even})", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
            pdf.ln(3)

            # ============ DEPARTMENT HEADER ============
            pdf.set_font("Helvetica", "B", 12)
            dept_color = colors.get('department', [0, 0, 139])
            pdf.set_text_color(*dept_color)
            pdf.cell(0, 7, self._safe_text(department), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)

            # ============ COURSE INFO TABLE ============
            # Auto-generate course code from subject if not provided
            if not course_code:
                course_code = paper.get('subject', 'SUBJ')[:6].upper().replace(' ', '')

            total_marks = paper.get('total_marks', 100)
            duration = paper.get('duration_minutes', 180)

            # Table dimensions
            col_widths = [35, 45, 40, 70]  # Course Code, Value, Max Marks label, Value
            row_height = 7

            # Draw course info table
            pdf.set_font("Helvetica", "B", 10)
            table_x = left_margin + (page_width - sum(col_widths)) / 2  # Center the table

            # Row 1: Course Code | [value] | Maximum Marks | [value]
            pdf.set_x(table_x)
            pdf.cell(col_widths[0], row_height, "Course Code", border=1, align="C")
            pdf.cell(col_widths[1], row_height, course_code, border=1, align="C")
            pdf.cell(col_widths[2], row_height, "Maximum Marks", border=1, align="C")
            pdf.cell(col_widths[3], row_height, f"{total_marks}", border=1, align="C")
            pdf.ln(row_height)

            # Row 2: Sem | [value] | Duration | [value]
            pdf.set_x(table_x)
            pdf.cell(col_widths[0], row_height, "Sem", border=1, align="C")
            pdf.cell(col_widths[1], row_height, semester, border=1, align="C")
            pdf.cell(col_widths[2], row_height, "Duration", border=1, align="C")
            pdf.cell(col_widths[3], row_height, f"{duration} min", border=1, align="C")
            pdf.ln(row_height)

            # Row 3: UG/PG | [value] | Faculty | [value]
            pdf.set_x(table_x)
            pdf.cell(col_widths[0], row_height, "UG/PG", border=1, align="C")
            pdf.cell(col_widths[1], row_height, ug_pg, border=1, align="C")
            pdf.cell(col_widths[2], row_height, "Faculty", border=1, align="C")
            faculty_text = faculty if faculty else "Course Faculty"
            pdf.cell(col_widths[3], row_height, self._safe_text(faculty_text[:25]), border=1, align="C")
            pdf.ln(row_height + 5)

            # ============ SUBJECT TITLE ============
            pdf.set_font("Helvetica", "B", 14)
            subject_color = colors.get('subject_title', [180, 0, 0])
            pdf.set_text_color(*subject_color)
            subject = paper.get('subject', 'Question Paper').upper()
            pdf.cell(0, 8, self._safe_text(subject), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

            # ============ SCHEME/SOLUTION HEADER (if with answers) ============
            if with_answers:
                pdf.set_font("Helvetica", "B", 12)
                label = labels.get('scheme_solution', 'SCHEME AND SOLUTION')
                pdf.cell(0, 7, label, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                pdf.set_font("Helvetica", "B", 12)
                label = labels.get('question_paper', 'QUESTION PAPER')
                pdf.cell(0, 7, label, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(5)

            # ============ INSTRUCTIONS ============
            if paper.get('instructions') and not with_answers:
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(0, 6, "Instructions:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font("Helvetica", "", 9)
                for idx, inst in enumerate(paper['instructions'], 1):
                    pdf.set_x(left_margin)
                    pdf.multi_cell(0, 4, self._safe_text(f"{idx}. {inst}"))
                pdf.ln(3)

            # ============ QUESTIONS IN TABLE FORMAT ============
            for section in paper.get('sections', []):
                # Section header
                pdf.set_font("Helvetica", "B", 11)
                section_name = section.get('name', 'Section')
                pdf.cell(0, 7, self._safe_text(section_name.upper()), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                if section.get('instructions'):
                    pdf.set_font("Helvetica", "I", 9)
                    pdf.cell(0, 5, self._safe_text(section['instructions']), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(3)

                # Question table header
                q_no_width = 15
                marks_width = 15
                question_width = page_width - q_no_width - marks_width

                pdf.set_font("Helvetica", "B", 10)
                pdf.set_x(left_margin)
                pdf.cell(q_no_width, 7, "Q. No.", border=1, align="C")
                if with_answers:
                    pdf.cell(question_width, 7, "QUESTION & ANSWER", border=1, align="C")
                else:
                    pdf.cell(question_width, 7, "QUESTION", border=1, align="C")
                pdf.cell(marks_width, 7, "M", border=1, align="C")
                pdf.ln(7)

                # Questions
                for q in section.get('questions', []):
                    q_num = q.get('question_number', '?')
                    q_text = q.get('question_text', '')
                    marks = q.get('marks', 0)

                    # Calculate height needed for question text
                    pdf.set_font("Helvetica", "", 10)

                    # Build full content for this cell
                    cell_content = self._safe_text(q_text)
                    if with_answers:
                        answer = q.get('answer', '')
                        if answer:
                            cell_content += f"\n\n**Answer:** {self._safe_text(answer)}"
                        explanation = q.get('explanation', '')
                        if explanation:
                            cell_content += f"\n\n**Explanation:** {self._safe_text(explanation[:300])}"

                    # Estimate row height (rough calculation)
                    lines_estimate = max(1, len(cell_content) // 80 + cell_content.count('\n') + 1)
                    row_height = max(10, lines_estimate * 5)

                    # Check if we need a new page
                    if pdf.get_y() + row_height > pdf.h - 20:
                        pdf.add_page()
                        # Repeat table header on new page
                        pdf.set_font("Helvetica", "B", 10)
                        pdf.set_x(left_margin)
                        pdf.cell(q_no_width, 7, "Q. No.", border=1, align="C")
                        pdf.cell(question_width, 7, "QUESTION" if not with_answers else "QUESTION & ANSWER", border=1, align="C")
                        pdf.cell(marks_width, 7, "M", border=1, align="C")
                        pdf.ln(7)

                    # Draw the row
                    y_before = pdf.get_y()

                    # Q.No cell
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.set_x(left_margin)
                    pdf.cell(q_no_width, row_height, str(q_num), border="LTB", align="C")

                    # Question cell (multi_cell for wrapping)
                    pdf.set_font("Helvetica", "", 9)
                    x_after_qno = pdf.get_x()
                    pdf.set_xy(x_after_qno, y_before)

                    # Use multi_cell for question text
                    pdf.multi_cell(question_width, 5, cell_content, border=0)
                    y_after_text = pdf.get_y()
                    actual_height = y_after_text - y_before

                    # Draw borders for question cell
                    pdf.rect(x_after_qno, y_before, question_width, actual_height)

                    # Marks cell
                    pdf.set_xy(x_after_qno + question_width, y_before)
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.cell(marks_width, actual_height, str(marks), border=1, align="C")

                    # Fix Q.No cell height
                    pdf.rect(left_margin, y_before, q_no_width, actual_height)

                    pdf.set_y(y_after_text)

                pdf.ln(5)

            return pdf.output()
        except Exception as e:
            logger.error(f"PDF generation failed for paper {paper_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _safe_text(self, text) -> str:
        """Convert text to ASCII-safe version for PDF"""
        if not text:
            return ""
        # Handle bytes/bytearray
        if isinstance(text, (bytes, bytearray)):
            text = text.decode('utf-8', errors='replace')
        # Ensure it's a string
        text = str(text)
        # Replace common problematic characters and math symbols
        replacements = {
            '•': '*',
            '–': '-',
            '—': '-',
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '…': '...',
            '≥': '>=',
            '≤': '<=',
            '≠': '!=',
            '≈': '~=',
            '×': 'x',
            '÷': '/',
            '∑': 'SUM',
            '∏': 'PROD',
            'σ': 'sigma',
            'μ': 'mu',
            'α': 'alpha',
            'β': 'beta',
            'γ': 'gamma',
            'δ': 'delta',
            'ε': 'epsilon',
            'θ': 'theta',
            'λ': 'lambda',
            'π': 'pi',
            'ρ': 'rho',
            'τ': 'tau',
            'φ': 'phi',
            'ω': 'omega',
            '∞': 'inf',
            '∈': 'in',
            '∉': 'not in',
            '⊂': 'subset',
            '⊆': 'subseteq',
            '∪': 'union',
            '∩': 'intersect',
            '∧': 'AND',
            '∨': 'OR',
            '¬': 'NOT',
            '→': '->',
            '←': '<-',
            '↔': '<->',
            '⇒': '=>',
            '⇐': '<=',
            '√': 'sqrt',
            '∂': 'd',
            '∇': 'nabla',
            '⌈': 'ceil(',
            '⌉': ')',
            '⌊': 'floor(',
            '⌋': ')',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.encode('latin-1', errors='replace').decode('latin-1')

    def _detect_table(self, text: str) -> list:
        """Detect markdown-style tables in text and return list of (is_table, content) tuples"""
        lines = text.split('\n')
        result = []
        current_table = []
        current_text = []

        for line in lines:
            # Check if line looks like a table row (has | separators)
            stripped = line.strip()
            if '|' in stripped and stripped.count('|') >= 2:
                # Flush any accumulated text
                if current_text:
                    result.append((False, '\n'.join(current_text)))
                    current_text = []
                current_table.append(stripped)
            else:
                # Flush any accumulated table
                if current_table:
                    result.append((True, current_table))
                    current_table = []
                current_text.append(line)

        # Flush remaining content
        if current_table:
            result.append((True, current_table))
        if current_text:
            result.append((False, '\n'.join(current_text)))

        return result

    def _render_table(self, pdf, table_lines: list, left_margin: float):
        """Render a markdown table as a PDF table"""
        from fpdf.enums import XPos, YPos

        if not table_lines:
            return

        # Parse table structure
        rows = []
        for line in table_lines:
            # Skip separator lines (|---|---|)
            if line.replace('|', '').replace('-', '').replace(':', '').strip() == '':
                continue
            # Split by | and clean cells
            cells = [c.strip() for c in line.split('|')]
            # Remove empty first/last cells from leading/trailing |
            cells = [c for c in cells if c or cells.index(c) not in [0, len(cells)-1]]
            if cells:
                rows.append(cells)

        if not rows:
            return

        # Calculate column widths
        num_cols = max(len(row) for row in rows)
        page_width = pdf.w - pdf.l_margin - pdf.r_margin
        col_width = page_width / num_cols

        # Render table
        pdf.set_font("Helvetica", "", 9)
        line_height = 5

        for row_idx, row in enumerate(rows):
            pdf.set_x(left_margin)
            # First row is header - make it bold
            if row_idx == 0:
                pdf.set_font("Helvetica", "B", 9)
            else:
                pdf.set_font("Helvetica", "", 9)

            for col_idx, cell in enumerate(row):
                # Pad row if fewer cells than expected
                if col_idx < num_cols:
                    cell_text = self._safe_text(cell) if col_idx < len(row) else ""
                    # Truncate if too long
                    if len(cell_text) > 20:
                        cell_text = cell_text[:18] + ".."
                    pdf.cell(col_width, line_height, cell_text, border=1, align="C")

            pdf.ln(line_height)

        pdf.ln(2)

    def _pdf_multi_cell_safe(self, pdf, text: str, width: int = 0, height: int = 5):
        """Safely write text to PDF, handling encoding issues and tables"""
        if not text:
            return

        from fpdf.enums import XPos, YPos
        left_margin = pdf.l_margin

        # Detect tables in text
        segments = self._detect_table(text)

        for is_table, content in segments:
            if is_table:
                # Render as table
                self._render_table(pdf, content, left_margin)
            else:
                # Render as regular text
                safe_text = self._safe_text(content)
                if safe_text.strip():
                    pdf.set_x(left_margin)
                    pdf.multi_cell(width, height, safe_text)

    def export_answer_key_only(self, paper_id: str) -> str:
        """Export ONLY the answer key (no questions) - for separate distribution"""
        paper = self.get_paper(paper_id)
        if not paper:
            return ""

        lines = []
        lines.append(f"# {paper.get('subject', 'Question Paper')} - ANSWER KEY ONLY")
        lines.append(f"Paper ID: {paper_id}")
        lines.append("")

        for section in paper.get('sections', []):
            lines.append(f"## {section['name']}")
            lines.append("")

            for q in section.get('questions', []):
                lines.append(f"**Q{q['question_number']}** [{q['marks']} marks] - {q.get('topic', 'N/A')}")
                lines.append(f"**Answer:** {q.get('answer', 'N/A')}")
                if q.get('explanation'):
                    lines.append(f"**Explanation:** {q['explanation']}")
                lines.append("")

        return "\n".join(lines)

    # ========== RUBRIC GENERATION ==========

    def generate_rubric(self, question: Dict) -> Dict:
        """Generate a marking rubric for a single question"""
        marks = question.get('marks', 5)
        question_type = question.get('question_type', 'short')
        topic = question.get('topic', '')
        answer = question.get('answer', '')
        explanation = question.get('explanation', '')

        # Build rubric based on question type and marks
        rubric = {
            "question_number": question.get('question_number', 0),
            "topic": topic,
            "total_marks": marks,
            "criteria": []
        }

        if question_type in ['numerical', 'calculation']:
            # Numerical/calculation questions - step-based rubric
            if marks >= 5:
                rubric["criteria"] = [
                    {"criterion": "Problem Setup", "marks": 1, "description": "Correctly identifies given values and what to find"},
                    {"criterion": "Formula/Method", "marks": 1, "description": "Uses correct formula or method"},
                    {"criterion": "Calculation Steps", "marks": marks - 3, "description": "Shows correct intermediate steps"},
                    {"criterion": "Final Answer", "marks": 1, "description": "Arrives at correct final answer with units"}
                ]
            else:
                rubric["criteria"] = [
                    {"criterion": "Method", "marks": max(1, marks // 2), "description": "Correct approach"},
                    {"criterion": "Answer", "marks": marks - max(1, marks // 2), "description": "Correct final answer"}
                ]

        elif question_type == 'mcq':
            rubric["criteria"] = [
                {"criterion": "Correct Option", "marks": marks, "description": "Selects the correct answer"}
            ]

        elif question_type in ['trace', 'algorithm']:
            # Trace/algorithm questions
            steps = max(2, marks - 1)
            rubric["criteria"] = [
                {"criterion": "Initial State", "marks": 1, "description": "Correctly shows initial state/setup"},
                {"criterion": "Step-by-step Trace", "marks": steps, "description": f"Correct execution of each step (partial credit for {steps} steps)"},
                {"criterion": "Final Result", "marks": max(1, marks - steps - 1), "description": "Correct final output/state"}
            ]

        elif question_type == 'theory':
            # Theory/explanation questions
            if marks >= 5:
                rubric["criteria"] = [
                    {"criterion": "Definition/Concept", "marks": 2, "description": "Clear and accurate definition or concept explanation"},
                    {"criterion": "Key Points", "marks": marks - 3, "description": "Covers all essential points/features"},
                    {"criterion": "Example/Application", "marks": 1, "description": "Provides relevant example or application"}
                ]
            else:
                rubric["criteria"] = [
                    {"criterion": "Core Concept", "marks": max(1, marks - 1), "description": "Demonstrates understanding of core concept"},
                    {"criterion": "Completeness", "marks": 1, "description": "Answer is complete and coherent"}
                ]

        else:  # Default: short answer
            if marks >= 4:
                rubric["criteria"] = [
                    {"criterion": "Accuracy", "marks": marks // 2, "description": "Factually correct information"},
                    {"criterion": "Completeness", "marks": marks - marks // 2, "description": "Covers all required aspects"}
                ]
            else:
                rubric["criteria"] = [
                    {"criterion": "Correct Answer", "marks": marks, "description": "Provides accurate and complete response"}
                ]

        # Add model answer reference
        if answer:
            rubric["model_answer"] = answer[:500] + "..." if len(answer) > 500 else answer

        return rubric

    def generate_paper_rubric(self, paper_id: str) -> Dict:
        """Generate rubrics for all questions in a paper"""
        paper = self.get_paper(paper_id)
        if not paper:
            return {"error": "Paper not found"}

        result = {
            "paper_id": paper_id,
            "title": paper.get('template_name', 'Question Paper'),
            "subject": paper.get('subject', ''),
            "total_marks": paper.get('total_marks', 0),
            "sections": []
        }

        for section in paper.get('sections', []):
            section_rubric = {
                "name": section.get('name', ''),
                "questions": []
            }
            for q in section.get('questions', []):
                rubric = self.generate_rubric(q)
                section_rubric["questions"].append(rubric)
            result["sections"].append(section_rubric)

        return result

    def export_rubric_markdown(self, paper_id: str) -> str:
        """Export paper rubric as markdown"""
        rubric_data = self.generate_paper_rubric(paper_id)
        if "error" in rubric_data:
            return ""

        lines = []
        lines.append(f"# MARKING RUBRIC")
        lines.append(f"## {rubric_data.get('title', 'Question Paper')}")
        lines.append(f"**Subject:** {rubric_data.get('subject', 'N/A')}")
        lines.append(f"**Total Marks:** {rubric_data.get('total_marks', 0)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for section in rubric_data.get('sections', []):
            lines.append(f"### {section['name']}")
            lines.append("")

            for q in section.get('questions', []):
                lines.append(f"#### Q{q['question_number']}: {q['topic']} [{q['total_marks']} marks]")
                lines.append("")
                lines.append("| Criterion | Marks | Description |")
                lines.append("|-----------|-------|-------------|")
                for c in q.get('criteria', []):
                    lines.append(f"| {c['criterion']} | {c['marks']} | {c['description']} |")
                lines.append("")

                if q.get('model_answer'):
                    lines.append(f"**Model Answer:** {q['model_answer']}")
                    lines.append("")

        return "\n".join(lines)

    # ========== ANALYTICS ==========

    def get_analytics(self) -> Dict:
        """Get analytics data for the dashboard"""
        from app.core.question_bank import get_question_count, DB_PATH
        import sqlite3

        stats = {
            "papers": {
                "total": 0,
                "by_subject": {}
            },
            "templates": {
                "total": 0
            },
            "questions": {
                "total_in_bank": 0,
                "by_topic": [],
                "by_difficulty": {}
            },
            "generation": {
                "total_generated": 0,
                "cache_hits": 0,
                "cache_hit_rate": 0
            }
        }

        # Count papers
        papers = list(PAPERS_DIR.glob("paper_*.json"))
        stats["papers"]["total"] = len(papers)

        # Analyze papers by subject
        for f in papers:
            try:
                data = json.loads(f.read_text())
                subject = data.get('subject', 'Unknown')
                stats["papers"]["by_subject"][subject] = stats["papers"]["by_subject"].get(subject, 0) + 1

                # Count generated questions
                for section in data.get('sections', []):
                    for q in section.get('questions', []):
                        stats["generation"]["total_generated"] += 1
                        if q.get('from_cache'):
                            stats["generation"]["cache_hits"] += 1
            except:
                continue

        # Calculate cache hit rate (as decimal 0-1, frontend will format as percentage)
        if stats["generation"]["total_generated"] > 0:
            stats["generation"]["cache_hit_rate"] = round(
                stats["generation"]["cache_hits"] / stats["generation"]["total_generated"], 4
            )

        # Count templates
        stats["templates"]["total"] = len(self.list_templates())

        # Question bank stats
        stats["questions"]["total_in_bank"] = get_question_count()

        # Get topic distribution from question bank
        try:
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()

                # By topic
                c.execute("""
                    SELECT topic, COUNT(*) as count
                    FROM templates
                    GROUP BY topic
                    ORDER BY count DESC
                    LIMIT 10
                """)
                stats["questions"]["by_topic"] = [
                    {"topic": row[0], "count": row[1]} for row in c.fetchall()
                ]

                # By difficulty
                c.execute("""
                    SELECT difficulty, COUNT(*) as count
                    FROM templates
                    GROUP BY difficulty
                """)
                for row in c.fetchall():
                    stats["questions"]["by_difficulty"][row[0]] = row[1]
        except:
            pass

        return stats


# Singleton
_service = None

def get_paper_service() -> PaperGeneratorService:
    global _service
    if not _service:
        _service = PaperGeneratorService()
    return _service
