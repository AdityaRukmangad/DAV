# CHAPTER 3: SOFTWARE REQUIREMENTS SPECIFICATION

## 3.1 Software Requirements

The system requires specific software components for development, deployment, and operation. Table 3.1 details the software requirements across different categories.

**Table 3.1: Software Requirements**

| Category | Component | Version | Purpose |
|----------|-----------|---------|---------|
| **Backend Framework** | Python | 3.11+ | Core programming language |
| | FastAPI | 0.128.0+ | REST API framework with async support |
| | Uvicorn | 0.40.0+ | ASGI server for FastAPI |
| **LLM & AI** | LangChain | 0.3.0 | LLM orchestration framework |
| | LangGraph | Latest | Multi-agent state machine |
| | OpenAI API | GPT-4 | Language model for generation |
| | Sentence-Transformers | 5.2.0+ | Text embedding models |
| **Vector Database** | ChromaDB | 0.5.23+ | Vector storage and similarity search |
| | HNSW | (bundled) | Approximate nearest neighbor |
| **Retrieval & Ranking** | FlashRank | 0.2.4 | Cross-encoder reranking |
| | PyPDF | 6.6.0+ | PDF text extraction |
| **Storage** | SQLite | 3.x | Question bank persistence |
| **Frontend** | Node.js | 18.x+ | JavaScript runtime |
| | React | 18.3.x | UI library |
| | TypeScript | 5.x | Type-safe JavaScript |
| | Vite | Latest | Build tool and dev server |
| | TailwindCSS | 3.x | Utility-first CSS framework |
| **Development** | Git | 2.x+ | Version control |
| | pytest | Latest | Python testing framework |
| | ESLint | Latest | JavaScript/TypeScript linter |
| **Deployment** | Docker | (optional) | Containerization |
| | Nginx | (optional) | Reverse proxy for production |

**Operating System Compatibility:**
- Linux (Ubuntu 22.04 LTS recommended)
- macOS (Monterey or later)
- Windows 10/11 with WSL2

**API Dependencies:**
- OpenAI API key with GPT-4 access
- Minimum $20 API credit for typical usage patterns

## 3.2 Hardware Requirements

The hardware specifications vary based on deployment scenario (development vs production) and expected load. Table 3.2 outlines minimum and recommended configurations.

**Table 3.2: Hardware Requirements**

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| **Processor** | 4-core CPU (Intel i5/AMD Ryzen 5) | 8-core CPU (Intel i7/AMD Ryzen 7) | 16-core CPU (Xeon/EPYC) |
| **RAM** | 8 GB | 16 GB | 32 GB+ |
| **Storage** | 20 GB SSD | 50 GB SSD | 100 GB+ NVMe SSD |
| **GPU** | None | None (CPU only) | Optional for local embeddings |
| **Network** | 10 Mbps | 50 Mbps | 100 Mbps+ |

**Storage Breakdown:**
- Operating System: 5 GB
- Python dependencies: 3 GB
- Node.js dependencies: 500 MB
- ChromaDB vector index: 100 MB per 10,000 chunks (grows with ingested PDFs)
- SQLite database: 50 MB per 1,000 questions
- Application code: 100 MB
- Workspace: 10 GB for PDFs and temporary files

**Performance Characteristics:**
- RAM usage scales with PDF corpus size (embeddings cached in memory)
- Disk I/O critical for vector search performance (SSD strongly recommended)
- Network bandwidth important for OpenAI API calls (streaming responses)

**Scalability Considerations:**
- Single server deployment handles 10-20 concurrent users
- Horizontal scaling possible through load balancer + multiple backend instances
- Vector database can be moved to dedicated server for large deployments

---

# CHAPTER 4: DESIGN OF THE PROJECT

## 4.1 System Architecture

The system follows a three-tier architecture with clear separation between presentation, application logic, and data persistence layers. Figure 4.1 illustrates the high-level architecture.

**Figure 4.1: System Architecture Diagram**

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │ Generation │  │ Paper       │  │ Provenance Viewer    │ │
│  │ Module     │  │ Composer    │  │ (Explainability)     │ │
│  └────────────┘  └─────────────┘  └──────────────────────┘ │
│         │                │                    │              │
│         └────────────────┴────────────────────┘              │
│                          │                                   │
│              React Frontend (TypeScript + Vite)              │
└──────────────────────────┼──────────────────────────────────┘
                           │ REST API (JSON over HTTP)
