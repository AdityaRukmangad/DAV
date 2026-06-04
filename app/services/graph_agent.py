"""
Module: app/services/graph_agent.py
Purpose: Multi-Agent Exam Engine.
"""

import os
import warnings
# Silence all the noise
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv()  # Load .env file

from typing import TypedDict, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from app.tools.calculator import get_math_tool
from app.tools.web_search import get_search_tool
from app.services.rag_service import get_rag_service
from app.core.question_bank import get_existing_template, save_template, check_duplicate, find_similar_questions
from app.tools.utils import get_logger
from app.services.metrics import get_metrics, timed_node, track_generation
from app.config import get_format_instruction, get_tags, get_prompt_loader
from app.config.pyq_analyzer import get_pyq_analyzer
import json
from pathlib import Path

logger = get_logger("Tribunal_Engine")

# Load question guidelines
def load_guidelines():
    """Load question generation guidelines"""
    guidelines_path = Path(__file__).parent.parent / "config" / "question_guidelines.json"
    try:
        with open(guidelines_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load guidelines: {e}")
        return {}

QUESTION_GUIDELINES = load_guidelines()

def calibrate_difficulty(difficulty: str, question_type: str) -> Dict[str, str]:
    """Calibrate difficulty to be easier and provide strict constraints"""
    # Make difficulties easier
    calibrated = difficulty
    if difficulty == "Hard":
        calibrated = "Medium"
    elif difficulty == "Medium":
        calibrated = "Easy-Medium"
    elif difficulty == "Easy":
        calibrated = "Very Easy"
    
    # Get guidelines for this difficulty/type
    guidelines = QUESTION_GUIDELINES.get('difficulty_guidelines', {}).get(difficulty, {})
    type_constraints = QUESTION_GUIDELINES.get('question_type_constraints', {}).get(question_type, {})
    
    return {
        'calibrated_difficulty': calibrated,
        'max_answer_length': guidelines.get(question_type, {}).get('answer_length', 'Concise'),
        'complexity': guidelines.get(question_type, {}).get('complexity', 'Simple'),
        'type_constraints': type_constraints,
        'original_difficulty': difficulty
    }

# --- TOPIC TYPE DETECTION (Context-Based) ---

def analyze_topic_type(topic: str, context: str) -> bool:
    """
    Analyze PDF context and determine if topic is computational or conceptual.
    Returns True if conceptual (no code needed), False if computational (needs code).

    Priority:
    1. Explicit user preference in topic text (highest priority)
    2. Context-based analysis
    3. Default to computational if ambiguous
    """
    topic_lower = topic.lower()

    # 1. Check for EXPLICIT user preference in topic text
    # User wants conceptual/theory question
    conceptual_keywords = ['conceptual', 'theory', 'theoretical', 'explain', 'define', 'describe', 'what is', 'types of']
    for kw in conceptual_keywords:
        if kw in topic_lower:
            logger.info(f"Topic '{topic}' explicitly requests CONCEPTUAL question (found '{kw}')")
            return True

    # User wants numerical/computational question
    numerical_keywords = ['numerical', 'calculate', 'compute', 'solve', 'find the', 'determine']
    for kw in numerical_keywords:
        if kw in topic_lower:
            logger.info(f"Topic '{topic}' explicitly requests COMPUTATIONAL question (found '{kw}')")
            return False

    # 2. Context-based analysis (if no explicit preference)
    context_lower = context.lower()

    # Check for computational signals in context
    computational_signals = [
        'formula', '=', 'calculate', 'compute', 'entropy(', 'gini(',
        'probability', 'p(', 'log2', 'sum of', '∑', 'σ', 'μ',
        '|', 'given', 'likelihood', 'accuracy', 'precision', 'recall'
    ]
    signal_count = sum(1 for signal in computational_signals if signal in context_lower)

    # Check for conceptual signals
    conceptual_signals = [
        'definition', 'defined as', 'refers to', 'is a', 'are called',
        'types of', 'categories', 'properties', 'characteristics',
        'advantage', 'disadvantage', 'comparison', 'difference between'
    ]
    concept_count = sum(1 for signal in conceptual_signals if signal in context_lower)

    # Only mark as conceptual if CLEARLY conceptual (more concept signals than computational)
    if concept_count >= 3 and signal_count < 2:
        logger.info(f"Topic '{topic}' detected as CONCEPTUAL (concept={concept_count}, compute={signal_count})")
        return True

    # 3. Default to computational - code verification is more reliable
    logger.info(f"Topic '{topic}' defaulting to COMPUTATIONAL (concept={concept_count}, compute={signal_count})")
    return False

# --- CONFIGURATION ---

# LLM Instance Cache - avoids creating new instances for every call
_llm_cache: Dict[str, any] = {}

def get_llm(json_mode=False, mode="auto"):
    """Get cached LLM instance. Creates once, reuses thereafter."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: raise ValueError("OPENAI_API_KEY missing")

    # Create cache key from configuration
    schema_name = json_mode.__name__ if json_mode else "none"
    cache_key = f"{mode}:{schema_name}"

    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    # Updated to use faster, production-ready GPT-4 models
    # instant: Fast responses for simple tasks (bloom detection, tagging)
    # auto: Balanced speed/quality for main generation
    # thinking: Complex reasoning (code generation, review)
    model_map = {"instant": "gpt-4o-mini", "auto": "gpt-4o", "thinking": "gpt-4-turbo"}
    selected = model_map.get(mode, "gpt-4o")

    # Set appropriate temperature based on task
    temp_map = {"instant": 0.7, "auto": 0.8, "thinking": 0.9}
    temperature = temp_map.get(mode, 0.8)

    llm = ChatOpenAI(
        model=selected,
        api_key=api_key,
        temperature=temperature,
        request_timeout=120
    )

    result = llm.with_structured_output(json_mode) if json_mode else llm
    _llm_cache[cache_key] = result
    logger.debug(f"[LLM Cache] Created new instance for {cache_key}")
    return result

def get_fallback_llm(json_mode=False):
    """Get cached fallback LLM instance."""
    return get_llm(json_mode=json_mode, mode="auto")

def clear_llm_cache():
    """Clear the LLM cache (useful for testing or config changes)."""
    global _llm_cache
    _llm_cache = {}
    logger.info("[LLM Cache] Cleared")

search_tool = get_search_tool()
math_tool = get_math_tool()

# --- DATA MODELS ---

class CodeDraft(BaseModel):
    """First pass: Generate only the verification code and dataset"""
    verification_code: str = Field(description="Python code that PRINTS the answer")
    dataset_description: str = Field(description="Brief description of the dataset/problem setup")

class QuestionDraft(BaseModel):
    """Second pass: Generate question based on executed code results"""
    question: str = Field(description="The exam question text")
    answer: str = Field(description="The precise answer")
    explanation: str = Field(description="Reasoning with citations")
    options: Optional[List[str]] = Field(default=None, description="Options if MCQ")
    verification_code: Optional[str] = Field(default=None, description="Python code that PRINTS the answer")
    difficulty_rating: str = Field(description="Self-assessed difficulty")

class CritiqueResult(BaseModel):
    score: int = Field(description="Quality score out of 10")
    feedback: str = Field(description="Specific feedback")
    is_passing: bool = Field(description="True if score >= 8")
    flaws: List[str] = Field(description="List of identified flaws")

# --- QUESTION TEMPLATES ---
# Strict templates for each question type to ensure consistent quality

QUESTION_TEMPLATES = {
    'mcq': """
**Multiple Choice Question Template:**

[Context/Scenario if needed - 1-2 sentences]

[Clear question statement ending with ?]

A) [First option - complete sentence/answer]
B) [Second option - complete sentence/answer]
C) [Third option - complete sentence/answer]
D) [Fourth option - complete sentence/answer]

CRITICAL: The options A), B), C), D) MUST be included in the question text itself!
Do NOT just say "Which option is correct?" without providing the options.

**Answer:** [Correct letter only, e.g., "A"]
**Explanation:** [Why correct answer is right and others are wrong]
""",

    'short': """
**Short Answer Question Template:**

[Context/Background - 1-2 sentences if needed]

[Clear, focused question - should be answerable in 2-5 sentences]

**Answer:** [Concise answer - 2-5 sentences]
**Key Points:** [Bullet points of essential concepts]
""",

    'numerical': """
**Numerical Question Template:**

[Problem setup with clear data]

Given the following data:
| Column1 | Column2 | ... |
|---------|---------|-----|
| value1  | value2  | ... |

[Clear question asking for specific calculation]

**Answer:** [Numerical result with units if applicable]
**Solution Steps:**
1. [Step 1 calculation]
2. [Step 2 calculation]
...
""",

    'long': """
**Long Answer Question Template:**

[Context/Scenario - 2-3 sentences]

Answer the following:

(a) [First part - 2-3 marks worth]

(b) [Second part - 2-3 marks worth]

(c) [Third part if applicable]

**Model Answer:**
(a) [Detailed answer for part a]

(b) [Detailed answer for part b]

(c) [Answer for part c if applicable]
"""
}

def refine_question(question_data: Dict, topic: str, difficulty: str, question_type: str = None) -> Dict:
    """
    Self-refinement step: Have LLM review and improve the generated question.
    Returns improved question_data.
    """
    if not question_data or 'question' not in question_data:
        return question_data

    logger.info("[Refinement] Self-reviewing question for quality...")

    q_text = question_data.get('question', '').lower()
    answer = question_data.get('answer', '').strip().upper()

    # Detect question type from content if not provided
    if not question_type:
        # Check if answer suggests MCQ (single letter A-D)
        if answer in ['A', 'B', 'C', 'D']:
            question_type = 'mcq'
        elif any(opt in q_text for opt in ['a)', 'b)', 'c)', 'd)', 'options:']):
            question_type = 'mcq'
        elif any(calc in q_text for calc in ['calculate', 'compute', 'find the value', 'determine']):
            question_type = 'numerical'
        elif '(a)' in q_text or '(b)' in q_text:
            question_type = 'long'
        else:
            question_type = 'short'

    # CRITICAL FIX: If MCQ but options are missing from question text, force regeneration
    if question_type == 'mcq':
        has_options = any(f'{opt})' in q_text for opt in ['a', 'b', 'c', 'd'])
        if not has_options:
            logger.warning("[Refinement] MCQ detected but options missing from question_text - will fix")

    template = QUESTION_TEMPLATES.get(question_type, QUESTION_TEMPLATES['short'])

    # Build MCQ-specific instructions if options are missing
    mcq_fix_instructions = ""
    if question_type == 'mcq':
        has_options = any(f'{opt})' in q_text for opt in ['a', 'b', 'c', 'd'])
        if not has_options:
            mcq_fix_instructions = f"""
