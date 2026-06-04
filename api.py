"""
Module: api.py
Purpose: FastAPI endpoints for exam generation.
"""

import os
import sys
import warnings
import logging

# --- NUCLEAR WARNING SUPPRESSION ---
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

warnings.simplefilter("ignore")
warnings.filterwarnings("ignore")
sys.warnoptions = []

for category in [DeprecationWarning, UserWarning, ResourceWarning, FutureWarning,
                 PendingDeprecationWarning, ImportWarning, RuntimeWarning]:
    warnings.filterwarnings("ignore", category=category)

for pattern in [".*PydanticDeprecated.*", ".*model_fields.*", ".*pydantic.*",
                ".*langchain.*", ".*deprecated.*"]:
    warnings.filterwarnings("ignore", message=pattern)

warnings.showwarning = lambda *a, **k: None
warnings.warn = lambda *a, **k: None

for logger_name in ["transformers", "sentence_transformers", "chromadb",
                    "langchain", "langchain_core", "langchain_community",
                    "langchain_openai", "pydantic"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)
    logging.getLogger(logger_name).propagate = False

import time
import json
import asyncio
from typing import Dict, Any, AsyncGenerator, List
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.services.rag_service import get_rag_service
from app.services.graph_agent import run_agent, run_agent_streaming
from app.services.paper_generator import get_paper_service, PaperTemplate, PaperSection, QuestionSpec, QuestionPart
from app.services.metrics import get_metrics
from app.config import reload_config
from app.tools.utils import get_logger, initialize_logging

load_dotenv()
initialize_logging()
logger = get_logger("FastAPI")

app = FastAPI(title="HQGE - Enterprise Exam Engine", version="5.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

class GenerateQuestionRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    difficulty: str = Field(default="Medium")
    question_type: str = Field(default=None, description="Question type: mcq, short, long, calculation, trace")


class BatchGenerateRequest(BaseModel):
    """Request for batch question generation"""
    questions: list[GenerateQuestionRequest] = Field(..., min_length=1, max_length=5)


@app.post("/api/v1/generate")
async def generate_question(request: GenerateQuestionRequest):
    try:
        start_time = time.time()
        result = run_agent(request.topic, request.difficulty, request.question_type)
        duration = round(time.time() - start_time, 2)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "status": "success",
            "data": result,
            "meta": {"duration_seconds": duration, "engine": "Tribunal"}
        }
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def stream_generator(topic: str, difficulty: str, question_type: str = None) -> AsyncGenerator[str, None]:
    """Async generator for SSE streaming - true real-time streaming"""
    import queue
    import threading

    event_queue = queue.Queue()
    done = threading.Event()

    def run_sync():
        """Run the sync generator in a thread, putting events in queue"""
        try:
            for event in run_agent_streaming(topic, difficulty, question_type):
                # Add timestamp and progress percentage
                event['timestamp'] = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0

                # Estimate progress percentage based on phase
                phase_progress = {
                    "start": 5,
                    "scout": 15,
                    "use_cache": 20,
                    "theory_author": 50,
                    "code_author": 30,
                    "executor": 45,
                    "question_author": 60,
                    "reviewer": 80,
                    "fallback": 70,
                    "archivist": 95,
                    "complete": 100,
                    "error": 100
                }
                event['progress'] = phase_progress.get(event.get('phase', ''), 50)

                # Add preview data if available
                if event.get('type') == 'progress' and event.get('phase') == 'question_author':
                    event['message'] = "Writing question text... (preview coming soon)"

                event_queue.put(event)
        except Exception as e:
            event_queue.put({"type": "error", "phase": "error", "message": str(e), "progress": 100})
        finally:
            done.set()

    # Start the sync generator in a thread
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

    # Stream events as they arrive
    while not done.is_set() or not event_queue.empty():
        try:
            event = event_queue.get(timeout=0.1)
            yield f"data: {json.dumps(event)}\n\n"
        except queue.Empty:
            # Send heartbeat to keep connection alive
            yield f": heartbeat\n\n"
        await asyncio.sleep(0.05)  # Small delay for responsiveness

    # Final event
    yield f"data: {json.dumps({'type': 'done', 'phase': 'end', 'message': 'Stream ended', 'progress': 100})}\n\n"


@app.get("/api/v1/generate/stream")
async def generate_question_stream(topic: str, difficulty: str = "Medium", question_type: str = None):
    """
    SSE endpoint for real-time question generation progress.

    Usage: EventSource('/api/v1/generate/stream?topic=DFS&difficulty=Medium&question_type=long')

    Events:
    - type: "progress" - Generation phase updates
    - type: "result" - Final generated question
    - type: "error" - Error occurred
    """
    if len(topic) < 3:
        raise HTTPException(status_code=400, detail="Topic must be at least 3 characters")

    return StreamingResponse(
        stream_generator(topic, difficulty, question_type),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/v1/generate/batch")
async def generate_questions_batch(request: BatchGenerateRequest):
    """
    Generate multiple questions in parallel (up to 5).

    Example request:
    {
        "questions": [
            {"topic": "DFS algorithm", "difficulty": "Medium"},
            {"topic": "Gini index calculation", "difficulty": "Hard"},
            {"topic": "Entropy", "difficulty": "Easy"}
        ]
    }
    """
    import concurrent.futures

    start_time = time.time()
    results = []
    errors = []

    def generate_single(idx: int, req: GenerateQuestionRequest):
        """Generate a single question with index tracking"""
        try:
            result = run_agent(req.topic, req.difficulty, req.question_type)
            return {"index": idx, "topic": req.topic, "difficulty": req.difficulty, "data": result, "error": None}
        except Exception as e:
            return {"index": idx, "topic": req.topic, "difficulty": req.difficulty, "data": None, "error": str(e)}

    # Run up to 5 questions in parallel using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(generate_single, i, q): i
            for i, q in enumerate(request.questions)
        }

        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result["error"]:
                    errors.append(result)
                else:
                    results.append(result)
            except Exception as e:
                idx = futures[future]
                errors.append({"index": idx, "error": str(e)})

    # Sort by original index
    results.sort(key=lambda x: x["index"])
    errors.sort(key=lambda x: x["index"])

    duration = round(time.time() - start_time, 2)

    return {
        "status": "success" if not errors else "partial",
        "results": results,
        "errors": errors,
        "meta": {
            "total_requested": len(request.questions),
            "successful": len(results),
            "failed": len(errors),
            "duration_seconds": duration
        }
    }