┌──────────────────────────┼──────────────────────────────────┐
│                   APPLICATION LAYER                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            FastAPI Endpoints                         │   │
│  │  /generate  /batch  /paper  /context  /provenance   │   │
│  └────────────┬─────────────────────────────────────────┘   │
│               │                                              │
│  ┌────────────▼───────────────────────────────────┐         │
│  │        LangGraph Multi-Agent Pipeline          │         │
│  │  ┌──────────┐  ┌────────┐  ┌──────────────┐   │         │
│  │  │  Bloom   │→ │ Scout  │→ │  Generator   │   │         │
│  │  │ Analyzer │  │ (RAG)  │  │  (LLM)       │   │         │
│  │  └──────────┘  └────────┘  └──────┬───────┘   │         │
│  │                                    ▼           │         │
│  │              ┌──────────────┐  ┌──────────┐   │         │
│  │              │  Validator   │→ │ Pedagogy │   │         │
│  │              │  (Tribunal)  │  │ Tagger   │   │         │
│  │              └──────────────┘  └─────┬────┘   │         │
│  │                                      ▼        │         │
│  │              ┌──────────────────────────┐     │         │
│  │              │ Guardian (Syllabus Check)│     │         │
│  │              └──────────────────────────┘     │         │
│  └────────────────────────────────────────────────┘         │
│               │                     │                        │
│  ┌────────────▼──────┐   ┌──────────▼─────────┐            │
│  │   RAG Service     │   │  Question Bank     │            │
│  │  - Embeddings     │   │  (SQLite)          │            │
│  │  - ChromaDB       │   │  - Metadata        │            │
│  │  - FlashRank      │   │  - Provenance      │            │
│  └───────────────────┘   └────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                     DATA LAYER                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  PDF Files   │  │ Vector Index │  │ Question DB      │  │
│  │  (Course     │  │ (ChromaDB)   │  │ (SQLite)         │  │
│  │  Materials)  │  │              │  │ - Questions      │  │
│  │              │  │ - Embeddings │  │ - Bloom levels   │  │
│  │              │  │ - Metadata   │  │ - CO/PO tags     │  │
│  │              │  │              │  │ - Provenance     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Architecture Characteristics:**

1. **Separation of Concerns**: Clear boundaries between UI, business logic, and data
2. **Stateless API**: REST endpoints enable horizontal scaling
3. **Event-Driven**: LangGraph state machine enables reactive workflows
4. **Modular Design**: Components can be developed and tested independently
5. **Observable**: Comprehensive logging and provenance tracking at each layer

**Data Flow Example (Question Generation):**

1. User enters topic in React frontend
2. Frontend POST request to `/api/v1/generate` with topic, difficulty
3. FastAPI endpoint initiates LangGraph workflow
4. Bloom Analyzer classifies topic → Bloom level 3
5. Scout retrieves k=8 chunks from ChromaDB based on Bloom level
6. Generator creates question using retrieved context + LLM
7. Validator checks correctness, loops back if quality insufficient
8. Pedagogy Tagger assigns CO2, PO1 based on question + Bloom level
9. Guardian validates topic against syllabus
10. Archivist saves to SQLite with full provenance metadata
11. Response streams back to frontend with progress updates
12. Provenance Viewer displays Bloom level, CO/PO, source chunks

## 4.2 Functional Description of the Modules

The system comprises ten core modules, each with specific responsibilities. Table 4.1 provides an overview before detailed descriptions.

**Table 4.1: Module Descriptions**

| Module | Primary Function | Dependencies |
|--------|-----------------|--------------|
| Bloom Analyzer | Classify topic cognitive level | LangChain, OpenAI |
| Scout (RAG) | Retrieve relevant context | ChromaDB, FlashRank |
| Generator | Create question text | LangChain, OpenAI |
| Validator | Quality assurance | LangChain, Python sandbox |
| Pedagogy Tagger | CO/PO assignment | LangChain, OpenAI |
| Guardian | Syllabus validation | Fuzzy matching library |
| Provenance Viewer | Explainability UI | React, TypeScript |
| Paper Composer | Template-based assembly | SQLite, Frontend |
| Question Bank | Persistent storage | SQLite |
| Web Interface | User interaction | React, Vite |