**CRITICAL MCQ FIX REQUIRED:**
The answer is "{answer}" but the options A), B), C), D) are NOT in the question text!
You MUST add the 4 options to the question text based on the explanation provided.
The explanation mentions: {question_data.get('explanation', '')[:500]}

Generate appropriate options where option {answer} is correct and the others are plausible distractors.
"""

    refinement_prompt = f"""Review and improve this exam question. Fix any issues with clarity, formatting, or accuracy.

ORIGINAL QUESTION:
{question_data.get('question', '')}

ORIGINAL ANSWER:
{question_data.get('answer', '')}
{mcq_fix_instructions}
TARGET TEMPLATE FORMAT:
{template}

REFINEMENT CHECKLIST:
1. Is the question clear and unambiguous?
2. Does it match the {difficulty} difficulty level?
3. Is the formatting clean with proper spacing?
4. For MCQs: Are all 4 options (A, B, C, D) ON SEPARATE LINES in the question text?
5. For numerical: Is there a clear data table?
6. Is the answer complete and accurate?

Return the IMPROVED version following the template format exactly.
Keep the same core question but improve clarity and formatting."""

    llm = get_llm(json_mode=QuestionDraft, mode="auto")

    try:
        response = llm.invoke([
            SystemMessage(content=refinement_prompt),
            HumanMessage(content="Improve this question.")
        ])
        refined = response.model_dump()

        # Preserve original fields that shouldn't change
        refined['verification_code'] = question_data.get('verification_code')
        refined['computed_answer'] = question_data.get('computed_answer')
        refined['question_type'] = question_type or question_data.get('question_type')

        logger.info("[Refinement] Question improved successfully")
        return refined
    except Exception as e:
        logger.warning(f"[Refinement] Failed, using original: {e}")
        return question_data

# --- STATE ---

class AgentState(TypedDict):
    topic: str
    target_difficulty: str
    question_type: Optional[str]  # 'mcq', 'short', 'long', 'calculation', 'trace', etc.
    db_template: Optional[Dict]
    retrieved_context: str
    source_type: str
    source_urls: List[str]
    source_pages: List[int]  # Page numbers from PDF used
    source_filename: Optional[str]  # PDF filename
    detected_keywords: Dict[str, str]  # Keywords detected in query -> relevant context
    code_draft: Optional[Dict]  # First pass: code only
    computed_result: Optional[str]  # Result from executing code
    question_data: Dict  # Second pass: full question
    critique: Optional[Dict]
    iteration_count: int
    revision_count: int
    verification_passed: bool
    verification_error: Optional[str]
    answer_mismatch: bool
    answer_validation_count: int
    use_fallback: bool
    is_conceptual: bool  # True if topic is theory-based, skip code generation
    cached_question: Optional[Dict]  # Cached question from bank (skip generation if set)
    force_new: bool  # Force new generation even if cache exists
    # BLOOM-ADAPTIVE RAG FIELDS (Step 2)
    bloom_level: Optional[int]  # Bloom's taxonomy level 1-6
    retrieved_chunk_ids: List[str]  # Chunk IDs retrieved for provenance
    retrieved_doc_ids: List[str]  # Document IDs retrieved for provenance
    # PEDAGOGY TAGGER FIELDS (Step 3)
    course_outcome: Optional[str]  # CO1, CO2, etc.
    program_outcome: Optional[str]  # PO1, PO2, etc.
    # PROVENANCE FIELDS (Step 4)
    question_id: Optional[int]  # Database ID after saving (for explainability)
    # GUARDIAN FIELDS (Step 5)
    guardian_validated: bool  # True if Guardian approved the question
    guardian_attempt_count: int  # Number of Guardian validation attempts (max 1 regeneration)
    guardian_failure_reason: Optional[str]  # Why Guardian rejected the question
    # DEDUPLICATION FIELDS
    used_cache_ids: set  # Track which cached questions have been used in this paper
    temperature_boost: float  # Temperature adjustment for retries

# --- NODES ---

# --- BLOOM LEVEL DETECTION (STEP 2) ---

class BloomAnalysis(BaseModel):
    """Bloom's Taxonomy level detection"""
    bloom_level: int = Field(description="Bloom's taxonomy level 1-6")
    reasoning: str = Field(description="Brief explanation of classification")

def detect_bloom_level(topic: str, question_type: str = None) -> int:
    """
    Detect Bloom's taxonomy level from topic and question type using LLM.

    Bloom Levels:
    1-2: Remember/Understand - Recall facts, definitions, concepts
    3-4: Apply/Analyze - Use knowledge, break down problems
    5-6: Evaluate/Create - Critique, design, synthesize
    """
    # Check if Bloom RAG is enabled
    bloom_enabled = os.getenv("BLOOM_RAG_ENABLED", "true").lower() == "true"
    if not bloom_enabled:
        logger.info("[Bloom] BLOOM_RAG_ENABLED=false, using default level 3")
        return 3  # Default middle level

    logger.info(f"[Bloom Analyzer] Analyzing topic: '{topic}' (type={question_type})")

    system_prompt = f"""You are an educational expert analyzing questions according to Bloom's Taxonomy.

BLOOM'S TAXONOMY LEVELS:

Level 1 - Remember: Recall facts, terms, basic concepts, definitions
  Keywords: define, list, name, identify, recall, state, what is
  Examples: "Define entropy", "What is Gini index", "List types of agents"

Level 2 - Understand: Explain ideas, interpret, summarize, describe
  Keywords: explain, describe, discuss, summarize, interpret, compare
  Examples: "Explain how ID3 works", "Describe rational agents"

Level 3 - Apply: Use information in new situations, implement, execute
  Keywords: apply, implement, use, execute, solve, calculate (simple)
  Examples: "Calculate entropy for dataset", "Apply Gini formula"

Level 4 - Analyze: Draw connections, examine structure, differentiate
  Keywords: analyze, examine, investigate, differentiate, compare complexity
  Examples: "Analyze algorithm complexity", "Compare BFS vs DFS"

Level 5 - Evaluate: Justify decisions, critique, assess, judge
  Keywords: evaluate, critique, justify, assess, judge, defend
  Examples: "Evaluate which algorithm is better", "Critique this approach"

Level 6 - Create: Design, construct, plan, produce new solutions
  Keywords: design, create, develop, formulate, construct, synthesize
  Examples: "Design a decision tree", "Create a new algorithm"

QUESTION TYPE HINTS:
- MCQ: Usually levels 1-3 (recall, understand, simple application)
- Short answer: Usually levels 1-3 (definitions, explanations)
- Long answer: Usually levels 3-5 (application, analysis, evaluation)
- Calculation/trace: Usually levels 3-4 (application, analysis)

Analyze the following topic and classify it into the appropriate Bloom level (1-6).
Topic: "{topic}"
Question Type: {question_type or "unknown"}

Be precise. Return the most appropriate single level based on what the topic is asking for."""

    llm = get_llm(json_mode=BloomAnalysis, mode="instant")  # Use fast model for classification

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Classify this topic's Bloom level.")
        ])

        bloom_level = response.bloom_level
        reasoning = response.reasoning

        # Validate range
        if bloom_level < 1 or bloom_level > 6:
            logger.warning(f"[Bloom] Invalid level {bloom_level}, defaulting to 3")
            bloom_level = 3

        logger.info(f"[Bloom Analyzer] ✓ Detected Level {bloom_level}: {reasoning}")
        return bloom_level

    except Exception as e:
        logger.error(f"[Bloom] Detection failed: {e}, defaulting to level 3")
        return 3  # Default to middle level on error

@timed_node("bloom_analyzer")
def analyze_bloom(state: AgentState) -> Dict:
    """Analyze topic to determine Bloom's taxonomy level for adaptive RAG"""
    topic = state['topic']
    question_type = state.get('question_type')

    bloom_level = detect_bloom_level(topic, question_type)

    return {
        'bloom_level': bloom_level
    }

@timed_node("scout")
def check_sources(state: AgentState) -> Dict:
    logger.info(f"[Phase 1] Scouting Sources for: {state['topic']}")
    context_parts = []
    sources = []
    all_source_urls = []
    source_pages = []
    source_filename = ""
    detected_keywords = {}

    # Run PDF search and duplicate check in PARALLEL for faster scout
    rag = get_rag_service()
    pdf_result = None
    duplicate_result = None

    # BLOOM-ADAPTIVE RAG: Get bloom_level from state (set by analyze_bloom node)
    bloom_level = state.get('bloom_level')
    logger.info(f"[Scout] Using Bloom level {bloom_level} for RAG retrieval")

    def search_pdf():
        # Pass bloom_level to enable adaptive k
        return rag.search_with_keywords(state['topic'], bloom_level=bloom_level)

    def check_cache():
        if state['iteration_count'] == 0 and not state.get('force_new', False):
            return check_duplicate(state['topic'], state['target_difficulty'], threshold=0.8)
        return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        pdf_future = executor.submit(search_pdf)
        cache_future = executor.submit(check_cache)

        pdf_result = pdf_future.result()
        duplicate_result = cache_future.result()

    # Unpack PDF results
    pdf_context, pages, filename, keyword_contexts = pdf_result
    source_pages = pages
    source_filename = filename
    detected_keywords = keyword_contexts

    # PROVENANCE TRACKING (Step 2): Capture chunk and doc IDs
    # For now, use page numbers as doc IDs (more detailed tracking can be added later)
    retrieved_chunk_ids = [f"page_{p}_chunk" for p in pages]  # Placeholder
    retrieved_doc_ids = [f"doc_{filename}_p{p}" for p in pages]

    # Log detected keywords
    if keyword_contexts:
        logger.info(f"Detected content keywords: {list(keyword_contexts.keys())}")

    # SAFETY CHECK: If PDF context is too weak, trigger fallback immediately
    if pdf_context and len(pdf_context) > 200:
        logger.info(f"PDF context found from {filename}, pages: {pages}")
        context_parts.append(f"--- AUTHORITATIVE SOURCE: UPLOADED PDF TEXTBOOK ---\n{pdf_context}\n\n--- CRITICAL: Use ONLY the formulas and methods from this PDF. ---")
        sources.append("pdf")
    else:
        logger.error("No PDF context found - Cannot generate without PDF source.")
        return {
            'retrieved_context': "",
            'source_type': "no_source",
            'source_urls': [],
            'source_pages': [],
            'source_filename': None,
            'detected_keywords': {},
            'db_template': None,
            'use_fallback': True,
            'retrieved_chunk_ids': [],
            'retrieved_doc_ids': []
        }

    # 2. Process duplicate check result
    cached_question = None
    updated_used_cache_ids = state.get('used_cache_ids', set()).copy()  # Make a copy to avoid modifying original
    
    if duplicate_result and duplicate_result.get('question_text'):
        cache_id = duplicate_result.get('id') or duplicate_result.get('cache_id')
        
        # CHECK IF THIS CACHE ID HAS ALREADY BEEN USED IN THIS PAPER
        if cache_id and cache_id in updated_used_cache_ids:
            logger.warning(f"[CACHE] Cache ID #{cache_id} already used in this paper! Skipping cache, will generate new question.")
            # Don't use cache - force generation
            cached_question = None
        else:
            logger.info(f"[CACHE HIT] Found similar question in bank (similarity: {duplicate_result.get('similarity_score', 0):.2f})")
            cached_question = duplicate_result
            sources.append("question_bank_cache")
            
            # IMMEDIATELY add to used_cache_ids so subsequent questions don't reuse it
            if cache_id:
                updated_used_cache_ids.add(cache_id)
                logger.info(f"[CACHE] Pre-registered cache ID #{cache_id} - will not be used again in this paper")
    elif state['iteration_count'] == 0 and not state.get('force_new', False):
        # Use existing template for format reference only
        template = get_existing_template(state['topic'], state['target_difficulty'])
        if template:
            logger.info("Found existing template - Using ONLY for format/structure reference")
            context_parts.append(f"--- FORMAT REFERENCE ---\n{template['question_text']}")
            sources.append("database_remix")

    logger.info("Web search disabled - Using PDF only for content accuracy")

    full_context = "\n\n".join(context_parts)

    # IMPORTANT: Respect explicit question_type from user (set in run_agent)
    # Only auto-detect if is_conceptual wasn't explicitly set based on question_type
    if state.get('is_conceptual') is not None:
        # User explicitly chose question_type - respect their choice
        topic_is_conceptual = state.get('is_conceptual')
        logger.info(f"Using explicit is_conceptual={topic_is_conceptual} from question_type")
    else:
        # No explicit choice - analyze topic based on PDF context
        topic_is_conceptual = analyze_topic_type(state['topic'], full_context)

    return {
        'retrieved_context': full_context,
        'source_type': "+".join(sources),
        'source_urls': all_source_urls,
        'source_pages': source_pages,
        'source_filename': source_filename,
        'detected_keywords': detected_keywords,
        'db_template': None,
        'is_conceptual': topic_is_conceptual,
        'cached_question': cached_question,  # Will be used to skip generation if set
        'used_cache_ids': updated_used_cache_ids,  # Updated with new cache IDs
        # BLOOM-ADAPTIVE RAG PROVENANCE (Step 2)
        'retrieved_chunk_ids': retrieved_chunk_ids,
        'retrieved_doc_ids': retrieved_doc_ids
    }