@app.post("/api/v1/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    file_path = UPLOAD_DIR / file.filename
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        rag = get_rag_service()
        stats = rag.ingest_file(str(file_path))

        return {"filename": file.filename, "status": "uploaded", "ingestion": stats}
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/suggestions")
async def get_suggestions():
    """Get intelligent topic suggestions extracted from uploaded PDF content"""
    try:
        from app.rag import DocumentRegistry
        registry = DocumentRegistry()
        ingested_docs = registry.get_ingested_documents()

        # Check what PDFs actually exist in uploads folder
        existing_pdfs = list(UPLOAD_DIR.glob("*.pdf"))

        logger.info(f"[Suggestions] Found {len(existing_pdfs)} PDFs, {len(ingested_docs)} ingested docs")

        if not existing_pdfs:
            logger.warning("[Suggestions] No PDFs found in uploads folder")
            return {"suggestions": [], "message": "No PDFs uploaded yet"}

        suggestions = []
        seen = set()

        # 1. Extract topics from PDF filenames
        for pdf_file in existing_pdfs:
            filename = pdf_file.stem
            topic = filename.replace('_', ' ').replace('-', ' ')
            for remove in ['lecture', 'chapter', 'notes', 'slides', 'pdf']:
                topic = topic.lower().replace(remove, '').strip()
            topic = ' '.join(topic.split())
            if topic and len(topic) > 2 and topic.lower() not in seen:
                seen.add(topic.lower())
                suggestions.append({"topic": topic.title(), "examples": []})
                logger.debug(f"[Suggestions] Added from filename: {topic.title()}")

        # 2. Search PDF content with diverse queries to find more topics
        if ingested_docs:
            logger.info(f"[Suggestions] Searching content in {len(ingested_docs)} docs")
            try:
                rag = get_rag_service()
                logger.info(f"[Suggestions] RAG service initialized: {rag is not None}")
            except Exception as rag_init_err:
                logger.error(f"[Suggestions] RAG service initialization failed: {rag_init_err}")
                rag = None
            
            all_content = ""
            
            if rag:
                try:
                    # Multiple search queries to find diverse topics
                    search_queries = [
                        "algorithm",
                        "definition",
                        "formula",
                        "example",
                        "method",
                        "process",
                        "technique"
                    ]

                    for query in search_queries:
                        try:
                            result = rag.search(query, k=3)
                            if result and isinstance(result, str) and len(result) > 50:
                                all_content += " " + result
                                logger.info(f"[Suggestions] Found {len(result)} chars for query: {query}")
                            else:
                                logger.debug(f"[Suggestions] Empty/short result for query: {query}")
                        except Exception as search_err:
                            logger.warning(f"[Suggestions] Search failed for '{query}': {search_err}")
                            continue
                except Exception as search_loop_err:
                    logger.error(f"[Suggestions] Search loop failed: {search_loop_err}")

            logger.info(f"[Suggestions] Extracted {len(all_content)} chars of content")
            
            # Fallback: Try direct ChromaDB query if RAG search failed
            if not all_content or len(all_content) < 100:
                logger.warning("[Suggestions] RAG search returned insufficient content, trying direct ChromaDB query")
                try:
                    from app.rag import get_rag_engine
                    rag_engine = get_rag_engine()
                    # Get some sample documents
                    sample_result = rag_engine.query_knowledge_base("topics concepts", k=10)
                    if sample_result and sample_result.context:
                        all_content = sample_result.context
                        logger.info(f"[Suggestions] Direct ChromaDB query returned {len(all_content)} chars")
                except Exception as direct_err:
                    logger.error(f"[Suggestions] Direct ChromaDB query also failed: {direct_err}")

            if all_content and len(all_content) > 100:
                try:
                    text = all_content.lower()
                    
                    import re

                    # Expanded and organized list of potential topics to look for
                    potential_topics = [
                        # ML/AI Core
                        "machine learning", "artificial intelligence", "deep learning",
                        "supervised learning", "unsupervised learning", "reinforcement learning",
                        # Decision Trees
                        "decision tree", "random forest", "id3 algorithm", "c4.5 algorithm", "cart",
                        "entropy", "gini index", "information gain", "gain ratio", "pruning",
                        # Classification
                        "classification", "naive bayes", "svm", "support vector machine",
                        "knn", "k-nearest neighbors", "logistic regression",
                        # Neural Networks
                        "neural network", "perceptron", "backpropagation", "mlp",
                        "activation function", "loss function", "gradient descent",
                        "cnn", "convolutional", "rnn", "recurrent", "lstm", "transformer",
                        # Clustering
                        "clustering", "k-means", "hierarchical clustering", "dbscan",
                        # Model Evaluation
                        "cross validation", "confusion matrix", "accuracy", "precision", "recall",
                        "overfitting", "underfitting", "regularization", "bias variance",
                        # Ensemble
                        "ensemble", "bagging", "boosting", "adaboost", "gradient boosting",
                        # Features
                        "feature selection", "dimensionality reduction", "pca",
                        "normalization", "standardization",
                        # AI/Agents
                        "rational agent", "intelligent agent", "reflex agent", "peas",
                        "search algorithm", "uninformed search", "informed search",
                        "heuristic", "a* algorithm", "minimax", "alpha beta pruning",
                        "constraint satisfaction", "game tree", "adversarial search",
                        # Search
                        "breadth first search", "bfs", "depth first search", "dfs",
                        "uniform cost search", "greedy best first", "hill climbing",
                        # Algorithms
                        "dynamic programming", "greedy algorithm", "divide and conquer",
                        "sorting algorithm", "binary search", "graph algorithm",
                        "time complexity", "space complexity", "big o notation",
                        # Stats
                        "probability", "bayes theorem", "conditional probability",
                        "hypothesis testing", "confidence interval", "correlation"
                    ]

                    logger.info(f"[Suggestions] Searching {len(potential_topics)} topics in {len(text)} chars")
                    
                    for term in potential_topics:
                        # Use word boundary regex for better matching
                        pattern = r'\b' + re.escape(term) + r'\b'
                        if re.search(pattern, text) and term.lower() not in seen:
                            seen.add(term.lower())
                            # Generate example question types
                            examples = []
                            if "tree" in term or "algorithm" in term:
                                examples = [f"{term} trace", f"{term} complexity"]
                            elif "function" in term or "formula" in term:
                                examples = [f"{term} calculation", f"{term} derivation"]
                            else:
                                examples = [f"{term} definition", f"{term} example"]

                            suggestions.append({
                                "topic": term.title(),
                                "examples": examples
                            })

                        if len(suggestions) >= 20:
                            break

                except Exception as e:
                    logger.warning(f"[Suggestions] Could not extract topics from content: {e}")

        # Sort suggestions: filename-based first, then alphabetically
        suggestions.sort(key=lambda x: (0 if x['examples'] == [] else 1, x['topic']))

        final_suggestions = suggestions[:15]
        logger.info(f"[Suggestions] Returning {len(final_suggestions)} suggestions")
        
        return {"suggestions": final_suggestions}
    except Exception as e:
        logger.error(f"[Suggestions] Failed to get suggestions: {e}")
        import traceback
        logger.error(f"[Suggestions] Traceback: {traceback.format_exc()}")
        # Return empty array instead of error to keep UI working
        return {"suggestions": [], "error": str(e)}

@app.get("/api/v1/suggestions-by-pdf")
async def get_suggestions_by_pdf():
    """Get topic suggestions grouped by PDF using syllabus-based matching"""
    try:
        from app.rag import DocumentRegistry, get_rag_engine
        from app.config.syllabus_loader import get_syllabus_loader
        from langchain_openai import ChatOpenAI
        import json
        
        registry = DocumentRegistry()
        ingested_docs = registry.get_ingested_documents()
        existing_pdfs = list(UPLOAD_DIR.glob("*.pdf"))
        syllabus = get_syllabus_loader()

        logger.info(f"[Suggestions By PDF] Found {len(existing_pdfs)} PDFs")

        if not existing_pdfs:
            return {"pdf_suggestions": [], "message": "No PDFs uploaded yet"}

        pdf_suggestions = []
        rag_engine = get_rag_engine()
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        for pdf_file in existing_pdfs:
            filename = pdf_file.name
            suggestions = []

            try:
                # Determine which unit this PDF belongs to
                unit_number = syllabus.match_unit_for_pdf(filename)
                
                if not unit_number:
                    logger.warning(f"[Suggestions By PDF] Could not match {filename} to any unit")
                    pdf_suggestions.append({
                        "filename": filename,
                        "unit_name": "Unknown Unit",
                        "suggestions": [],
                        "count": 0
                    })
                    continue

                unit = syllabus.get_unit_by_number(unit_number)
                unit_name = unit.get('unit_name', f'Unit {unit_number}')
                
                # Get PDF content
                result = rag_engine.query_by_pdf(filename, k=20)
                
                if not result or not result.context or len(result.context) < 200:
                    logger.warning(f"[Suggestions By PDF] Insufficient content from {filename}")
                    pdf_suggestions.append({
                        "filename": filename,
                        "unit_name": unit_name,
                        "suggestions": [],
                        "count": 0
                    })
                    continue

                # Get syllabus topics for this unit
                unit_topics = syllabus.get_unit_topics(unit_number)
                co_mapping = syllabus.get_co_mapping(unit_number)
                bloom_levels = syllabus.get_bloom_levels(unit_number)

                logger.info(f"[Suggestions By PDF] Unit {unit_number}: {len(unit_topics)} syllabus topics")

                # Build topic list from syllabus
                topic_list = []
                for topic in unit_topics:
                    topic_list.append(f"- {topic['name']}")
                    for subtopic in topic.get('subtopics', []):
                        topic_list.append(f"  - {subtopic}")
                
                syllabus_topics_str = "\n".join(topic_list)

                # Use LLM to match PDF content with syllabus topics
                extraction_prompt = f"""You are analyzing course material for Unit {unit_number}: {unit_name}.

SYLLABUS TOPICS FOR THIS UNIT:
{syllabus_topics_str}

PDF CONTENT (first 7000 chars):
{result.context[:7000]}

Task: From the SYLLABUS TOPICS above, identify which topics are ACTUALLY covered in the PDF content. Return the most important topics and subtopics that have substantial content in the PDF.

Return ONLY a JSON array with 10-15 topic objects:
[
  {{"topic": "Exact Topic Name from Syllabus", "examples": ["specific concept from PDF", "another concept"]}},
  ...
]

Rules:
- Use EXACT topic/subtopic names from the syllabus
- Only include topics with actual content in the PDF
- Examples should be specific terms/concepts found in the PDF
- Prioritize main topics over subtopics
- Return valid JSON only, no markdown"""

                response = llm.invoke(extraction_prompt)
                content = response.content.strip()
                
                # Remove markdown code blocks
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()
                
                # Parse JSON
                try:
                    topics_data = json.loads(content)
                    if isinstance(topics_data, list):
                        suggestions = topics_data[:15]
                        logger.info(f"[Suggestions By PDF] Unit {unit_number}: {len(suggestions)} topics matched")
                    else:
                        suggestions = []
                except json.JSONDecodeError as je:
                    logger.error(f"[Suggestions By PDF] JSON parse error: {je}")
                    suggestions = []

            except Exception as e:
                logger.error(f"[Suggestions By PDF] Failed for {filename}: {e}", exc_info=True)
                unit_name = "Unknown Unit"

            pdf_suggestions.append({
                "filename": filename,
                "unit_name": unit_name,
                "unit_number": unit_number if unit_number else 0,
                "suggestions": suggestions,
                "count": len(suggestions),
                "co_mapping": co_mapping if unit_number else [],
                "bloom_levels": bloom_levels if unit_number else []
            })

        total_topics = sum(pdf['count'] for pdf in pdf_suggestions)
        logger.info(f"[Suggestions By PDF] Total: {total_topics} topics across {len(pdf_suggestions)} PDFs")
        
        return {"pdf_suggestions": pdf_suggestions}

    except Exception as e:
        logger.error(f"[Suggestions By PDF] Error: {e}", exc_info=True)
        return {"pdf_suggestions": [], "error": str(e)}

@app.get("/api/v1/bloom-levels")
async def get_bloom_levels():
    """Get available Bloom's taxonomy cognitive levels for question generation"""
    from app.services.paper_generator import BLOOMS_TAXONOMY
    levels = []
    for key, data in BLOOMS_TAXONOMY.items():
        levels.append({
            "id": key,
            "name": key.capitalize(),
            "level": data["level"],
            "description": data["description"],
            "example_verbs": data["verbs"][:4]
        })
    # Sort by level
    levels.sort(key=lambda x: x["level"])
    return {"levels": levels}

@app.get("/api/v1/knowledge-hub/syllabus")
async def get_syllabus_info():
    """Get complete syllabus information for display in Knowledge Hub"""
    try:
        from app.config.syllabus_loader import get_syllabus_loader
        
        syllabus = get_syllabus_loader()
        course_info = syllabus.get_course_info()
        units = syllabus.get_all_units()
        
        return {
            "course_info": course_info,
            "units": units,
            "course_outcomes": syllabus.syllabus_data.get('course_outcomes', {}),
            "co_po_mapping": syllabus.syllabus_data.get('co_po_mapping', {}),
            "total_units": len(units),
            "credits": syllabus.syllabus_data.get('credits', {})
        }
    except Exception as e:
        logger.error(f"Failed to get syllabus: {e}")
        return {"error": str(e), "units": []}

@app.get("/api/v1/knowledge-hub/pyq-papers")
async def get_pyq_papers():
    """Get list of previous year question papers with statistics"""
    try:
        from app.config.pyq_analyzer import get_pyq_analyzer
        import json
        from pathlib import Path
        
        analyzer = get_pyq_analyzer()
        pyq_dir = Path(__file__).parent / "data" / "previous_year_papers"
        
        papers = []
        if pyq_dir.exists():
            for json_file in pyq_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        paper = json.load(f)
                        
                        # Calculate statistics
                        total_questions = len(paper.get('questions', []))
                        total_marks = sum(q.get('marks', 0) for q in paper.get('questions', []))
                        
                        # Count by question type
                        type_distribution = {}
                        difficulty_distribution = {}
                        co_distribution = {}
                        
                        for q in paper.get('questions', []):
                            q_type = q.get('question_type', 'unknown')
                            type_distribution[q_type] = type_distribution.get(q_type, 0) + 1
                            
                            diff = q.get('difficulty', 'Unknown')
                            difficulty_distribution[diff] = difficulty_distribution.get(diff, 0) + 1
                            
                            for co in q.get('co_mapping', []):
                                co_distribution[co] = co_distribution.get(co, 0) + 1
                        
                        papers.append({
                            "filename": json_file.name,
                            "exam_name": paper.get('exam_name', 'Unknown Exam'),
                            "academic_year": paper.get('academic_year', 'N/A'),
                            "semester": paper.get('semester', 'N/A'),
                            "total_questions": total_questions,
                            "total_marks": total_marks,
                            "duration_minutes": paper.get('duration_minutes', 0),
                            "type_distribution": type_distribution,
                            "difficulty_distribution": difficulty_distribution,
                            "co_distribution": co_distribution
                        })
                except Exception as e:
                    logger.error(f"Failed to load {json_file}: {e}")
        
        # Add analyzer patterns summary
        patterns_summary = {
            "total_papers_analyzed": analyzer.patterns['total_papers'],
            "total_questions_analyzed": analyzer.patterns['total_questions'],
            "co_patterns": {}
        }
        
        # Summarize CO patterns
        for co, data in analyzer.patterns['by_co'].items():
            patterns_summary['co_patterns'][co] = {
                "question_types": dict(data['question_types']),
                "marks_distribution": dict(data['marks_distribution'])
            }
        
        return {
            "papers": papers,
            "patterns_summary": patterns_summary,
            "total_papers": len(papers)
        }
    except Exception as e:
        logger.error(f"Failed to get PYQ papers: {e}")
        return {"papers": [], "error": str(e)}


@app.post("/api/v1/context")
async def get_pdf_context(request: Dict[str, Any]):
    """Get PDF context for a topic (similar to CLI --show-context)"""
    try:
        topic = request.get("topic", "")
        if not topic:
            raise HTTPException(status_code=400, detail="Topic is required")

        rag = get_rag_service()
        context = rag.search(topic, k=5)

        if not context:
            return {"topic": topic, "context": None, "message": "No context found"}

        return {"topic": topic, "context": context, "chunks": 5}
    except Exception as e:
        logger.error(f"Failed to get context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/documents")
async def get_documents():
    """Get list of uploaded/ingested documents - only files that exist in uploads folder"""
    try:
        from app.rag import DocumentRegistry
        registry = DocumentRegistry()
        ingested_docs = registry.get_ingested_documents()

        # Build lookup from registry (deduplicate by filename, keep latest)
        registry_lookup = {}
        for doc in ingested_docs:
            # Handle both Windows and Unix paths
            filename = os.path.basename(doc['path'])
            registry_lookup[filename] = doc
            logger.debug(f"[Documents] Registry entry: {filename} -> {doc.get('chunks', 0)} chunks")

        # Only show files that actually exist in uploads folder
        documents = []
        seen = set()
        for pdf_file in UPLOAD_DIR.glob("*.pdf"):
            filename = pdf_file.name
            if filename in seen:
                continue
            seen.add(filename)

            # Get metadata from registry if available
            reg_info = registry_lookup.get(filename, {})
            chunk_count = int(reg_info.get('chunks', 0))
            logger.debug(f"[Documents] {filename} -> {chunk_count} chunks")
            documents.append({
                'filename': filename,
                'path': str(pdf_file),
                'chunks': chunk_count,
                'hash': reg_info.get('hash', '')[:12]
            })

        return {"documents": documents, "count": len(documents)}
    except Exception as e:
        logger.error(f"Failed to get documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== PAPER GENERATION ENDPOINTS ==========

class QuestionPartRequest(BaseModel):
    part_label: str = "a"
    description: str = ""
    marks: int = 2

class QuestionSpecRequest(BaseModel):
    topic: str
    question_type: str = "calculation"  # trace, pseudo-code, calculation, theory, mcq
    marks: int = 5  # Frontend sends 'marks', we use this directly
    difficulty: str = "Medium"
    parts: list[QuestionPartRequest] = []
    count: int = 1  # How many questions to generate for this spec
    keywords: list[str] = []
    bloom_level: str = ""  # Bloom's taxonomy: remember, understand, apply, analyze, evaluate, create

    @property
    def total_marks(self) -> int:
        """Alias for backwards compatibility"""
        return self.marks

class PaperSectionRequest(BaseModel):
    name: str = "Section A"
    title: str = "Questions"
    instructions: str = "Answer all questions"
    questions: list[QuestionSpecRequest] = []

class PaperTemplateRequest(BaseModel):
    name: str = "Untitled Paper"
    subject: str = ""
    duration_minutes: int = 180
    total_marks: int = 100
    instructions: list[str] = []
    sections: list[PaperSectionRequest] = []

@app.post("/api/v1/paper/template")
async def create_paper_template(request: PaperTemplateRequest):
    """Create or update a paper template"""
    try:
        service = get_paper_service()

        # Convert request to dataclasses
        sections = []
        for s in request.sections:
            questions = []
            for q in s.questions:
                parts = [QuestionPart(p.part_label, p.description, p.marks) for p in q.parts]
                questions.append(QuestionSpec(
                    topic=q.topic,
                    question_type=q.question_type,
                    total_marks=q.total_marks,
                    difficulty=q.difficulty,
                    parts=parts,
                    count=q.count,
                    keywords=q.keywords,
                    bloom_level=q.bloom_level
                ))
            sections.append(PaperSection(
                name=s.name,
                title=s.title,
                instructions=s.instructions,
                questions=questions
            ))

        template = PaperTemplate(
            name=request.name,
            subject=request.subject,
            duration_minutes=request.duration_minutes,
            total_marks=request.total_marks,
            instructions=request.instructions,
            sections=sections
        )

        template_id = service.save_template(template)
        return {"status": "success", "paper_id": template_id, "template_id": template_id, "template": template.to_dict()}
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/paper/templates")
async def list_paper_templates():
    """List all paper templates"""
    try:
        service = get_paper_service()
        templates = service.list_templates()
        return {"templates": templates, "count": len(templates)}
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/paper/template/{template_id}")
async def get_paper_template(template_id: str):
    """Get a specific paper template"""
    try:
        service = get_paper_service()
        template = service.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"template": template.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/paper/template/{template_id}")
async def delete_paper_template(template_id: str):
    """Delete a paper template"""
    try:
        service = get_paper_service()
        if service.delete_template(template_id):
            return {"status": "success", "message": "Template deleted"}
        raise HTTPException(status_code=404, detail="Template not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _format_paper_for_frontend(paper_dict: dict) -> dict:
    """Map backend paper fields to frontend expected format"""
    return {
        'paper_id': paper_dict.get('id', ''),
        'title': paper_dict.get('template_name', 'Untitled Paper'),
        'subject': paper_dict.get('subject', ''),
        'duration_minutes': paper_dict.get('duration_minutes', 180),
        'total_marks': paper_dict.get('total_marks', 0),
        'instructions': paper_dict.get('instructions', []),
        'sections': paper_dict.get('sections', []),
        'generated_at': paper_dict.get('generated_at', ''),
        'stats': paper_dict.get('generation_stats', {})
    }

@app.post("/api/v1/paper/generate/{template_id}")
async def generate_paper(template_id: str):
    """Generate a question paper from a template"""
    try:
        service = get_paper_service()
        start_time = time.time()

        paper = service.generate_paper(template_id, parallel=True)

        duration = round(time.time() - start_time, 2)
        return {
            "status": "success",
            "paper": _format_paper_for_frontend(paper.to_dict()),
            "generation_time_seconds": duration
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate paper: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def paper_stream_generator(template_id: str) -> AsyncGenerator[str, None]:
    """Async generator for SSE streaming of paper generation progress"""
    import queue
    import threading

    event_queue = queue.Queue()
    done = threading.Event()
    paper_result = [None]  # Use list to allow mutation in thread

    def run_generation():
        """Run paper generation in a thread, sending progress events"""
        try:
            service = get_paper_service()
            template = service.get_template(template_id)

            if not template:
                event_queue.put({
                    "type": "error",
                    "message": "Template not found",
                    "progress": 100
                })
                return

            # Send initial event
            total_questions = sum(
                sum(q.count for q in section.questions)
                for section in template.sections
            )
            event_queue.put({
                "type": "start",
                "message": f"Starting paper generation: {template.name}",
                "total_questions": total_questions,
                "progress": 5
            })

            # Generate questions one by one with progress
            from app.services.graph_agent import run_agent
            from app.services.paper_generator import GeneratedPaper
            import datetime

            generated_sections = []
            questions_completed = 0
            question_number = 1

            for section_idx, section in enumerate(template.sections):
                event_queue.put({
                    "type": "section_start",
                    "message": f"Starting {section.name}",
                    "section_index": section_idx,
                    "section_name": section.name,
                    "progress": int(10 + (questions_completed / max(total_questions, 1)) * 80)
                })

                generated_questions = []

                for spec_idx, spec in enumerate(section.questions):
                    for i in range(spec.count):
                        # Send progress event for this question
                        event_queue.put({
                            "type": "question_start",
                            "message": f"Generating Q{question_number}: {spec.topic}",
                            "topic": spec.topic,
                            "difficulty": spec.difficulty,
                            "question_number": question_number,
                            "progress": int(10 + (questions_completed / max(total_questions, 1)) * 80)
                        })

                        # Generate the question
                        try:
                            result = run_agent(spec.topic, spec.difficulty, spec.question_type)
                            question_text = result.get('question', result.get('question_text', ''))
                            answer = result.get('answer', '')
                            explanation = result.get('explanation', '')

                            gen_q = {
                                "question_number": question_number,
                                "part_of_section": section.name,
                                "topic": spec.topic,
                                "question_type": spec.question_type,
                                "difficulty": spec.difficulty,
                                "marks": spec.total_marks,
                                "parts_marks": [],
                                "question_text": question_text,
                                "answer": answer,
                                "explanation": explanation,
                                "verification_code": result.get('python_code', ''),
                                "from_cache": result.get('from_cache', False)
                            }
                            generated_questions.append(gen_q)

                            # Send completion event with preview
                            preview = question_text[:100] + "..." if len(question_text) > 100 else question_text
                            event_queue.put({
                                "type": "question_complete",
                                "message": f"Completed Q{question_number}: {spec.topic}",
                                "question_number": question_number,
                                "preview": preview,
                                "from_cache": result.get('from_cache', False),
                                "progress": int(10 + ((questions_completed + 1) / max(total_questions, 1)) * 80)
                            })

                        except Exception as e:
                            event_queue.put({
                                "type": "question_error",
                                "message": f"Error generating Q{question_number}: {str(e)[:50]}",
                                "question_number": question_number,
                                "error": str(e),
                                "progress": int(10 + ((questions_completed + 1) / max(total_questions, 1)) * 80)
                            })
                            # Create placeholder question on error
                            gen_q = {
                                "question_number": question_number,
                                "part_of_section": section.name,
                                "topic": spec.topic,
                                "question_type": spec.question_type,
                                "difficulty": spec.difficulty,
                                "marks": spec.total_marks,
                                "parts_marks": [],
                                "question_text": f"[Error generating question on {spec.topic}]",
                                "answer": "",
                                "explanation": "",
                                "verification_code": ""
                            }
                            generated_questions.append(gen_q)

                        questions_completed += 1
                        question_number += 1

                # Create section as dict (not dataclass)
                gen_section = {
                    "name": section.name,
                    "title": section.title,
                    "instructions": section.instructions,
                    "questions": generated_questions
                }
                generated_sections.append(gen_section)

                event_queue.put({
                    "type": "section_complete",
                    "message": f"Completed {section.name}",
                    "section_index": section_idx,
                    "questions_in_section": len(generated_questions),
                    "progress": int(10 + (questions_completed / max(total_questions, 1)) * 80)
                })

            # Create final paper
            event_queue.put({
                "type": "finalizing",
                "message": "Finalizing paper...",
                "progress": 95
            })

            paper = GeneratedPaper(
                id=template_id,
                template_id=template_id,
                template_name=template.name,
                subject=template.subject,
                duration_minutes=template.duration_minutes,
                total_marks=template.total_marks,
                instructions=template.instructions,
                sections=generated_sections,
                generated_at=datetime.datetime.now().isoformat()
            )

            # Save the paper
            service._save_paper(paper)
            paper_result[0] = paper

            event_queue.put({
                "type": "complete",
                "message": "Paper generation complete!",
                "paper_id": paper.id,
                "total_questions": questions_completed,
                "progress": 100
            })

        except Exception as e:
            event_queue.put({
                "type": "error",
                "message": f"Generation failed: {str(e)}",
                "error": str(e),
                "progress": 100
            })
        finally:
            done.set()

    # Start generation in a thread
    thread = threading.Thread(target=run_generation, daemon=True)
    thread.start()

    # Stream events as they arrive
    while not done.is_set() or not event_queue.empty():
        try:
            event = event_queue.get(timeout=0.1)
            yield f"data: {json.dumps(event)}\n\n"
        except queue.Empty:
            # Send heartbeat to keep connection alive
            yield f": heartbeat\n\n"
        await asyncio.sleep(0.05)

    # Send final result if available
    if paper_result[0]:
        final_event = {
            "type": "result",
            "paper": _format_paper_for_frontend(paper_result[0].to_dict()),
            "progress": 100
        }
        yield f"data: {json.dumps(final_event)}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'message': 'Stream ended'})}\n\n"


@app.get("/api/v1/paper/generate/{template_id}/stream")
async def generate_paper_stream(template_id: str):
    """
    SSE endpoint for real-time paper generation progress.

    Usage: EventSource('/api/v1/paper/generate/{template_id}/stream')

    Events:
    - type: "start" - Generation started with total_questions count
    - type: "section_start" - Starting a new section
    - type: "question_start" - Starting to generate a question
    - type: "question_complete" - Question generated with preview
    - type: "question_error" - Error generating question
    - type: "section_complete" - Section completed
    - type: "finalizing" - Creating final paper
    - type: "complete" - Generation complete with paper_id
    - type: "result" - Final paper data
    - type: "error" - Error occurred
    """
    return StreamingResponse(
        paper_stream_generator(template_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/v1/paper/papers")
async def list_generated_papers():
    """List all generated papers"""
    try:
        service = get_paper_service()
        papers = service.list_papers()
        return {"papers": papers, "count": len(papers)}
    except Exception as e:
        logger.error(f"Failed to list papers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/paper/{paper_id}")
async def get_generated_paper(paper_id: str):
    """Get a generated paper"""
    try:
        service = get_paper_service()
        paper = service.get_paper(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        return {"paper": _format_paper_for_frontend(paper)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get paper: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/paper/{paper_id}/export")
async def export_paper(
    paper_id: str,
    with_answers: bool = False,
    format: str = "markdown",
    # Academic PDF template parameters
    course_code: str = "",
    semester: str = "",
    academic_year: str = "",
    ug_pg: str = "",
    faculty: str = "",
    department: str = ""
):
    """
    Export a paper as markdown or PDF.

    For PDF format, additional academic template parameters can be provided:
    - course_code: Course code (e.g., "IS353IA")
    - semester: Semester (e.g., "V")
    - academic_year: Academic year (e.g., "2024-2025")
    - ug_pg: "UG" or "PG"
    - faculty: Faculty name(s)
    - department: Department name

    Defaults are loaded from app/config/pdf_template.yaml
    """
    try:
        service = get_paper_service()

        if format == "pdf":
            pdf_bytes = service.export_paper_pdf(
                paper_id,
                with_answers=with_answers,
                course_code=course_code,
                semester=semester,
                academic_year=academic_year,
                ug_pg=ug_pg,
                faculty=faculty,
                department=department
            )
            if not pdf_bytes:
                raise HTTPException(status_code=404, detail="Paper not found or PDF generation failed")

            from fastapi.responses import Response
            filename = f"paper_{paper_id}{'_answers' if with_answers else ''}.pdf"
            # Convert bytearray to bytes for FastAPI Response
            if isinstance(pdf_bytes, bytearray):
                pdf_bytes = bytes(pdf_bytes)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        # Default: markdown
        if with_answers:
            content = service.export_paper_with_answers(paper_id)
        else:
            content = service.export_paper_markdown(paper_id)

        if not content:
            raise HTTPException(status_code=404, detail="Paper not found")

        return {"paper_id": paper_id, "format": "markdown", "markdown": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export paper: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/paper/{paper_id}/answer-key")
async def export_answer_key(paper_id: str, format: str = "markdown"):
    """Export ONLY the answer key (separate from questions)"""
    try:
        service = get_paper_service()

        if format == "pdf":
            # For PDF, use the full with_answers export but could customize later
            pdf_bytes = service.export_paper_pdf(paper_id, with_answers=True)
            if not pdf_bytes:
                raise HTTPException(status_code=404, detail="Paper not found or PDF generation failed")

            from fastapi.responses import Response
            # Convert bytearray to bytes for FastAPI Response
            if isinstance(pdf_bytes, bytearray):
                pdf_bytes = bytes(pdf_bytes)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=answer_key_{paper_id}.pdf"}
            )

        # Markdown answer key only
        content = service.export_answer_key_only(paper_id)
        if not content:
            raise HTTPException(status_code=404, detail="Paper not found")

        return {"paper_id": paper_id, "format": "markdown", "content": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export answer key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/paper/{paper_id}/rubric")
async def get_paper_rubric(paper_id: str, format: str = "json"):
    """
    Get marking rubric for a paper.

    Format options:
    - json: Structured rubric data
    - markdown: Formatted markdown for printing
    """
    try:
        service = get_paper_service()

        if format == "markdown":
            content = service.export_rubric_markdown(paper_id)
            if not content:
                raise HTTPException(status_code=404, detail="Paper not found")
            return {"paper_id": paper_id, "format": "markdown", "content": content}

        # Default: JSON
        rubric = service.generate_paper_rubric(paper_id)
        if "error" in rubric:
            raise HTTPException(status_code=404, detail=rubric["error"])

        return {"paper_id": paper_id, "rubric": rubric}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate rubric: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics")
async def get_analytics():
    """
    Get analytics dashboard data.

    Returns:
    - papers: Total papers, by subject
    - templates: Total templates
    - questions: Question bank stats, by topic, by difficulty
    - generation: Total generated, cache hits, cache hit rate
    """
    try:
        service = get_paper_service()
        stats = service.get_analytics()
        return {"status": "success", "analytics": stats}
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# OBSERVABILITY / METRICS ENDPOINTS
# =============================================================================

@app.get("/api/v1/metrics")
async def get_generation_metrics():
    """
    Get question generation metrics and performance stats.

    Returns:
    - summary: Total runs, success rate, avg duration
    - node_performance: Per-node timing and success rates
    - common_paths: Most frequent generation paths
    - recent_errors: Last 10 errors for debugging
    """
    try:
        metrics = get_metrics()
        return {"status": "success", "metrics": metrics.get_stats()}
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/metrics/node/{node_name}")
async def get_node_metrics(node_name: str):
    """
    Get detailed metrics for a specific graph node.

    Node names: scout, theory_author, code_author, executor, question_author, reviewer, fallback, archivist
    """
    try:
        metrics = get_metrics()
        return {"status": "success", "node": metrics.get_node_stats(node_name)}
    except Exception as e:
        logger.error(f"Failed to get node metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/metrics/slow")
async def get_slow_runs(threshold_ms: float = 30000):
    """
    Get generation runs that exceeded a duration threshold.

    Args:
        threshold_ms: Duration threshold in milliseconds (default: 30000 = 30s)
    """
    try:
        metrics = get_metrics()
        return {"status": "success", "slow_runs": metrics.get_slow_runs(threshold_ms)}
    except Exception as e:
        logger.error(f"Failed to get slow runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/metrics/reset")
async def reset_metrics():
    """Reset all metrics (useful for testing or fresh starts)."""
    try:
        metrics = get_metrics()
        metrics.reset()
        return {"status": "success", "message": "Metrics reset"}
    except Exception as e:
        logger.error(f"Failed to reset metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/config/reload")
async def reload_configuration():
    """Reload prompts and tags from YAML config files without restart."""
    try:
        reload_config()
        return {"status": "success", "message": "Configuration reloaded"}
    except Exception as e:
        logger.error(f"Failed to reload config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STEP 4: PROVENANCE & EXPLAINABILITY LAYER
# ============================================================================

def get_chunks_by_ids(chunk_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch chunk content from ChromaDB by chunk IDs.

    Args:
        chunk_ids: List of chunk IDs to retrieve

    Returns:
        Dictionary mapping chunk_id to chunk data (content, metadata)
    """
    if not chunk_ids:
        return {}

    try:
        rag_engine = get_rag_engine()
        chroma_db = rag_engine.vector_store.get_database()

        # Get chunks by IDs
        result = chroma_db._collection.get(ids=chunk_ids)

        chunks_map = {}
        if result and 'documents' in result and 'metadatas' in result:
            for i, chunk_id in enumerate(result['ids']):
                chunks_map[chunk_id] = {
                    'content': result['documents'][i] if i < len(result['documents']) else '',
                    'metadata': result['metadatas'][i] if i < len(result['metadatas']) else {}
                }

        return chunks_map
    except Exception as e:
        logger.error(f"Failed to fetch chunks by IDs: {e}")
        return {}


@app.get("/api/v1/question/{question_id}/explain")
async def explain_question(question_id: int):
    """
    STEP 4: Provenance & Explainability Endpoint

    Returns provenance data for a question including:
    - Question text and metadata
    - Bloom level, CO/PO tags
    - Source documents with chunk content

    This is READ-ONLY - no regeneration allowed.
    """
    try:
        # Query SQLite for the question
        import sqlite3
        from app.core.question_bank import DB_PATH

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, topic, difficulty, question_text, answer_text,
                          bloom_level, course_outcome, program_outcome,
                          retrieved_chunk_ids, retrieved_doc_ids, source_type
                   FROM templates WHERE id = ?""",
                (question_id,)
            )
            row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Question not found")

        # Parse chunk and doc IDs from JSON
        chunk_ids = json.loads(row['retrieved_chunk_ids']) if row['retrieved_chunk_ids'] else []
        doc_ids = json.loads(row['retrieved_doc_ids']) if row['retrieved_doc_ids'] else []

        # Fetch chunk content from ChromaDB
        chunks_map = get_chunks_by_ids(chunk_ids)

        # Group chunks by document
        doc_chunks = {}
        for chunk_id in chunk_ids:
            if chunk_id in chunks_map:
                chunk_data = chunks_map[chunk_id]
                doc_source = chunk_data['metadata'].get('source', 'Unknown')

                if doc_source not in doc_chunks:
                    doc_chunks[doc_source] = []

                # Limit content preview to 300 characters
                content = chunk_data['content']
                preview = content[:300] + '...' if len(content) > 300 else content

                doc_chunks[doc_source].append({
                    'chunk_id': chunk_id,
                    'content_preview': preview,
                    'page': chunk_data['metadata'].get('page', 'N/A')
                })

        # Build source documents list
        source_documents = []
        for doc_id in set(doc_ids):
            chunks = doc_chunks.get(doc_id, [])
            source_documents.append({
                'doc_id': doc_id,
                'chunk_count': len(chunks),
                'chunks': chunks
            })

        # Build response
        response = {
            'question_id': row['id'],
            'question_text': row['question_text'],
            'answer': row['answer_text'],
            'topic': row['topic'],
            'difficulty': row['difficulty'],
            'bloom_level': row['bloom_level'],
            'course_outcome': row['course_outcome'],
            'program_outcome': row['program_outcome'],
            'source_type': row['source_type'],
            'source_documents': source_documents,
            'total_chunks_used': len(chunk_ids)
        }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to explain question {question_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))