### 4.2.1 Bloom Analyzer Module

**Purpose:** Classifies the cognitive complexity of a given topic using Bloom's taxonomy levels 1-6 to enable adaptive RAG retrieval.

**Inputs:**
- Topic string (e.g., "Define entropy in decision trees")
- Question type (optional): mcq, short, long, calculation

**Processing:**
1. Extract verb from topic using NLP parsing
2. Analyze syntactic complexity and keyword patterns
3. Construct few-shot prompt with Bloom taxonomy examples
4. Invoke GPT-4 with structured output schema (BloomAnalysis)
5. Validate returned level within range [1, 6]
6. Log classification reasoning for debugging

**Outputs:**
- bloom_level (integer 1-6)
- reasoning (string explaining classification)

**Algorithm:**

```
function detect_bloom_level(topic, question_type):
    if BLOOM_RAG_ENABLED == false:
        return 3  // Default middle level

    // Build classification prompt
    prompt = construct_bloom_prompt(topic, question_type)

    // Few-shot examples embedded in prompt:
    // "Define X" → Level 1 (Remember)
    // "Explain Y" → Level 2 (Understand)
    // "Calculate Z" → Level 3 (Apply)
    // "Compare A and B" → Level 4 (Analyze)
    // "Evaluate which is better" → Level 5 (Evaluate)
    // "Design a new approach" → Level 6 (Create)

    // Invoke LLM with structured output
    response = LLM.invoke(prompt, schema=BloomAnalysis)
    level = response.bloom_level

    // Validation
    if level < 1 or level > 6:
        log_warning("Invalid Bloom level, defaulting to 3")
        return 3

    log_info(f"Bloom Level {level}: {response.reasoning}")
    return level
```

**Integration Point:**
- First node in LangGraph pipeline
- Output `bloom_level` stored in AgentState
- Used by Scout module to determine retrieval k

**Error Handling:**
- LLM API failures default to Bloom level 3
- Invalid outputs (level out of range) trigger fallback
- Configurable via `BLOOM_RAG_ENABLED` environment variable

### 4.2.2 Scout Module (RAG Retrieval)

**Purpose:** Retrieves relevant context from ingested PDF materials using Bloom-adaptive k-value for optimal information density.

**Inputs:**
- Topic string
- Bloom level (from Analyzer)
- Previous retrieval cache (optional)

**Processing Steps:**

1. **Adaptive k Calculation:**
```
k = bloom_to_k(bloom_level)
  = 4  if bloom_level ≤ 2
  = 8  if bloom_level ≤ 4
  = 13 if bloom_level ≥ 5
```

2. **Query Expansion:**
   - Extract content keywords (algorithm, definition, formula, etc.)
   - Generate specialized sub-queries for each keyword type
   - Maintain primary query for general context

3. **Parallel Retrieval:**
   - Execute primary search with adaptive k
   - Execute keyword-specific searches with k=5 each
   - Use ThreadPoolExecutor for concurrent searches

4. **Embedding-Based Search:**
```
query_embedding = sentence_transformer.encode(query)
results = chromadb.query(
    query_embeddings=[query_embedding],
    n_results=k,
    where={"source": "pdf"}  // Filter by document type
)
```

5. **Reranking:**
```
reranked = flashrank.rerank(
    query=original_query,
    documents=retrieved_chunks,
    top_k=k  // Final k after reranking
)
```

6. **Provenance Capture:**
```
chunk_ids = [chunk.id for chunk in reranked]
doc_ids = [chunk.metadata['source'] for chunk in reranked]
pages = [chunk.metadata['page'] for chunk in reranked]
```

**Outputs:**
- retrieved_context (concatenated text from top-k chunks)
- retrieved_chunk_ids (list of unique chunk identifiers)
- retrieved_doc_ids (list of source document names)
- source_pages (list of PDF page numbers)
- detected_keywords (dict mapping keywords to their contexts)

**Performance Optimization:**
- Cache query results with TTL=300s
- Deduplicate similar queries using embedding similarity > 0.95
- Use HNSW index for O(log N) search complexity