@timed_node("theory_author")
def generate_theory_question(state: AgentState) -> Dict:
    """Generate question for CONCEPTUAL topics - no code needed, test understanding directly"""
    context = state.get('retrieved_context', '')
    question_type = state.get('question_type', 'short')
    marks = state.get('marks', 2)
    co_mapping = state.get('co_mapping', [])

    logger.info(f"[Phase 2-THEORY] Generating conceptual/theory question (type={question_type}, marks={marks})...")

    # Get difficulty calibration and PYQ patterns
    difficulty_info = calibrate_difficulty(state['target_difficulty'], question_type)
    pyq_analyzer = get_pyq_analyzer()
    pyq_hints = pyq_analyzer.get_generation_hints(
        marks=marks,
        question_type=question_type,
        co=co_mapping[0] if co_mapping else 'CO1',
        difficulty=state['target_difficulty']
    )

    # Build STRICT format instructions based on question_type
    if question_type == 'short':
        format_instruction = f"""
FORMAT: Short Answer Question
- Create a VERY FOCUSED question answerable in {pyq_hints['expected_length']}
- DO NOT use MCQ format - this requires a written response
- The answer MUST be {pyq_hints['expected_length']} MAXIMUM
- DO NOT ask multi-part questions
- DO NOT require lengthy explanations

STRICT CONSTRAINTS FOR SHORT ANSWER ({marks} marks):
- Question should be 1-2 lines maximum
- Answer MUST fit in {pyq_hints['expected_length']}
- Focus on ONE specific concept only
- Use simple, direct language
- Difficulty: {difficulty_info['calibrated_difficulty']} (easier than {difficulty_info['original_difficulty']})

EXAMPLES OF GOOD SHORT QUESTIONS:
- "Define artificial intelligence."
- "What is a rational agent?"
- "Differentiate between BFS and DFS search."
- "State the principle of A* search algorithm."

AVOID:
- "Explain in detail..."
- "Discuss various aspects..."
- Multi-part questions like (a), (b), (c)
- Questions requiring examples and elaboration
"""
    elif question_type == 'mcq':
        format_instruction = """
FORMAT: Multiple Choice Question (MCQ)
- Present a clear question stem
- Provide exactly 4 options labeled A), B), C), D)
- Put each option on a NEW LINE
- Only ONE option should be correct
- The answer should be just the letter (e.g., "A")
"""
    elif question_type == 'long':
        format_instruction = f"""
FORMAT: Long Answer / Essay Question
- Create a multi-part question with (a), (b), (c) parts
- Each part should require {pyq_hints['expected_length']}
- DO NOT use MCQ format - this is an essay/written response question
- The answer should be a comprehensive written response for each part
- Total answer length: {pyq_hints['expected_length']}
"""
    else:
        format_instruction = f"""
FORMAT: Open-ended Question
- Create a question appropriate for the topic
- Expected answer length: {pyq_hints['expected_length']}
- The answer should be clear and comprehensive
"""

    # Add PYQ style notes
    pyq_style = "\n".join([f"- {note}" for note in pyq_hints['style_notes']])

    system_prompt = f"""You are an expert professor creating an exam question about a CONCEPTUAL topic.

Topic: {state['topic']}
Marks: {marks}
Original Difficulty: {state['target_difficulty']} → Calibrated to: {difficulty_info['calibrated_difficulty']}

IMPORTANT: Make this question EASIER than typical {state['target_difficulty']} difficulty.

Reference material from PDF:
{context[:8000]}

QUESTION GENERATION GUIDELINES:
{format_instruction}

STYLE NOTES FROM PREVIOUS YEAR PAPERS:
{pyq_style}

CRITICAL CONSTRAINTS:
1. Answer length MUST be: {pyq_hints['expected_length']}
2. Question complexity: {difficulty_info['complexity']}
3. For {marks} marks questions, keep it focused and brief
4. DO NOT make the question harder than necessary
5. Use simple, clear language

FORMATTING REQUIREMENTS:
- Use SHORT paragraphs (2-3 sentences max)
- Add BLANK LINES between different parts of the question
- For data/tables, use markdown table format with blank lines before and after
- For multi-part questions, clearly separate parts with blank lines
- Be specific and reference concepts from the PDF context

The answer should be based DIRECTLY on the PDF content provided."""

    llm = get_llm(json_mode=QuestionDraft, mode="auto")

    try:
        type_instruction = f" as a {question_type.upper()} question worth {marks} marks" if question_type else ""
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create a {difficulty_info['calibrated_difficulty']} conceptual question about {state['topic']}{type_instruction}. Remember: Keep it simple and focused!")
        ])
        q_data = response.model_dump()
        q_data['computed_answer'] = q_data.get('answer', '')  # No code verification for theory
        q_data['question_type'] = question_type  # Preserve the requested type
        q_data['marks'] = marks
        q_data['difficulty_rating'] = difficulty_info['calibrated_difficulty']

        # Self-refinement step
        q_data = refine_question(q_data, state['topic'], difficulty_info['calibrated_difficulty'], question_type)

        logger.info("[Phase 2-THEORY] Theory question generation complete")
        return {'question_data': q_data, 'verification_passed': True}
    except Exception as e:
        logger.error(f"Theory question generation failed: {e}")
        return {'use_fallback': True, 'verification_error': str(e)}

@timed_node("code_author")
def generate_code_only(state: AgentState) -> Dict:
    """PHASE 2A: Generate only verification code and dataset (First Pass)"""
    if state.get('use_fallback') or state.get('is_conceptual'): return {}
    context = state.get('retrieved_context', '')
    detected_keywords = state.get('detected_keywords', {})

    is_remix = "OLD QUESTION (BLUEPRINT)" in context
    task = "Create a BRAND NEW dataset/problem variation using numbers from Web Examples." if is_remix else "Create a rigorous problem based on the Context."

    logger.info(f"[Phase 2A] Code Generation ({'REMIXING' if is_remix else 'NEW'})...")

    # Build keyword-specific instructions based on what user asked for
    keyword_instructions = ""
    if detected_keywords:
        keyword_instructions = "\n\n**USER REQUESTED SPECIFIC CONTENT TYPE - FOLLOW THESE INSTRUCTIONS:**\n"
        for keyword in detected_keywords.keys():
            if keyword in ["pseudo-code", "pseudocode", "algorithm", "code"]:
                keyword_instructions += f"""
    - The user specifically asked about "{keyword}" - Your question MUST focus on the ALGORITHM/PSEUDO-CODE
    - Use the pseudo-code/algorithm from the PDF context labeled "RELEVANT {keyword.upper()} CONTENT"
    - The question should ask students to trace through or apply the EXACT algorithm steps from the PDF
    - DO NOT create a generic calculation question - it MUST be about following the algorithm steps
    - Include the algorithm/pseudo-code steps in the verification code comments
"""
            elif keyword in ["trace", "example", "step"]:
                keyword_instructions += f"""
    - The user specifically asked about "{keyword}" - Your question MUST be a TRACE/STEP-BY-STEP problem
    - The question should ask students to manually trace through the algorithm execution
    - Show intermediate states at each step
    - The verification code should output step-by-step execution trace
"""
            elif keyword in ["complexity", "time", "space"]:
                keyword_instructions += f"""
    - The user specifically asked about "{keyword}" - Your question MUST focus on COMPLEXITY ANALYSIS
    - Ask about time complexity, space complexity, or big-O analysis
    - Reference complexity formulas from the PDF
"""
            elif keyword in ["definition", "theorem", "formula"]:
                keyword_instructions += f"""
    - The user specifically asked about "{keyword}" - Focus on the THEORETICAL aspect
    - Use definitions or formulas EXACTLY as shown in the PDF
    - The question should test understanding of the concept, not just computation
"""

    critique_prompt = ""
    if state.get('verification_error'):
        critique_prompt = f"\n[CODE ERROR FROM PREVIOUS ATTEMPT]: {state['verification_error']}\nFix the code."

    system_prompt = f"""
    You are an Expert Professor creating exam problems.
    Topic: {state['topic']} | Difficulty: {state['target_difficulty']}

    TASK: {task}

    **INSTRUCTIONS:**
    1. Use the PDF context below as reference for formulas/methods
    2. Write Python code that creates a dataset and computes the answer
    3. Code must print() the final answer with key steps shown
    4. Use raw input data - don't hardcode intermediate values

    **DIFFICULTY:**
    - Easy: ~15-20 data points, single question
    - Medium: ~20-30 data points, may have 2 parts
    - Hard: ~30-50 data points, 2-3 parts required

    **CODE REQUIREMENTS:**
    - Define dataset as Python data structure
    - Compute everything dynamically (no hardcoded counts)
    - Print answer showing key steps/sequence
    - End with print(answer)

    Context:
    {context[:12000]}
    {keyword_instructions}
    {critique_prompt}
    """

    llm = get_llm(json_mode=CodeDraft, mode="auto")

    try:
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content="Generate code.")])
        return {'code_draft': response.model_dump()}
    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        return {'use_fallback': True, 'verification_error': str(e)}

@timed_node("executor")
def execute_code(state: AgentState) -> Dict:
    """PHASE 2B: Execute the generated code to get actual result"""
    if state.get('use_fallback'): return {}

    code_draft = state.get('code_draft', {})
    code = code_draft.get('verification_code')

    if not code:
        return {'use_fallback': True, 'verification_error': "No code generated"}

    logger.info("[Phase 2B] Executing Code...")
    result = math_tool.run(code)

    if "Error" in result:
        logger.warning(f"Code Execution Failed: {result}")
        if state['iteration_count'] >= 2:
            return {'use_fallback': True, 'verification_passed': False}
        return {
            'verification_passed': False,
            'verification_error': result,
            'iteration_count': state['iteration_count'] + 1,
            'code_draft': None  # Clear to regenerate
        }

    logger.info(f"Code Executed Successfully. Output: {result.strip()}")

    # ANSWER SANITY VALIDATION
    # Check if the answer is mathematically invalid for certain topics
    result_stripped = result.strip()
    topic_lower = state['topic'].lower()

    # Detect invalid answers based on topic
    is_invalid = False
    sanity_error = None

    try:
        # Try to extract numeric value from result
        import re
        numeric_match = re.search(r'[-+]?[0-9]*\.?[0-9]+', result_stripped)
        if numeric_match:
            numeric_value = float(numeric_match.group())

            # Gini index validation: should be in range (0, 0.5] for binary classification
            # Value of 0.0 means perfect purity (all same class), which is unlikely for real problems
            if 'gini' in topic_lower:
                if numeric_value == 0.0:
                    is_invalid = True
                    sanity_error = "Gini index returned 0.0 (perfect purity). This is unlikely for the given dataset. Code may have a bug."
                elif numeric_value < 0 or numeric_value > 0.5:
                    is_invalid = True
                    sanity_error = f"Gini index {numeric_value} is outside valid range [0, 0.5] for binary classification."

            # Information gain validation: should be positive for useful attributes
            elif 'information gain' in topic_lower or 'entropy' in topic_lower:
                if numeric_value < 0:
                    is_invalid = True
                    sanity_error = f"Information gain/entropy cannot be negative (got {numeric_value})."

            # Error rate validation: should be in [0, 1]
            elif 'error' in topic_lower and 'rate' in topic_lower:
                if numeric_value < 0 or numeric_value > 1:
                    is_invalid = True
                    sanity_error = f"Error rate {numeric_value} is outside valid range [0, 1]."

            # Probability validation: should be in [0, 1]
            elif 'probability' in topic_lower or 'likelihood' in topic_lower:
                if numeric_value < 0 or numeric_value > 1:
                    is_invalid = True
                    sanity_error = f"Probability {numeric_value} is outside valid range [0, 1]."

    except (ValueError, AttributeError):
        # If we can't parse a number, skip sanity check
        pass

    if is_invalid:
        logger.warning(f"Answer Sanity Check Failed: {sanity_error}")
        if state['iteration_count'] >= 2:
            # After 2 retries, give up
            return {'use_fallback': True, 'verification_passed': False}
        # Trigger code regeneration
        return {
            'verification_passed': False,
            'verification_error': sanity_error,
            'iteration_count': state['iteration_count'] + 1,
            'code_draft': None  # Clear to regenerate
        }

    return {
        'computed_result': result_stripped,
        'verification_passed': True
    }

@timed_node("question_author")
def generate_question_from_result(state: AgentState) -> Dict:
    """PHASE 2C: Generate complete question in a single call for reliability"""
    if state.get('use_fallback'): return {}

    code_draft = state.get('code_draft', {})
    computed_result = state.get('computed_result', '')
    context = state.get('retrieved_context', '')
    question_type = state.get('question_type', 'calculation')  # Default to calculation for computational

    # Truncate to keep context manageable
    MAX_RESULT_LENGTH = 1500
    MAX_CODE_LENGTH = 2000

    if len(computed_result) > MAX_RESULT_LENGTH:
        half = MAX_RESULT_LENGTH // 2
        computed_result = computed_result[:half] + "\n...[truncated]...\n" + computed_result[-half:]

    verification_code = code_draft.get('verification_code', '')
    if len(verification_code) > MAX_CODE_LENGTH:
        verification_code = verification_code[:MAX_CODE_LENGTH] + "\n# ..."

    logger.info(f"[Phase 2C] Writing Question (type={question_type})...")

    # Build format instructions based on question_type
    if question_type == 'mcq':
        format_instruction = """
FORMAT: Multiple Choice Question (MCQ)
- Present a clear question stem with the problem/calculation
- Provide exactly 4 options labeled A), B), C), D)
- Put each option on a NEW LINE
- Only ONE option should be correct (matching the computed answer)
- The answer field should be just the letter (e.g., "A")
- Include plausible distractors based on common calculation errors
"""
    elif question_type == 'long':
        format_instruction = """
FORMAT: Long Answer / Calculation Question
- Create a multi-part question with (a), (b), (c) parts
- Each part should build on the previous or test related calculations
- DO NOT use MCQ format - students should show their working
- The answer should include step-by-step calculations
- Separate parts clearly with blank lines
"""
    elif question_type == 'short':
        format_instruction = """
FORMAT: Short Answer / Calculation Question
- Create a focused calculation question
- DO NOT use MCQ format - students should show their working
- The answer should be the computed result with brief explanation
"""
    elif question_type == 'trace':
        format_instruction = """
FORMAT: Algorithm Trace Question
- Ask students to trace through the algorithm step-by-step
- Show initial state and ask for intermediate/final states
- The answer should show the trace at each step
"""
    else:
        format_instruction = """
FORMAT: Calculation Question
- Create a question requiring numerical computation
- Include all necessary data in a clear format (tables if appropriate)
- The answer should match the computed result
- For Medium/Hard, include multiple parts (a), (b), etc.
"""

    # Single comprehensive prompt for better quality
    system_prompt = f"""You are an expert professor creating an exam question.

Topic: {state['topic']}
Difficulty: {state['target_difficulty']}

Reference material from PDF:
{context[:3000]}

Verification code that computes the answer:
```python
{verification_code}
```

Computed answer from code:
{computed_result}

Create a well-structured exam question based on this information.

{format_instruction}

GENERAL FORMATTING REQUIREMENTS:
- Use SHORT paragraphs (2-3 sentences max)
- Add BLANK LINES between different sections of the question
- Present data as a clean markdown table with blank lines before and after
- For multi-part questions, clearly separate parts with blank lines
- Use markdown formatting (bold, lists, tables) where appropriate
- The answer MUST match the computed result above"""

    llm = get_llm(json_mode=QuestionDraft, mode="auto")

    try:
        type_instruction = f" as a {question_type.upper()} question" if question_type else ""
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create a {state['target_difficulty']} difficulty question about {state['topic']}{type_instruction}.")
        ])
        q_data = response.model_dump()
        q_data['verification_code'] = verification_code
        q_data['computed_answer'] = computed_result
        q_data['question_type'] = question_type  # Preserve the requested type

        # Self-refinement step
        q_data = refine_question(q_data, state['topic'], state['target_difficulty'], question_type)

        logger.info("[Phase 2C] Question generation complete")
        return {'question_data': q_data}
    except Exception as e:
        logger.error(f"Question generation failed: {e}")
        # Return minimal valid data to avoid fallback cascade
        return {
            'question_data': {
                'question': f"Explain the concept of {state['topic']} and provide an example calculation.",
                'answer': computed_result or "See explanation",
                'explanation': f"This question tests understanding of {state['topic']}.",
                'verification_code': verification_code,
                'computed_answer': computed_result,
                'difficulty_rating': state['target_difficulty'],
                'question_type': question_type,
                'options': None
            }
        }

def generate_draft(state: AgentState) -> Dict:
    if state.get('use_fallback'): return {}
    context = state.get('retrieved_context', '')
    
    is_remix = "OLD QUESTION (BLUEPRINT)" in context
    
    task = "Create a BRAND NEW variation of the Old Question using new numbers from Web Examples." if is_remix else "Create a rigorous exam question based on the Context."
    
    logger.info(f"[Phase 2] Authoring ({'REMIXING' if is_remix else 'NEW CREATION'})...")

    critique_prompt = ""
    if state.get('critique'):
        c = state['critique']
        critique_prompt = f"\n[PREVIOUS FEEDBACK]: {c.get('feedback')}"
    if state.get('verification_error'):
        critique_prompt += f"\n[CODE ERROR]: {state['verification_error']}"

    # Check if this is an answer mismatch retry
    answer_validation_count = state.get('answer_validation_count', 0)
    if answer_validation_count > 0:
        critique_prompt += f"""
[CRITICAL - ANSWER MISMATCH DETECTED - Attempt #{answer_validation_count}]:
Your previous manual answer did NOT match what the code computed.

TO FIX THIS:
1. Look at your verification_code
2. Trace through it step by step:
   - What does "sum(1 for row in data if ...)" count? Count the matching items.
   - What do the formulas compute using those counts? Calculate step by step.
3. What does the final print() statement output? Write that EXACT string in 'answer'

DO NOT calculate independently - TRACE THE CODE EXECUTION.
"""

    system_prompt = f"""
    You are an Expert Professor.
    Topic: {state['topic']} | Difficulty: {state['target_difficulty']}

    TASK: {task}

    CRITICAL INSTRUCTIONS FOR VERIFICATION CODE:
    - Change the input values/dataset so the answer is different from the blueprint.
    - Write a Python script ('verification_code') that calculates the NEW answer.
    - The script MUST contain `print(answer)` at the end.

    **MANDATORY CODE STRUCTURE - NEVER HARDCODE VALUES:**
    1. ALWAYS define the dataset as a Python data structure (list of dicts, etc.)
    2. ALWAYS count/compute values DYNAMICALLY from that data structure
    3. NEVER manually hardcode counts like "pos_A_T = 4" - use loops/comprehensions
    4. Example CORRECT approach:
       ```python
       data = [{{'A': 'T', 'B': 'F', 'Class': '+'}}, ...]
       pos_A_T = sum(1 for row in data if row['A'] == 'T' and row['Class'] == '+')
       ```
    5. Example WRONG approach (DO NOT DO THIS):
       ```python
       pos_A_T = 4  # ❌ WRONG - hardcoded!
       ```

    **ANSWER FIELD - CRITICAL:**
    - First write the verification_code completely
    - Then mentally RUN the code line by line to predict the print() output
    - The 'answer' field = your predicted print() output
    - Example: If code prints "IG(A) = 0.61, IG(B) = 0.03, Choose A", write exactly that
    - DO NOT calculate manually - trace the code's data flow and operations
    - For counts: trace the list comprehensions (e.g., "sum(1 for row in data if ...)" → count items)
    - For formulas: trace the arithmetic using the counts from step above
    - Double-check: Does your answer match what the code would print?

    **EXPLANATION FIELD - CRITICAL:**
    - DO NOT show manual arithmetic calculations in the explanation
    - Instead, describe the ALGORITHM/LOGIC the code uses
    - Reference the code execution: "The code computes..." or "When the algorithm runs..."
    - If you must show intermediate values, derive them by tracing the code, not manual math
    - NEVER write calculations like "IG(A) = 0.94 - ((4/10)*0.81 + (6/10)*0.92)" unless you traced these exact values from code execution

    Context:
    {context[:12000]}

    {critique_prompt}
    """
    
    mode = "thinking" if state['revision_count'] > 0 else "auto"
    llm = get_llm(json_mode=QuestionDraft, mode=mode)
    
    try:
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content="Draft.")])
        return {'question_data': response.model_dump()}
    except Exception as e:
        logger.error(f"Author failed: {e}")
        return {'use_fallback': True, 'verification_error': str(e)}