**Figure 4.2: Bloom-Adaptive Retrieval Strategy**

```
Query: "Define entropy"
  ↓
Bloom Analyzer → Level 1 (Remember)
  ↓
bloom_to_k(1) → k=4
  ↓
ChromaDB retrieval (4 chunks)
  ↓
FlashRank reranking (top 4)
  ↓
Context: [Definition chunk, Formula chunk, Example chunk, Property chunk]

vs.

Query: "Design a new splitting criterion"
  ↓
Bloom Analyzer → Level 6 (Create)
  ↓
bloom_to_k(6) → k=13
  ↓
ChromaDB retrieval (13 chunks)
  ↓
FlashRank reranking (top 13)
  ↓
Context: [Definitions, Existing methods, Comparisons, Trade-offs,
          Theoretical background, Implementation details,
          Evaluation metrics, Case studies, ...]
```

### 4.2.3 Generator Module

**Purpose:** Creates question text, answer, and explanation using retrieved context and LLM generation.

**Dual-Path Architecture:**

The generator implements two distinct workflows based on question type:

**Path A: Theory Questions (Conceptual)**
- For question types: short, long, mcq, theory
- Generates question directly from context using template prompts
- No code verification required

**Path B: Computational Questions**
- For question types: calculation, trace, algorithm
- Two-pass generation:
  1. First pass: Generate verification code only
  2. Execute code to compute correct answer
  3. Second pass: Generate question text using computed answer

**Theory Question Generation:**

```
function generate_theory_question(state):
    topic = state.topic
    difficulty = state.target_difficulty
    context = state.retrieved_context
    bloom_level = state.bloom_level

    // Load appropriate template
    template = get_question_template(state.question_type)

    // Construct prompt with context
    prompt = f"""
    Based on the following context from course materials:

    {context}

    Generate a {difficulty} {question_type} question about: {topic}

    Cognitive Level: Bloom Level {bloom_level}

    {template}
    """

    // Invoke LLM with structured output
    response = LLM.invoke(prompt, schema=QuestionSchema)

    return {
        question: response.question,
        answer: response.answer,
        explanation: response.explanation,
        question_type: question_type
    }
```

**Computational Question Generation:**

```
function generate_computational_question(state):
    topic = state.topic
    context = state.retrieved_context

    // PASS 1: Generate verification code
    code_prompt = construct_code_prompt(topic, context)
    code = LLM.invoke(code_prompt, mode="code")

    // Execute code to get computed result
    try:
        result = execute_python(code)
        computed_answer = result.output
    catch ExecutionError:
        log_error("Code execution failed, retrying...")
        return retry_generation()

    // PASS 2: Generate question using computed answer
    question_prompt = construct_question_prompt(
        topic, context, code, computed_answer
    )

    question_data = LLM.invoke(question_prompt, schema=QuestionSchema)

    return {
        question: question_data.question,
        answer: computed_answer,
        verification_code: code,
        explanation: question_data.explanation
    }
```

**Output Schema:**

```python
class QuestionSchema(BaseModel):
    question: str = Field(description="The question text")
    answer: str = Field(description="Correct answer")
    explanation: str = Field(description="Detailed explanation")
    question_type: str = Field(description="Question category")
```

**Quality Controls:**
- Minimum question length: 50 characters
- Maximum question length: 1000 characters
- Answer must be present and non-empty
- For computational questions, answer must match code execution result

### 4.2.4 Validator Module (Tribunal)

**Purpose:** Multi-stage validation ensuring correctness, clarity, appropriate difficulty, and pedagogical soundness.

**Parallel Review Architecture:**

The validator runs two agents concurrently:

1. **Critic Agent:** Assesses question quality, clarity, difficulty calibration
2. **Verification Agent:** Checks answer correctness through code execution or cross-reference

```
function parallel_review(state):
    question_data = state.question_data

    // Run critic and validator in parallel
    with ThreadPoolExecutor() as executor:
        critic_future = executor.submit(run_critic, question_data)
        verify_future = executor.submit(run_verifier, question_data)

        critique = critic_future.result()
        verification = verify_future.result()

    // Aggregate results
    is_passing = critique.score >= 7.0 AND verification.correct

    if not is_passing:
        state.revision_count += 1
        if state.revision_count < MAX_RETRIES:
            return route_to_generator_with_feedback(critique)
        else:
            return route_to_fallback()

    return route_to_tagger()  // Proceed to pedagogy tagging
```