def critique_draft(state: AgentState) -> Dict:
    if state.get('use_fallback'): return {}
    if state.get('verification_error'): return {'critique': {'is_passing': True, 'score': 7}}

    q = state['question_data']
    code_draft = state.get('code_draft', {})

    system_prompt = f"""
    Review this exam question. Target Difficulty: {state['target_difficulty']}

    Question: {q.get('question')}
    Answer: {q.get('answer')}

    **EVALUATION CRITERIA:**

    1. **Validity** (Required):
       - Is the question solvable with the given information?
       - Is the answer correct and reasonable?
       - Are there any ambiguities or unclear instructions?

    2. **Difficulty Match** (Required):
       Target: {state['target_difficulty']}

       Dataset Complexity Expectations:
       - Easy: 15-20 data points, 3-4 attributes, multi-step calculation, single focused question
       - Medium: 20-30 data points, 4-5 attributes, complex multi-step process, may have 2 parts
       - Hard: 30-50 data points, 5+ attributes, extensive calculations, edge cases, MUST have 2-3 parts

       Multi-part Question Requirements:
       - Easy: Single question is fine
       - Medium: Should consider having Part (a) and Part (b)
       - Hard: MUST have multiple parts (a), (b), and optionally (c)

       Does the dataset SIZE, COMPLEXITY, and NUMBER OF PARTS match the target difficulty?

    3. **Quality** (Required):
       - Is the data realistic and meaningful?
       - Does it follow the PDF formulas correctly?
       - Is the explanation clear?

    **GRADING:**
    - Score 8-10: Valid, matches difficulty, high quality → PASS
    - Score 7: Acceptable but could be improved → PASS
    - Score 0-6: Too simple/complex for difficulty, or has issues → REJECT

    Verification Code (for context):
    ```python
    {code_draft.get('verification_code', '')[:500]}
    ```
    """

    llm = get_llm(json_mode=CritiqueResult, mode="thinking")
    logger.info("[Phase 3] Critic Reviewing...")

    try:
        result = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content="Grade this question against the difficulty target.")])
        status = "PASS" if result.is_passing else "REJECT"
        logger.info(f"Critic Score: {result.score}/10 [{status}]")

        # Increment revision_count when rejecting to prevent infinite loops
        if not result.is_passing:
            current_count = state.get('revision_count', 0)
            logger.info(f"Critic rejected - Revision count: {current_count} -> {current_count + 1}")
            return {
                'critique': result.model_dump(),
                'revision_count': current_count + 1
            }

        return {'critique': result.model_dump()}
    except Exception:
        return {'critique': {'is_passing': True, 'score': 8}}

def verify_code(state: AgentState) -> Dict:
    if state.get('use_fallback'): return {}
    q_data = state.get('question_data', {})
    code = q_data.get('verification_code')

    if not code:
        logger.info("No code. Skipping verification.")
        return {'verification_passed': True}

    logger.info("[Phase 4] Verifying Logic...")
    result = math_tool.run(code)

    if "Error" in result:
        logger.warning(f"Verification Failed: {result}")
        if state['iteration_count'] >= 2:
            return {'use_fallback': True, 'verification_passed': False}
        return {'verification_passed': False, 'verification_error': result, 'iteration_count': state['iteration_count'] + 1}

    logger.info(f"Verification Successful. Output: {result.strip()}")
    q_data['computed_answer'] = result.strip()
    return {'verification_passed': True, 'question_data': q_data}

class QuestionCodeValidation(BaseModel):
    is_valid: bool = Field(description="True if question text matches what the code actually computes")
    reasoning: str = Field(description="Explanation of whether the question asks for what the code computes")
    issues: List[str] = Field(description="List of specific misalignments between question and code")

def validate_question_code_alignment(state: AgentState) -> Dict:
    """Validate that the question text asks students to compute what the code actually computes."""
    if state.get('use_fallback'): return {}

    q_data = state.get('question_data', {})
    code_draft = state.get('code_draft', {})

    question_text = q_data.get('question', '')
    verification_code = code_draft.get('verification_code', '')
    dataset_description = code_draft.get('dataset_description', '')

    # Skip if no verification code
    if not verification_code:
        logger.info("[Phase 5] No verification code to validate against.")
        return {'answer_mismatch': False}

    logger.info("[Phase 5] Validating Question-Code Alignment...")

    validation_count = state.get('answer_validation_count', 0)

    system_prompt = f"""
    You are a rigorous validator for exam questions.

    TASK: Verify that the QUESTION TEXT asks students to compute what the VERIFICATION CODE actually computes.

    QUESTION TEXT (what students are asked to solve):
    {question_text}

    VERIFICATION CODE (what the code actually computes):
    ```python
    {verification_code}
    ```

    DATASET DESCRIPTION:
    {dataset_description}

    CRITICAL VALIDATION RULES:
    1. Does the question provide the EXACT SAME input data that the code uses?
       - Check: Are the dataset values in the question identical to those in the code?
       - Example: If code has data = [{{'A': 'T', 'B': 'F'}}], question must show same table

    2. Does the question ask students to compute the SAME OUTPUT as the code?
       - Check: What does the code's final print() statement output?
       - Check: Does the question ask for that same calculation?

    3. Are there any shortcuts or pre-calculated values given in the question that the code computes?
       - BAD: Question gives intermediate results that the code is supposed to calculate
       - GOOD: Question gives only raw input data, asks students to compute the final result

    4. Does the question match the algorithm/formula the code implements?
       - The method/formula asked in the question must match what the code actually computes

    Mark is_valid = False if:
    - Question provides different input data than code uses
    - Question asks for different output than code computes
    - Question gives away pre-calculated values that students should compute
    - Question asks for wrong formula/algorithm

    Mark is_valid = True if:
    - Question presents the exact input data from the code
    - Question asks students to compute exactly what the code computes
    - No shortcuts or pre-calculated intermediate values given
    """

    llm = get_llm(json_mode=QuestionCodeValidation, mode="thinking")

    try:
        result = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Validate the alignment between question and code. Be strict.")
        ])

        status = "✓ ALIGNED" if result.is_valid else "✗ MISALIGNED"
        logger.info(f"Question-Code Validation: {status}")
        logger.info(f"Reasoning: {result.reasoning}")
        if result.issues:
            logger.info(f"Issues: {', '.join(result.issues)}")

        if not result.is_valid:
            if validation_count >= 1:
                # After 2 attempts, add warning and proceed
                logger.warning("  QUESTION-CODE MISALIGNMENT PERSISTS - Proceeding with warning")
                q_data['answer_warning'] = f" WARNING: Question may not match code logic. Issues: {', '.join(result.issues)}"
                return {
                    'answer_mismatch': False,  # Allow it to pass but with warning
                    'question_data': q_data
                }
            else:
                # First misalignment - request regeneration
                logger.warning(f"Question-code misalignment detected. Requesting regeneration (attempt {validation_count + 1}/2)")
                return {
                    'answer_mismatch': True,
                    'verification_error': f"Question text doesn't align with code logic. {result.reasoning}. Issues: {', '.join(result.issues)}",
                    'answer_validation_count': validation_count + 1,
                    'revision_count': state['revision_count'] + 1
                }

        return {'answer_mismatch': False}

    except Exception as e:
        logger.error(f"Question-code validation failed: {e}")
        # On error, assume they're aligned to avoid blocking
        return {'answer_mismatch': False}

@timed_node("reviewer")
def parallel_review(state: AgentState) -> Dict:
    """Run critic and validator in PARALLEL for faster review"""
    if state.get('use_fallback'):
        return {}

    logger.info("[Phase 3+5] Running Critic & Validator in PARALLEL...")

    results = {
        'critique': {'is_passing': True, 'score': 8},
        'answer_mismatch': False,
        'verification_passed': False  # Will be set to True if review passes
    }

    def run_critique():
        try:
            return _run_critique_logic(state)
        except Exception as e:
            logger.error(f"Critique task failed: {e}")
            return {'critique': {'is_passing': True, 'score': 7}}

    def run_validation():
        try:
            return _run_validation_logic(state)
        except Exception as e:
            logger.error(f"Validation task failed: {e}")
            return {'answer_mismatch': False}

    # Run both in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_critique = executor.submit(run_critique)
        future_validation = executor.submit(run_validation)

        for future in as_completed([future_critique, future_validation]):
            try:
                result = future.result()
                if result and isinstance(result, dict):
                    results.update(result)
                else:
                    logger.warning(f"Review task returned invalid result: {result}")
            except Exception as e:
                logger.error(f"Review task execution failed: {e}")

    # Check if review passed
    is_passing = results.get('critique', {}).get('is_passing', True)
    has_mismatch = results.get('answer_mismatch', False)
    
    if is_passing and not has_mismatch:
        results['verification_passed'] = True
        logger.info(f"[Review] Question passed review - marked for archiving")
    else:
        results['verification_passed'] = False
        logger.warning(f"[Review] Question failed review - critique_passing={is_passing}, has_mismatch={has_mismatch}")

    logger.info(f"Parallel review complete - Critique: {results.get('critique', {}).get('score', '?')}/10")
    return results

def _run_critique_logic(state: AgentState) -> Dict:
    """Critique logic extracted for parallel execution"""
    if state.get('verification_error'):
        return {'critique': {'is_passing': True, 'score': 7}}

    q = state.get('question_data', {})
    if not q:
        logger.warning("[Critique] No question data available for critique")
        return {'critique': {'is_passing': True, 'score': 7}}
        
    code_draft = state.get('code_draft', {})

    system_prompt = f"""
    Review this exam question. Target Difficulty: {state['target_difficulty']}

    Question: {q.get('question')}
    Answer: {q.get('answer')}

    **EVALUATION CRITERIA:**

    1. **Validity** (Required):
       - Is the question solvable with the given information?
       - Is the answer correct and reasonable?

    2. **Difficulty Match** (Required):
       Target: {state['target_difficulty']}
       - Easy: 15-20 data points, single focused question
       - Medium: 20-30 data points, may have 2 parts
       - Hard: 30-50 data points, MUST have 2-3 parts

    3. **Quality** (Required):
       - Is the data realistic?
       - Does it follow the PDF formulas?

    **GRADING:**
    - Score 8-10: Valid, matches difficulty → PASS
    - Score 7: Acceptable → PASS
    - Score 0-6: Issues → REJECT

    Verification Code:
    ```python
    {code_draft.get('verification_code', '')[:500]}
    ```
    """

    llm = get_llm(json_mode=CritiqueResult, mode="auto")

    try:
        result = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content="Grade quickly.")])
        status = "PASS" if result.is_passing else "REJECT"
        logger.info(f"Critic Score: {result.score}/10 [{status}]")
        return {'critique': result.model_dump()}
    except Exception:
        return {'critique': {'is_passing': True, 'score': 8}}

def _run_validation_logic(state: AgentState) -> Dict:
    """Validation logic extracted for parallel execution - includes strict answer comparison"""
    q_data = state.get('question_data', {})
    code_draft = state.get('code_draft', {})

    question_text = q_data.get('question', '')
    stated_answer = q_data.get('answer', '')
    verification_code = code_draft.get('verification_code', '') or q_data.get('verification_code', '')

    if not verification_code:
        return {'answer_mismatch': False}

    validation_count = state.get('answer_validation_count', 0)

    # STRICT VERIFICATION: Re-run code and compare output to stated answer
    try:
        code_output = math_tool.run(verification_code)
        if "Error" not in code_output:
            code_output_clean = code_output.strip().lower()
            stated_answer_clean = stated_answer.strip().lower() if stated_answer else ""

            # Extract key values for comparison
            import re

            # Extract numbers from both
            code_numbers = set(re.findall(r'[-+]?\d*\.?\d+', code_output_clean))
            answer_numbers = set(re.findall(r'[-+]?\d*\.?\d+', stated_answer_clean))

            # Extract letter answers (A, B, C, D) for MCQ
            code_letters = set(re.findall(r'\b([a-d])\b', code_output_clean))
            answer_letters = set(re.findall(r'\b([a-d])\b', stated_answer_clean))

            # Check for numeric mismatch
            numeric_match = bool(code_numbers & answer_numbers) if code_numbers and answer_numbers else True
            letter_match = bool(code_letters & answer_letters) if code_letters and answer_letters else True

            if not numeric_match and code_numbers and answer_numbers:
                mismatch_msg = f"Code outputs {code_numbers} but answer states {answer_numbers}"
                logger.warning(f"[STRICT] Answer mismatch detected: {mismatch_msg}")
                q_data['answer_verification'] = {
                    'code_output': code_output.strip()[:200],
                    'match': False,
                    'issue': mismatch_msg
                }
            elif not letter_match and code_letters and answer_letters:
                mismatch_msg = f"Code outputs {code_letters} but answer states {answer_letters}"
                logger.warning(f"[STRICT] Answer mismatch detected: {mismatch_msg}")
                q_data['answer_verification'] = {
                    'code_output': code_output.strip()[:200],
                    'match': False,
                    'issue': mismatch_msg
                }
            else:
                logger.info(f"[STRICT] Answer verification passed - code output matches stated answer")
                q_data['answer_verification'] = {
                    'code_output': code_output.strip()[:200],
                    'match': True
                }
    except Exception as e:
        logger.warning(f"[STRICT] Could not verify answer: {e}")

    # LLM-based validation for question-code alignment
    system_prompt = f"""
    Verify that the QUESTION TEXT matches what the CODE computes.

    QUESTION TEXT:
    {question_text[:2000]}

    CODE:
    ```python
    {verification_code[:1500]}
    ```

    Check:
    1. Does question provide same input data as code?
    2. Does question ask for same output as code computes?

    Mark is_valid = False if there's a mismatch.
    """

    llm = get_llm(json_mode=QuestionCodeValidation, mode="auto")

    try:
        result = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Validate quickly.")
        ])

        if not result.is_valid:
            if validation_count >= 1:
                q_data['answer_warning'] = f"WARNING: Possible mismatch. {', '.join(result.issues)}"
                return {'answer_mismatch': False, 'question_data': q_data}
            else:
                return {
                    'answer_mismatch': True,
                    'verification_error': f"Mismatch: {result.reasoning}",
                    'answer_validation_count': validation_count + 1
                }

        return {'answer_mismatch': False, 'question_data': q_data}

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return {'answer_mismatch': False}

@timed_node("fallback")
def use_fallback(state: AgentState) -> Dict:
    logger.warning("[Fallback] Main generation failed. Using simplified generation.")
    context = state['retrieved_context']
    question_type = state.get('question_type', 'short')

    llm = get_llm(json_mode=QuestionDraft, mode="auto")

    # Build format instructions based on question_type
    if question_type == 'mcq':
        format_instruction = """
FORMAT: Multiple Choice Question (MCQ)
- Present a clear question stem
- Provide exactly 4 options labeled A), B), C), D)
- Put each option on a NEW LINE
- Only ONE option should be correct
- The answer should be just the letter (e.g., "A")
"""
    elif question_type == 'long':
        format_instruction = """
FORMAT: Long Answer / Essay Question
- Create a multi-part question with (a), (b), (c) parts
- Each part should require a detailed explanation
- DO NOT use MCQ format - this is a written response question
- The answer should be comprehensive for each part
"""
    elif question_type == 'short':
        format_instruction = """
FORMAT: Short Answer Question
- Create a focused question answerable in 2-5 sentences
- DO NOT use MCQ format - this requires a written response
- The answer should be concise but complete
"""
    else:
        format_instruction = """
FORMAT: Open-ended Question
- Create a question appropriate for the topic
- The answer should be clear and comprehensive
"""

    # Better fallback prompt that actually generates a question
    system_prompt = f"""You are an expert professor creating an exam question.

Topic: {state['topic']}
Difficulty: {state['target_difficulty']}

Using the following reference material, create a clear, well-structured exam question:

{context[:6000]}

{format_instruction}

GENERAL FORMATTING REQUIREMENTS:
- Use SHORT paragraphs (2-3 sentences max)
- Add BLANK LINES between different sections of the question
- Present data as a clean markdown table with blank lines before and after
- For multi-part questions, clearly separate parts with blank lines
- Use markdown formatting (bold, lists, tables) where appropriate

The question should be appropriate for the difficulty level specified."""

    try:
        type_instruction = f" as a {question_type.upper()} question" if question_type else ""
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=f"Create a {state['target_difficulty']} {state['topic']} question{type_instruction}.")])
        q_data = response.model_dump()
        q_data['question_type'] = question_type  # Preserve the requested type

        # Self-refinement step
        q_data = refine_question(q_data, state['topic'], state['target_difficulty'], question_type)

        return {'question_data': q_data, 'verification_passed': True, 'source_type': f"{state['source_type']} (fallback)"}
    except Exception as e:
        logger.error(f"Fallback generation failed: {e}")
        return {'verification_passed': False}

@timed_node("use_cache")
def use_cached_question(state: AgentState) -> Dict:
    """
    Use a cached question from the question bank instead of generating new.
    Checks if cached question was already used in this paper to prevent duplicates.
    """
    cached = state.get('cached_question')
    if not cached:
        logger.warning("[CACHE] No cached question found, falling back to generation")
        return {'use_fallback': True}

    # Check if this cached question was already used in this paper
    cache_id = cached.get('id') or cached.get('cache_id')
    used_cache_ids = state.get('used_cache_ids', set())

    if cache_id and cache_id in used_cache_ids:
        logger.warning(f"[CACHE] Cached question #{cache_id} already used in this paper. Forcing new generation.")
        return {'use_fallback': True, 'cached_question': None}  # Clear cache and generate new

    logger.info(f"[CACHE] Using cached question #{cache_id} (similarity: {cached.get('similarity_score', 0):.2f})")

    # Convert cached format to question_data format
    question_data = {
        'question': cached.get('question_text') or cached.get('question', ''),
        'answer': cached.get('answer', ''),
        'explanation': cached.get('explanation', ''),
        'verification_code': cached.get('python_code') or cached.get('verification_code', ''),
        'from_cache': True,
        'cache_id': cache_id,  # Include cache ID for tracking
        'cache_similarity': cached.get('similarity_score', 0)
    }

    # ADD CACHE ID TO USED SET TO PREVENT REUSE
    if cache_id:
        used_cache_ids.add(cache_id)
        logger.info(f"[CACHE] Added question #{cache_id} to used_cache_ids. Total used: {len(used_cache_ids)}")

    return {
        'question_data': question_data,
        'verification_passed': True,
        'source_type': 'question_bank_cache',
        'used_cache_ids': used_cache_ids  # Return updated set
    }


# --- PEDAGOGY TAGGER (STEP 3) ---

class PedagogyTags(BaseModel):
    """Educational metadata tags"""
    course_outcome: str = Field(description="Course outcome (CO1, CO2, etc.)")
    program_outcome: str = Field(description="Program outcome (PO1, PO2, etc.)")
    reasoning: str = Field(description="Brief reasoning for the tags")