**Critic Agent Evaluation Criteria:**

```
Rubric (1-10 scale):
- Clarity (2 points): Unambiguous phrasing, well-defined terms
- Relevance (2 points): Aligned with topic and retrieved context
- Difficulty (2 points): Matches target difficulty level
- Pedagogical Value (2 points): Tests meaningful concepts
- Answer Quality (2 points): Complete, accurate explanation
```

**Verification Agent Logic:**

For computational questions:
```
function verify_computational(question, code, stated_answer):
    // Re-execute verification code
    actual_answer = execute_python(code)

    // Fuzzy match for numerical tolerance
    match = abs(actual_answer - stated_answer) < EPSILON

    if not match:
        return {
            correct: false,
            error: f"Answer mismatch: expected {actual_answer}, got {stated_answer}"
        }

    return {correct: true}
```

For theory questions:
```
function verify_theory(question, answer, context):
    // Check if answer is grounded in retrieved context
    similarity = semantic_similarity(answer, context)

    if similarity < THRESHOLD:
        return {
            correct: false,
            error: "Answer not supported by source materials"
        }

    return {correct: true}
```

**Iterative Refinement:**

When validation fails:
1. Append critique to state feedback
2. Increment revision counter
3. Route back to generator with feedback
4. Generator adjusts based on specific critique points
5. Re-validation (max 2 retries)

If all retries exhausted:
- Log failure reason
- Route to fallback (use cached similar question or skip)

### 4.2.5 Pedagogy Tagger Module

**Purpose:** Automatically assigns Course Outcomes (CO) and Program Outcomes (PO) based on question content and Bloom level.

**Activation:** Controlled by `ENABLE_PEDAGOGY_TAGGER` environment variable (default: false for backward compatibility).

**Input:**
- question_data (full question with answer)
- bloom_level (from Bloom Analyzer)
- topic (original query)

**Hybrid Tagging Strategy:**

```
function tag_pedagogy(state):
    if not ENABLE_PEDAGOGY_TAGGER:
        return {}  // Skip tagging

    question = state.question_data.question
    bloom = state.bloom_level

    // Try rule-based first
    if can_apply_rules(bloom, question):
        co, po = rule_based_tagging(bloom, question)
        confidence = 0.9
    else:
        // Fall back to LLM classification
        co, po = llm_tagging(question, bloom)
        confidence = 0.7

    log_info(f"Tagged {co}, {po} with confidence {confidence}")

    return {
        course_outcome: co,
        program_outcome: po
    }
```

**Rule-Based Heuristics:**

```
CO Assignment Rules:
- Bloom 1-2 + keywords(define, list, state) → CO1 (Knowledge)
- Bloom 3 + keywords(calculate, apply, solve) → CO2 (Application)
- Bloom 4 + keywords(analyze, compare) → CO3 (Analysis)
- Bloom 5-6 + keywords(evaluate, design) → CO4 (Synthesis)

PO Assignment Rules:
- Question type = calculation/trace → PO1 (Engineering knowledge)
- Bloom 4-6 → PO2 (Problem analysis)
- Design/create questions → PO3 (Design/development)
```

**LLM-Based Tagging:**

```
Prompt Template:
"You are an education expert mapping questions to learning outcomes.

QUESTION: {question_text}
BLOOM LEVEL: {bloom_level}
TOPIC: {topic}

Assign the most appropriate:
- Course Outcome (CO1-CO5)
- Program Outcome (PO1-PO6)

Course Outcomes:
CO1: Remember and understand fundamental concepts
CO2: Apply knowledge to solve problems
CO3: Analyze and evaluate complex scenarios
CO4: Design and create solutions
CO5: Communicate effectively

Program Outcomes:
PO1: Engineering knowledge
PO2: Problem analysis
PO3: Design/development of solutions
PO4: Research skills
PO5: Modern tool usage
PO6: Professional skills

Output JSON: {\"co\": \"CO2\", \"po\": \"PO1\", \"reasoning\": \"...\"}
"
```

**Validation:**
- CO must match pattern CO[1-5]
- PO must match pattern PO[1-6]
- If invalid, apply fallback based on Bloom level