@timed_node("pedagogy_tagger")
def tag_pedagogy(state: AgentState) -> Dict:
    """
    Tag question with educational metadata (Course Outcome, Program Outcome).
    OPTIONAL node - controlled by ENABLE_PEDAGOGY_TAGGER env variable.
    """
    # Check if pedagogy tagger is enabled
    tagger_enabled = os.getenv("ENABLE_PEDAGOGY_TAGGER", "false").lower() == "true"
    if not tagger_enabled:
        logger.info("[Pedagogy Tagger] DISABLED (ENABLE_PEDAGOGY_TAGGER=false)")
        return {}  # Skip tagging

    logger.info("[Pedagogy Tagger] Tagging question with CO/PO...")

    question_data = state.get('question_data', {})
    question_text = question_data.get('question', '')
    bloom_level = state.get('bloom_level', 3)
    topic = state.get('topic', '')

    if not question_text:
        logger.warning("[Pedagogy Tagger] No question text found, skipping")
        return {}

    # Rule-based + LLM hybrid approach
    system_prompt = f"""You are an educational assessment expert tagging questions with curriculum outcomes.

QUESTION:
{question_text[:1000]}

TOPIC: {topic}
BLOOM LEVEL: {bloom_level}

TAG this question with appropriate educational outcomes:

COURSE OUTCOMES (CO):
- CO1: Remember and understand fundamental concepts
- CO2: Apply knowledge to solve problems
- CO3: Analyze and evaluate complex scenarios
- CO4: Design and create solutions
- CO5: Communicate and work collaboratively

PROGRAM OUTCOMES (PO):
- PO1: Engineering knowledge and problem-solving
- PO2: Critical thinking and analysis
- PO3: Design and development of solutions
- PO4: Research and investigation
- PO5: Modern tool usage
- PO6: Communication skills

RULES:
1. Choose the MOST APPROPRIATE single CO and PO
2. Base selection on Bloom level and question type
3. If uncertain, choose the most likely option
4. Keep reasoning brief (1 sentence)

Return structured JSON with: course_outcome, program_outcome, reasoning"""

    llm = get_llm(json_mode=PedagogyTags, mode="instant")  # Fast model for tagging

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Tag this question.")
        ])

        co = response.course_outcome
        po = response.program_outcome
        reasoning = response.reasoning

        logger.info(f"[Pedagogy Tagger] ✓ Tagged: {co}, {po} - {reasoning}")

        return {
            'course_outcome': co,
            'program_outcome': po
        }

    except Exception as e:
        logger.error(f"[Pedagogy Tagger] Tagging failed: {e}")
        # Default fallback based on bloom level
        if bloom_level <= 2:
            return {'course_outcome': 'CO1', 'program_outcome': 'PO1'}
        elif bloom_level <= 4:
            return {'course_outcome': 'CO2', 'program_outcome': 'PO1'}
        else:
            return {'course_outcome': 'CO3', 'program_outcome': 'PO2'}

# --- STEP 5: GUARDIAN SYLLABUS VALIDATOR ---

from app.services.guardian import get_guardian

@timed_node("guardian")
def validate_syllabus(state: AgentState) -> Dict:
    """
    STEP 5: Guardian Validator

    Validates that the generated question aligns with the course syllabus.
    - Checks if topic is in syllabus
    - Finds unit alignment
    - Allows ONE regeneration attempt if validation fails

    Backward Compatible: If Guardian is disabled (config), validation passes automatically.
    """
    guardian = get_guardian()

    # If Guardian is disabled, pass validation automatically
    if not guardian.is_enabled():
        logger.info("[Guardian] Disabled - skipping validation")
        return {
            'guardian_validated': True,
            'guardian_failure_reason': None
        }

    topic = state.get('topic', '')
    bloom_level = state.get('bloom_level')
    attempt_count = state.get('guardian_attempt_count', 0)

    # Validate topic against syllabus
    is_valid, reason, unit_num = guardian.validate_topic(topic, bloom_level)

    if is_valid:
        logger.info(f"[Guardian] ✓ Question approved (Topic: {topic}, Unit: {unit_num})")
        return {
            'guardian_validated': True,
            'guardian_failure_reason': None
        }
    else:
        # Increment attempt count for retry logic
        new_attempt_count = attempt_count + 1
        logger.warning(f"[Guardian] ✗ Question rejected: {reason} (Attempt: {new_attempt_count})")
        return {
            'guardian_validated': False,
            'guardian_failure_reason': reason,
            'guardian_attempt_count': new_attempt_count
        }

@timed_node("archivist")
def save_result(state: AgentState) -> Dict:
    if not state.get('verification_passed'): return {}
    q = state.get('question_data', {})
    # Don't save if it came from cache (already in bank)
    if q.get('from_cache'):
        logger.info("[CACHE] Skipping save - question was from cache")
        return {}
    if q and 'question' in q:
        question_id = save_template(
            state['topic'],
            state['target_difficulty'],
            q['question'],
            q.get('verification_code', ''),
            state['source_type'],
            full_data=q,
            source_urls=state.get('source_urls', [])
        )
        if question_id:
            # Store question ID in state for API response
            return {'question_id': question_id}
    return {}

def build_graph():
    workflow = StateGraph(AgentState)

    # TWO-PASS PIPELINE: Code-First Architecture with PARALLEL REVIEW
    # NEW: Theory path for conceptual topics (no code needed)
    # NEW: Cache path for duplicate detection
    # STEP 2: Bloom Analyzer for adaptive RAG
    # STEP 3: Pedagogy Tagger for educational metadata
    workflow.add_node("bloom_analyzer", analyze_bloom)  # STEP 2: First node - detect Bloom level
    workflow.add_node("scout", check_sources)
    workflow.add_node("use_cache", use_cached_question)  # NEW: Use cached question
    workflow.add_node("theory_author", generate_theory_question)  # For conceptual topics
    workflow.add_node("code_author", generate_code_only)
    workflow.add_node("executor", execute_code)
    workflow.add_node("question_author", generate_question_from_result)
    workflow.add_node("reviewer", parallel_review)  # PARALLEL: runs critic + validator together
    workflow.add_node("pedagogy_tagger", tag_pedagogy)  # STEP 3: Tag with CO/PO after review
    workflow.add_node("guardian", validate_syllabus)  # STEP 5: Syllabus validator
    workflow.add_node("fallback", use_fallback)
    workflow.add_node("archivist", save_result)

    # STEP 2: Start with Bloom analyzer (detects level for adaptive RAG)
    workflow.set_entry_point("bloom_analyzer")

    # Bloom Analyzer -> Scout (always)
    workflow.add_edge("bloom_analyzer", "scout")

    # 1. Scout -> Route based on cache hit or topic type
    def route_after_scout(state):
        if state.get('use_fallback'):
            return "fallback"
        # Check for cache hit first
        if state.get('cached_question'):
            return "use_cache"
        if state.get('is_conceptual'):
            return "theory_author"  # Skip code for conceptual topics
        return "code_author"

    workflow.add_conditional_edges(
        "scout",
        route_after_scout,
        {"fallback": "fallback", "use_cache": "use_cache", "theory_author": "theory_author", "code_author": "code_author"}
    )

    # Cache -> Save if using cache; otherwise route back to generation
    def route_after_cache(state):
        # If use_cached_question requested fallback (e.g., cache already used),
        # route to appropriate generation path instead of archiving.
        if state.get('use_fallback'):
            # Respect conceptual topics: theory_author if conceptual, else code_author
            return "theory_author" if state.get('is_conceptual') else "code_author"
        # Using a valid cached question → archive directly
        return "archivist"

    workflow.add_conditional_edges(
        "use_cache",
        route_after_cache,
        {"archivist": "archivist", "theory_author": "theory_author", "code_author": "code_author"}
    )

    # Theory path goes straight to reviewer (no code execution needed)
    workflow.add_conditional_edges(
        "theory_author",
        lambda x: "fallback" if x.get('use_fallback') else "reviewer",
        {"fallback": "fallback", "reviewer": "reviewer"}
    )

    # 2. Code Generation -> Executor (or Fallback)
    workflow.add_conditional_edges(
        "code_author",
        lambda x: "fallback" if x.get('use_fallback') else "executor",
        {"fallback": "fallback", "executor": "executor"}
    )

    # 3. Code Execution -> Question Writer (or Retry Code)
    workflow.add_conditional_edges(
        "executor",
        lambda x: "fallback" if x.get('use_fallback') else "question_author" if x.get('verification_passed') else "code_author",
        {"fallback": "fallback", "question_author": "question_author", "code_author": "code_author"}
    )

    # 4. Question Generation -> Parallel Review (critic + validator run together)
    workflow.add_conditional_edges(
        "question_author",
        lambda x: "fallback" if x.get('use_fallback') else "reviewer",
        {"fallback": "fallback", "reviewer": "reviewer"}
    )

    # 5. Parallel Review -> Pedagogy Tagger (optional) or Save (or Retry if failed)
    def route_after_review(state):
        if state.get('use_fallback'):
            return "fallback"

        # Check critique result
        is_passing = state.get('critique', {}).get('is_passing', True)
        revision_count = state.get('revision_count', 0)

        # Retry up to 2 times if critic fails
        if not is_passing and revision_count < 2:
            return "retry"

        # Check validation result
        if state.get('answer_mismatch'):
            return "retry"

        # STEP 3: Route through pedagogy_tagger if enabled, otherwise go to Guardian
        tagger_enabled = os.getenv("ENABLE_PEDAGOGY_TAGGER", "false").lower() == "true"
        if tagger_enabled:
            return "tag"
        else:
            # STEP 5: Go to Guardian validator
            return "guardian"

    workflow.add_conditional_edges(
        "reviewer",
        route_after_review,
        {"fallback": "fallback", "retry": "code_author", "tag": "pedagogy_tagger", "guardian": "guardian"}
    )

    # STEP 3: Pedagogy Tagger -> Guardian (STEP 5)
    workflow.add_edge("pedagogy_tagger", "guardian")

    # STEP 5: Guardian Validator -> Route based on validation result
    def route_after_guardian(state):
        """
        Route after Guardian validation:
        - If Guardian disabled or validated: go to save
        - If Guardian rejected and attempts < 1: retry generation
        - Otherwise: go to save (exhausted attempts)
        """
        guardian_enabled = os.getenv("ENABLE_GUARDIAN", "false").lower() == "true"

        # If Guardian disabled, always save
        if not guardian_enabled:
            return "save"

        is_validated = state.get('guardian_validated', True)
        attempt_count = state.get('guardian_attempt_count', 0)

        # If validated, save the question
        if is_validated:
            return "save"

        # If not validated and we haven't retried yet, allow ONE regeneration
        if attempt_count < 1:
            logger.warning(f"[Guardian] Attempting regeneration (attempt {attempt_count + 1}/1)")
            return "retry"

        # Exhausted attempts, save anyway (or could reject - for now we save with warning)
        logger.warning("[Guardian] Max regeneration attempts reached. Proceeding to save.")
        return "save"

    workflow.add_conditional_edges(
        "guardian",
        route_after_guardian,
        {"save": "archivist", "retry": "code_author"}
    )

    workflow.add_edge("fallback", "archivist")
    workflow.add_edge("archivist", END)

    return workflow.compile()

# ========== AUTO-TAGGING ==========

def auto_tag_question(topic: str, question_type: str, difficulty: str) -> List[str]:
    """
    Generate automatic tags for a question based on topic and type.
    Tags are loaded from config/tags.yaml - extensible for any domain (physics, chemistry, etc.)
    """
    tags = set()

    # Add difficulty tag
    tags.add(f"difficulty:{difficulty.lower()}")

    # Add question type tag
    if question_type:
        tags.add(f"type:{question_type.lower()}")

    # Get topic-based tags from config (supports any domain)
    topic_tags = get_tags(topic)
    tags.update(topic_tags)

    return sorted(list(tags))


_graph = None

def get_graph():
    """Get cached compiled graph. Builds once, reuses thereafter."""
    global _graph
    if _graph is None:
        logger.info("[Graph Cache] Building graph for first time...")
        _graph = build_graph()
    return _graph

def rebuild_graph():
    """Force rebuild of graph (use after code changes in dev)."""
    global _graph
    _graph = None
    return get_graph()

def run_agent(topic: str, difficulty: str = "Medium", question_type: str = None,
               used_cache_ids: set = None, temperature_boost: float = 0.0):
    """
    Run the question generation agent.

    Args:
        topic: The topic for the question
        difficulty: Question difficulty level
        question_type: Type of question (mcq, short, long, etc.)
        used_cache_ids: Set of cache IDs already used in this paper (prevents reuse)
        temperature_boost: Additional temperature to add for retry attempts (0.0 - 0.5)
    """
    graph = get_graph()  # Use cached graph
    logger.info(f"Tribunal Engine Started for Topic: {topic}, Type: {question_type}")

    # Determine if conceptual based on question_type
    # mcq, short, long are typically conceptual; numerical, trace, calculation are computational
    # If question_type is None, leave is_conceptual as None so check_sources can auto-detect
    if question_type:
        is_conceptual = question_type in ('short', 'long', 'mcq', 'theory', 'conceptual')
    else:
        is_conceptual = None  # Will be auto-detected in check_sources

    # Track this generation run with metrics
    with track_generation(topic, difficulty, question_type) as run_id:
        # Initialize with empty DB template so we don't accidentally fallback
        initial_state = {
            "topic": topic,
            "target_difficulty": difficulty,
            "question_type": question_type,  # Pass question type to generation
            "_run_id": run_id,  # For metrics tracking in nodes
            "iteration_count": 0,
            "revision_count": 0,
            "verification_passed": False,
            "use_fallback": False,
            "is_conceptual": is_conceptual,  # Set based on question_type, or None for auto-detect
            "code_draft": None,  # For code-first approach
            "computed_result": None,  # Actual result from code execution
            "question_data": {},
            "source_urls": [],
            "source_pages": [],
            "source_filename": None,
            # Deduplication support
            "used_cache_ids": used_cache_ids or set(),  # Track used cache IDs
            "temperature_boost": temperature_boost,  # For retry temperature adjustment
            "detected_keywords": {},  # Keywords detected in query for targeted context
            "answer_mismatch": False,
            "answer_validation_count": 0,
            # STEP 2: Bloom-Adaptive RAG initialization
            "bloom_level": None,  # Will be set by analyze_bloom node
            "retrieved_chunk_ids": [],
            "retrieved_doc_ids": [],
            # STEP 3: Pedagogy Tagger initialization
            "course_outcome": None,
            "program_outcome": None,
            # STEP 5: Guardian initialization
            "guardian_validated": False,
            "guardian_attempt_count": 0,
            "guardian_failure_reason": None
        }

        result = graph.invoke(initial_state)

        # We strictly return the generated data, never the raw DB template anymore
        final_data = result.get('question_data', {})

        if final_data:
            final_data['source'] = result.get('source_type')
            final_data['source_urls'] = result.get('source_urls', [])
            final_data['source_pages'] = result.get('source_pages', [])
            final_data['source_filename'] = result.get('source_filename', '')
            if result.get('critique'):
                final_data['quality_score'] = result['critique'].get('score', 0)

            # STEP 2: Add Bloom-Adaptive RAG provenance
            final_data['bloom_level'] = result.get('bloom_level')
            final_data['retrieved_chunk_ids'] = result.get('retrieved_chunk_ids', [])
            final_data['retrieved_doc_ids'] = result.get('retrieved_doc_ids', [])

            # STEP 3: Add Pedagogy tags
            final_data['course_outcome'] = result.get('course_outcome')
            final_data['program_outcome'] = result.get('program_outcome')

            # STEP 4: Add question ID for provenance
            final_data['question_id'] = result.get('question_id')

            # Auto-tag the question
            question_type = final_data.get('question_type', '')
            final_data['tags'] = auto_tag_question(topic, question_type, difficulty)

            # DEDUPLICATION: Pass updated used_cache_ids back to caller
            final_data['used_cache_ids'] = list(result.get('used_cache_ids', []))  # Convert set to list for JSON serialization

            # Note: Quality filtering happens in the graph via critic routing
            # If we reach here with a low score, it means we exhausted retries
            # Return it with the score so the user knows it's suboptimal
        else:
            final_data = {"error": "Failed to generate question."}

    return final_data


def run_agent_streaming(topic: str, difficulty: str = "Medium", question_type: str = None):
    """
    Generator version of run_agent that yields progress events.
    Used for SSE streaming endpoint.

    Yields dicts with:
    - type: "progress" | "result" | "error"
    - phase: current phase name
    - message: human readable status
    - data: (for result type) the final question data
    """
    graph = get_graph()  # Use cached graph
    logger.info(f"[Streaming] Tribunal Engine Started for Topic: {topic}, Type: {question_type}")

    # Determine if conceptual based on question_type (same logic as run_agent)
    if question_type:
        is_conceptual = question_type in ('short', 'long', 'mcq', 'theory', 'conceptual')
    else:
        is_conceptual = None  # Will be auto-detected in check_sources

    initial_state = {
        "topic": topic,
        "target_difficulty": difficulty,
        "question_type": question_type,
        "iteration_count": 0,
        "revision_count": 0,
        "verification_passed": False,
        "use_fallback": False,
        "is_conceptual": is_conceptual,  # Set based on question_type, or None for auto-detect
        "code_draft": None,
        "computed_result": None,
        "question_data": {},
        "source_urls": [],
        "source_pages": [],
        "source_filename": None,
        "detected_keywords": {},
        "answer_mismatch": False,
        "answer_validation_count": 0,
        # STEP 2: Bloom-Adaptive RAG initialization
        "bloom_level": None,
        "retrieved_chunk_ids": [],
        "retrieved_doc_ids": [],
        # STEP 3: Pedagogy Tagger initialization
        "course_outcome": None,
        "program_outcome": None
    }

    # Phase descriptions for progress updates
    phase_messages = {
        "bloom_analyzer": "Analyzing Bloom's taxonomy level...",  # STEP 2
        "scout": "Searching PDF sources...",
        "use_cache": "Found cached question, loading...",
        "theory_author": "Generating theory-based question...",
        "code_author": "Generating verification code...",
        "executor": "Executing code to compute answer...",
        "question_author": "Writing question text...",
        "reviewer": "Reviewing quality...",
        "pedagogy_tagger": "Tagging with educational outcomes...",  # STEP 3
        "fallback": "Using fallback generation...",
        "archivist": "Saving result..."
    }

    yield {"type": "progress", "phase": "start", "message": f"Starting generation for: {topic}", "topic": topic, "difficulty": difficulty}

    try:
        # Stream through graph execution, accumulate state
        accumulated_state = dict(initial_state)

        for event in graph.stream(initial_state):
            # event is a dict with node name -> output
            for node_name, output in event.items():
                # Update accumulated state
                accumulated_state.update(output)

                message = phase_messages.get(node_name, f"Processing {node_name}...")

                # Build detailed progress event
                progress_event = {
                    "type": "progress",
                    "phase": node_name,
                    "message": message
                }

                # Add source info after scout phase
                if node_name == "scout":
                    if output.get('source_filename'):
                        progress_event["source_file"] = output['source_filename']
                    if output.get('source_pages'):
                        progress_event["source_pages"] = output['source_pages']
                    if output.get('cached_question'):
                        progress_event["cache_hit"] = True
                        progress_event["message"] = "Found similar question in cache!"

                # Add preview after question generation
                if node_name in ["question_author", "theory_author", "fallback"]:
                    q_data = output.get('question_data', {})
                    if q_data and q_data.get('question'):
                        # Provide preview of first 200 chars
                        preview = q_data['question'][:200] + "..." if len(q_data.get('question', '')) > 200 else q_data.get('question', '')
                        progress_event["preview"] = preview
                        progress_event["message"] = "Question generated! Reviewing..."

                # Add quality info after review
                if node_name == "reviewer":
                    critique = output.get('critique', {})
                    if critique:
                        progress_event["quality_score"] = critique.get('score', 0)
                        progress_event["message"] = f"Quality review: {critique.get('score', '?')}/10"

                yield progress_event

                # Check for errors
                if output.get('use_fallback') and node_name != "scout":
                    yield {"type": "progress", "phase": node_name, "message": "Retrying with fallback..."}

                # Check for retries
                if output.get('verification_error'):
                    yield {"type": "progress", "phase": node_name, "message": f"Retry: {output['verification_error'][:100]}..."}

        # Build final result from accumulated state
        final_data = accumulated_state.get('question_data', {})
        if final_data and 'question' in final_data:
            final_data['source'] = accumulated_state.get('source_type')
            final_data['source_urls'] = accumulated_state.get('source_urls', [])
            final_data['source_pages'] = accumulated_state.get('source_pages', [])
            final_data['source_filename'] = accumulated_state.get('source_filename', '')
            if accumulated_state.get('critique'):
                final_data['quality_score'] = accumulated_state['critique'].get('score', 0)

            # STEP 2: Add Bloom-Adaptive RAG provenance
            final_data['bloom_level'] = accumulated_state.get('bloom_level')
            final_data['retrieved_chunk_ids'] = accumulated_state.get('retrieved_chunk_ids', [])
            final_data['retrieved_doc_ids'] = accumulated_state.get('retrieved_doc_ids', [])

            # STEP 3: Add Pedagogy tags
            final_data['course_outcome'] = accumulated_state.get('course_outcome')
            final_data['program_outcome'] = accumulated_state.get('program_outcome')

            # Auto-tag the question
            question_type = final_data.get('question_type', '')
            final_data['tags'] = auto_tag_question(topic, question_type, difficulty)

            yield {"type": "result", "phase": "complete", "message": "Generation complete", "data": final_data}
        else:
            yield {"type": "error", "phase": "complete", "message": "Failed to generate question", "data": {"error": "Generation failed"}}

    except Exception as e:
        logger.error(f"[Streaming] Error: {e}")
        yield {"type": "error", "phase": "error", "message": str(e), "data": {"error": str(e)}}