**Storage:**
- CO/PO fields added to SQLite schema
- Displayed in Provenance Viewer for transparency

### 4.2.6 Guardian Module (Syllabus Validator)

**Purpose:** Ensures generated questions align with prescribed course syllabus and unit structure, preventing out-of-scope content.

**Activation:** Controlled by `ENABLE_GUARDIAN` environment variable (default: true).

**Syllabus Structure:**

```yaml
course:
  name: "Data Structures and Algorithms"
  units:
    - unit: 1
      topics:
        - Arrays and Linked Lists
        - Stacks and Queues
        - Trees (Binary, BST)
    - unit: 2
      topics:
        - Sorting Algorithms
        - Searching Algorithms
        - Hashing
    - unit: 3
      topics:
        - Graphs (Traversal, MST)
        - Dynamic Programming
```

**Validation Algorithm:**

```
function validate_topic_against_syllabus(topic, syllabus):
    topic_tokens = tokenize(lowercase(topic))

    for unit in syllabus.units:
        for syllabus_topic in unit.topics:
            syllabus_tokens = tokenize(lowercase(syllabus_topic))

            // Fuzzy matching strategies:

            // 1. Exact substring match
            if topic in syllabus_topic OR syllabus_topic in topic:
                return {valid: true, unit: unit.number, match: syllabus_topic}

            // 2. Jaccard similarity (token overlap)
            intersection = topic_tokens ∩ syllabus_tokens
            union = topic_tokens ∪ syllabus_tokens
            jaccard = |intersection| / |union|

            if jaccard > 0.6:
                return {valid: true, unit: unit.number, match: syllabus_topic}

            // 3. Levenshtein distance
            edit_dist = levenshtein(topic, syllabus_topic)
            similarity = 1 - (edit_dist / max(len(topic), len(syllabus_topic)))

            if similarity > 0.75:
                return {valid: true, unit: unit.number, match: syllabus_topic}

    // No match found
    return {valid: false, reason: "Topic not found in syllabus"}
```

**Table 4.2: Guardian Validator Rule Set**

| Bloom Level | Matching Threshold | Regeneration Allowed | Rationale |
|-------------|-------------------|----------------------|-----------|
| 1-2 | 0.6 (relaxed) | Yes (1 attempt) | Factual questions have less variance |
| 3-4 | 0.7 (moderate) | Yes (1 attempt) | Applied questions may use alternate phrasing |
| 5-6 | 0.8 (strict) | No | Creative questions risk going off-syllabus |

**Regeneration Logic:**

```
function check_with_guardian(state):
    if not ENABLE_GUARDIAN:
        return {syllabus_valid: true}

    topic = state.topic
    bloom = state.bloom_level

    validation = validate_topic_against_syllabus(topic, SYLLABUS)

    if validation.valid:
        log_info(f"Topic '{topic}' matches Unit {validation.unit}: {validation.match}")
        return {syllabus_valid: true, unit: validation.unit}

    // Failed validation
    if state.guardian_retries < 1 AND bloom <= 4:
        log_warning(f"Topic '{topic}' not in syllabus, allowing 1 regeneration")
        state.guardian_retries += 1
        return route_to_generator_with_syllabus_constraint()
    else:
        log_error(f"Topic '{topic}' rejected by Guardian")
        return {
            syllabus_valid: false,
            error: "Topic outside course syllabus",
            use_fallback: true
        }
```

**Configuration:**

```bash
# Enable/disable Guardian
ENABLE_GUARDIAN=true

# Syllabus file path
SYLLABUS_PATH=./data/syllabi/ds_syllabus.yaml

# Matching strictness (0.0 - 1.0)
GUARDIAN_THRESHOLD=0.7
```

**Error Handling:**
- Missing syllabus file: Guardian disabled automatically with warning
- Malformed syllabus YAML: Validation fails-closed (rejects all topics)
- Network timeout during validation: Allow question with logged warning

### 4.2.7 Provenance Viewer (Explainability Component)

**Purpose:** Provides transparent, read-only view of metadata explaining how each question was generated.

**Displayed Information:**

1. **Bloom's Taxonomy Classification**
   - Detected level (1-6)
   - Reasoning for classification
   - Cognitive demand category (Remember/Understand/Apply/Analyze/Evaluate/Create)

2. **Educational Outcome Tags**
   - Assigned Course Outcome (CO)
   - Assigned Program Outcome (PO)
   - Tagging confidence (rule-based vs LLM)

3. **Source PDF Provenance**
   - Retrieved chunk IDs with preview
   - Source document names
   - PDF page numbers
   - Expandable view of full chunk content

4. **Generation Metadata**
   - Retrieval strategy (adaptive k value used)
   - Number of chunks retrieved vs final k
   - Validation score from tribunal
   - Guardian status (pass/fail + unit mapping)

**Figure 4.4: Provenance Viewer Component Design**

```
┌─────────────────────────────────────────────────────┐
│        Provenance Viewer - Question #42             │
├─────────────────────────────────────────────────────┤
│  Topic: "Calculate information gain for dataset"    │
│                                                      │
│  ▼ Bloom's Taxonomy                                 │
│     Level: 3 (Apply)                                │
│     Reason: Question requires applying formula      │
│     Retrieval: k=8 chunks (Bloom-adaptive)          │
│                                                      │
│  ▼ Educational Outcomes                             │
│     Course Outcome: CO2 (Application)               │
│     Program Outcome: PO1 (Engineering knowledge)    │
│     Confidence: 0.9 (Rule-based)                    │
│                                                      │
│  ▼ Source Materials                                 │
│     Document: ML_Textbook.pdf                       │
│     Pages: [45, 46, 47, 48]                         │
│                                                      │
│     [Expand Chunk 1] (page 45)                      │
│     "Information gain is a measure of..."           │
│                                                      │
│     [Expand Chunk 2] (page 46)                      │
│     "Formula: IG(S,A) = Entropy(S) - ..."           │
│                                                      │
│  ▼ Validation                                       │
│     Guardian: ✓ Passed (Unit 2: Decision Trees)    │
│     Quality Score: 8.5/10                           │
│     Verification: ✓ Code execution matched answer  │
│                                                      │
│  [ Close ]                                          │
└─────────────────────────────────────────────────────┘
```

**Frontend Implementation:**

```typescript
interface ProvenanceData {
    bloom_level: number;
    bloom_reasoning: string;
    course_outcome: string;
    program_outcome: string;
    retrieved_chunks: Array<{
        id: string;
        content: string;
        source_doc: string;
        page_num: number;
    }>;
    guardian_status: {
        valid: boolean;
        unit: number;
        match: string;
    };
    validation_score: number;
}

function ProvenanceViewer({questionId}: Props) {
    const [provenance, setProvenance] = useState<ProvenanceData>();
    const [expandedChunks, setExpandedChunks] = useState<Set<string>>();

    useEffect(() => {
        fetchProvenance(questionId).then(setProvenance);
    }, [questionId]);

    return (
        <Modal>
            <Section title="Bloom's Taxonomy">
                <Badge level={provenance.bloom_level} />
                <Text>{provenance.bloom_reasoning}</Text>
            </Section>

            <Section title="Educational Outcomes">
                <Tag>{provenance.course_outcome}</Tag>
                <Tag>{provenance.program_outcome}</Tag>
            </Section>

            <Section title="Source Materials">
                {provenance.retrieved_chunks.map(chunk => (
                    <ChunkPreview
                        chunk={chunk}
                        expanded={expandedChunks.has(chunk.id)}
                        onToggle={() => toggleChunk(chunk.id)}
                    />
                ))}
            </Section>
        </Modal>
    );
}
```

**Data Flow:**

1. User clicks "View Provenance" on generated question
2. Frontend fetches from `/api/v1/provenance/{question_id}`
3. Backend queries SQLite for full_json column containing all metadata
4. Response includes Bloom level, CO/PO, chunk IDs, validation scores
5. Frontend renders expandable sections with source snippets
6. User can verify question grounding in specific textbook passages

**Access Control:**
- Read-only (no editing or regeneration from viewer)
- Available for all questions in bank
- Optional PDF snippet highlighting (if PDF viewer integrated)

**Benefits:**
- Builds trust through transparency
- Enables faculty to verify correctness against sources
- Supports error diagnosis (if bad question, which chunk caused it?)
- Educational value (students can see what materials support answer)

