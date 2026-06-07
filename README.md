# Tribunal: AI Questionnaire Generator

An intelligent, multi-agent system for generating high-quality evaluation questions with verification code, provenance tracking, syllabus validation, and a full-featured Data Analytics & Visualization (DAV) dashboard.

## Features

### Core Capabilities
- **Multi-Agent Pipeline**: LangGraph-based workflow with specialized agents (Scout, Code Author, Executor, Question Author, Reviewer, Pedagogy Tagger, Guardian)
- **Code-First Generation**: Generates verification code first, executes it, then writes the question
- **RAG-Powered**: Retrieves context from uploaded PDFs using ChromaDB vector store
- **Quality Assurance**: Built-in critic agent with configurable quality thresholds
- **Question Bank**: SQLite database with deduplication and caching
- **Paper Generation**: Create full exam papers with customizable templates

### Advanced Features (Steps 2-5)

#### Step 2: Bloom-Adaptive RAG
- Detects Bloom's taxonomy level (1-6) from topic
- Adjusts RAG retrieval strategy based on cognitive level
- Stores chunk IDs and document IDs for provenance

#### Step 3: Pedagogy Tagger
- Automatically assigns Course Outcomes (CO) and Program Outcomes (PO)
- Educational metadata for NBA/NAAC compliance
- Enable with `ENABLE_PEDAGOGY_TAGGER=true`

#### Step 4: Provenance & Explainability
- View source documents and chunks used for question generation
- Display Bloom level, CO/PO tags, and metadata
- Read-only provenance viewer (no regeneration)
- API endpoint: `GET /api/v1/question/{id}/explain`

#### Step 5: Guardian Syllabus Validator
- Validates questions against course syllabus
- Fuzzy matching with configurable thresholds
- Allows ONE regeneration if validation fails
- Enable with `ENABLE_GUARDIAN=true`
- Configure syllabus in `config/syllabus.yaml`

### Step 6: Data Analytics & Visualization (DAV)

A full analytics dashboard powered by a dedicated backend service and React frontend with interactive charts. Covers all 6 DAV components from the project specification.

**Backend service** (`app/services/dav_service.py`):

| Function | Purpose |
|---|---|
| `clean_data()` | Remove duplicates, standardize difficulty casing, fill missing Bloom/CO/PO |
| `get_overview()` | Total questions, unique topics, difficulty variance & std dev, Bloom balance score |
| `get_bloom_distribution()` | Per-level counts, per-topic breakdown, Difficulty × Bloom heatmap matrix |
| `get_topic_coverage()` | Maps questions to `syllabus.yaml` — coverage % and gap topics per unit |
| `get_difficulty_trends()` | Daily/weekly stacked counts, cumulative growth curve, avg difficulty over time |
| `get_copo_matrix()` | NBA/NAAC CO × PO attainment matrix with 4-level scoring |
| `get_eda_report()` | Mean difficulty, variance, top-10 topics, data quality %, accuracy proxies |
| `get_paper_balance()` | Compares actual Bloom distribution against ideal — flags imbalances, gives suggestions |
| `get_similarity_report()` | Jaccard similarity scan — detects exact-duplicate, near-duplicate, similar question pairs |
| `submit_feedback()` | Bulk insert student response records into `student_feedback` table |
| `get_feedback_analysis()` | Per-question accuracy, weak topic detection, score distribution, difficult question flags |
| `get_copo_consistency()` | Validates CO/PO tags against Bloom-level rules — flags mismatches for accreditation |

**Frontend dashboard** (`frontend/components/DAVModule.tsx`) — 10-tab interface:

| Tab | Visualizations |
|---|---|
| Overview | Difficulty pie, source pie, stat chips (variance, std dev, Bloom balance), data cleaning |
| Bloom's | Bar chart by cognitive level, Difficulty × Bloom intensity heatmap |
| Coverage | Unit coverage radar, per-unit bar chart, expandable topic accordion (✓/✗), gap topics |
| Trends | Stacked bar (Easy/Medium/Hard), cumulative growth line, avg difficulty line |
| CO-PO | NBA attainment matrix (4-level color coded), CO bar, PO bar |
| EDA | Stats row, Bloom bar, Top-10 topics, content quality bars, completeness gaps, CO pie |
| Balance | Actual vs ideal Bloom bar chart, difficulty actual vs ideal, deviation table, suggestions |
| Similarity | Threshold slider, flagged pair cards with side-by-side question previews |
| Feedback | Score distribution bar, topic performance (color-coded), weak topics, difficult questions |
| Consistency | CO/PO issue pie, Bloom→CO rules reference, filterable issue list with fix guidance |

**All API endpoints** (`/api/v1/dav/*`):
- `GET  /api/v1/dav/overview`
- `GET  /api/v1/dav/bloom-distribution`
- `GET  /api/v1/dav/topic-coverage`
- `GET  /api/v1/dav/difficulty-trends`
- `GET  /api/v1/dav/copo-matrix`
- `GET  /api/v1/dav/eda-report`
- `POST /api/v1/dav/clean`
- `GET  /api/v1/dav/paper-balance`
- `GET  /api/v1/dav/similarity?threshold=0.55`
- `GET  /api/v1/dav/feedback`
- `POST /api/v1/dav/feedback`
- `GET  /api/v1/dav/copo-consistency`

---

## Installation

### Prerequisites
- Python 3.9+
- Node.js 18+
- Git

### Backend Setup

```bash
# Clone repository
git clone https://github.com/yourusername/tribunal.git
cd tribunal

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables — copy the example and fill in your key
cp .env.example .env
```

Edit `.env` and add your API key. **Gemini is recommended** (free tier available):

```bash
# Option 1: Google Gemini (recommended)
GEMINI_API_KEY=your_gemini_api_key_here

# Option 2: OpenAI (fallback)
# OPENAI_API_KEY=your_openai_api_key_here
```

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com) → API Keys.

```bash
# Initialize database
python -c "from app.core.question_bank import init_db; init_db()"

# Start backend server
uvicorn api:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies (includes Recharts for DAV charts)
npm install

# Start development server
npm run dev
```

Access the UI at `http://localhost:5173`

---

## Quick Start

### 1. Upload a PDF

```bash
# Via CLI
python main.py --upload path/to/document.pdf

# Via API
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@document.pdf"
```

### 2. Generate a Question

```bash
# Via CLI
python main.py --topic "decision trees" --difficulty Medium

# Via API
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "decision trees", "difficulty": "Medium"}'
```

### 3. View Provenance (Step 4)

```bash
curl http://localhost:8000/api/v1/question/1/explain
```

### 4. Analytics Dashboard (Step 6)

Open the **Analytics** tab in the UI, or query directly:

```bash
# Overview stats
curl http://localhost:8000/api/v1/dav/overview

# Syllabus coverage gap report
curl http://localhost:8000/api/v1/dav/topic-coverage

# CO-PO attainment matrix
curl http://localhost:8000/api/v1/dav/copo-matrix

# Full EDA report
curl http://localhost:8000/api/v1/dav/eda-report

# Paper balance check (Bloom distribution vs ideal)
curl http://localhost:8000/api/v1/dav/paper-balance

# Similar/duplicate question detection
curl "http://localhost:8000/api/v1/dav/similarity?threshold=0.55"

# CO/PO mapping consistency check
curl http://localhost:8000/api/v1/dav/copo-consistency

# Student feedback analysis
curl http://localhost:8000/api/v1/dav/feedback

# Submit student feedback (bulk)
curl -X POST http://localhost:8000/api/v1/dav/feedback \
  -H "Content-Type: application/json" \
  -d '{"feedbacks": [{"question_id": 1, "student_id": "s1", "score": 72, "correct": true, "difficulty_felt": "Medium"}]}'

# Data cleaning pass
curl -X POST http://localhost:8000/api/v1/dav/clean
```

### 5. Generate a Paper

```bash
python main.py --paper templates/midterm_template.json
```

---

## Configuration

### Syllabus Configuration (Guardian + DAV Coverage)

Edit `config/syllabus.yaml`:

```yaml
enabled: true  # Enable Guardian validation

course:
  code: "CS501"
  name: "Machine Learning"

units:
  - unit: 1
    name: "Introduction"
    topics:
      - "supervised learning"
      - "unsupervised learning"

validation:
  similarity_threshold: 0.6  # Default matching threshold
  strict_threshold: 0.8      # For Bloom level 5-6
  max_regenerations: 1       # Allow one retry
```

> The same syllabus.yaml drives both the Guardian validator and the DAV coverage gap analysis.

### Environment Variables

```bash
# ── API Key (pick one) ────────────────────────────────────────
GEMINI_API_KEY=your_gemini_key      # Recommended — free tier at aistudio.google.com
# OPENAI_API_KEY=your_openai_key    # Fallback if not using Gemini

# ── Optional Features (default: false) ───────────────────────
ENABLE_PEDAGOGY_TAGGER=false        # Enable CO/PO tagging (Step 3)
ENABLE_GUARDIAN=false               # Enable syllabus validation (Step 5)

# ── Bloom-Adaptive RAG tuning (Step 2) ───────────────────────
BLOOM_RAG_ENABLED=true
BLOOM_K_LOW=4
BLOOM_K_MED=8
BLOOM_K_HIGH=13
```

**Gemini models used:**

| Mode | Model | Used for |
|---|---|---|
| instant / auto | `gemini-2.0-flash` | Bloom detection, tagging, most generation |
| thinking | `gemini-2.5-flash-preview-05-20` | Code generation, review, complex reasoning |

---

## API Endpoints

### Question Generation
- `POST /api/v1/generate` — Generate single question
- `GET /api/v1/generate/stream` — Stream generation progress (SSE)
- `POST /api/v1/context` — Get PDF context for topic

### Provenance (Step 4)
- `GET /api/v1/question/{id}/explain` — Get question provenance

### Document Management
- `POST /api/v1/upload` — Upload PDF
- `GET /api/v1/documents` — List uploaded documents
- `GET /api/v1/suggestions` — Get topic suggestions

### Paper Generation
- `POST /api/v1/paper/template` — Create paper template
- `POST /api/v1/paper/generate/{paper_id}` — Generate paper
- `GET /api/v1/paper/generate/{paper_id}/stream` — Stream paper generation
- `GET /api/v1/paper/{paper_id}` — Retrieve generated paper
- `GET /api/v1/paper/{paper_id}/export` — Export as PDF/Markdown

### Metrics & Analytics
- `GET /api/v1/metrics` — Generation pipeline metrics
- `GET /api/v1/analytics` — Question bank analytics

### DAV — Data Analytics & Visualization (Step 6)
- `GET  /api/v1/dav/overview` — Summary stats and difficulty distribution
- `GET  /api/v1/dav/bloom-distribution` — Bloom level breakdown + heatmap
- `GET  /api/v1/dav/topic-coverage` — Syllabus coverage vs gap topics
- `GET  /api/v1/dav/difficulty-trends` — Daily/weekly generation trends
- `GET  /api/v1/dav/copo-matrix` — NBA CO×PO attainment matrix
- `GET  /api/v1/dav/eda-report` — Full exploratory data analysis report
- `POST /api/v1/dav/clean` — Data cleaning pass (dedup, standardize, fill)
- `GET  /api/v1/dav/paper-balance` — Bloom balance checker vs ideal distribution
- `GET  /api/v1/dav/similarity?threshold=0.55` — Similar/duplicate question detection
- `GET  /api/v1/dav/feedback` — Student performance feedback analysis
- `POST /api/v1/dav/feedback` — Submit student feedback records
- `GET  /api/v1/dav/copo-consistency` — CO/PO mapping consistency validation

---

## Architecture

### Multi-Agent Pipeline

```
Bloom Analyzer → Scout → [Cache Check]
                         ↓
                  Code Author → Executor → Question Author
                         ↓                      ↓
                  Theory Author ──────────────→ Reviewer
                                                 ↓
                                          Pedagogy Tagger
                                                 ↓
                                            Guardian
                                                 ↓
                                            Archivist
```

### Agent Responsibilities

- **Bloom Analyzer**: Detects Bloom's taxonomy level (Step 2)
- **Scout**: Retrieves context from RAG, checks cache, detects topic type
- **Code Author**: Generates verification code first
- **Executor**: Runs code, captures output
- **Question Author**: Writes question from code result
- **Theory Author**: Handles conceptual topics (no code)
- **Reviewer**: Parallel critic + validator
- **Pedagogy Tagger**: Assigns CO/PO tags (Step 3)
- **Guardian**: Validates against syllabus (Step 5)
- **Archivist**: Saves to question bank

### DAV Data Flow

```
SQLite question_bank.db + student_feedback table
         ↓
app/services/dav_service.py
  ├── clean_data()              → dedup, standardize, fill nulls
  ├── get_overview()            → summary stats, variance, Bloom balance
  ├── get_bloom_distribution()  → bar data + heatmap matrix
  ├── get_topic_coverage()      → coverage % vs config/syllabus.yaml
  ├── get_difficulty_trends()   → daily/weekly time series
  ├── get_copo_matrix()         → NBA attainment levels
  ├── get_eda_report()          → full statistical EDA
  ├── get_paper_balance()       → actual vs ideal Bloom distribution
  ├── get_similarity_report()   → Jaccard similarity, duplicate detection
  ├── submit_feedback()         → store student response records
  ├── get_feedback_analysis()   → accuracy, weak topics, difficult questions
  └── get_copo_consistency()    → Bloom→CO→PO rule validation
         ↓
/api/v1/dav/* endpoints (12 total)
         ↓
frontend/components/DAVModule.tsx — 10 tabs
  (Recharts: Bar, Pie, Line, Radar, Cell heatmap)
```

### Technology Stack

**Backend:**
- FastAPI (REST API & SSE streaming)
- LangGraph (multi-agent orchestration)
- LangChain (LLM integration)
- ChromaDB (vector store)
- SQLite (question bank)
- **Google Gemini** via OpenAI-compatible endpoint (primary LLM)
- OpenAI GPT-4o (optional fallback)

**Frontend:**
- React 18 + TypeScript
- Vite (build tool)
- TailwindCSS (styling)
- Recharts (DAV charts — Bar, Pie, Line, Radar)
- React Markdown (question rendering)

---

## Database Schema

```sql
CREATE TABLE templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT,
    difficulty TEXT,
    question_text TEXT,
    answer_text TEXT,
    explanation_text TEXT,
    verification_code TEXT,
    source_type TEXT,
    source_urls TEXT,
    full_json TEXT,
    created_at REAL,
    -- Step 2: Bloom-Adaptive RAG
    bloom_level INTEGER,
    retrieved_chunk_ids TEXT,
    retrieved_doc_ids TEXT,
    -- Step 3: Pedagogy Tagger
    course_outcome TEXT,
    program_outcome TEXT
);

-- Step 6: Student feedback (auto-created by DAV service)
CREATE TABLE IF NOT EXISTS student_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER,
    student_id TEXT,
    score INTEGER,           -- 0–100
    time_taken_sec INTEGER,
    correct INTEGER,         -- 1 or 0
    difficulty_felt TEXT,    -- 'Easy', 'Medium', 'Hard'
    created_at REAL
);
```

> Both tables auto-migrate / auto-create on startup — no manual setup needed.

---

## Code Structure

```
.
├── api.py                          # FastAPI application + DAV endpoints
├── main.py                         # CLI interface
├── requirements.txt
├── config/
│   ├── syllabus.yaml               # Guardian + DAV coverage config
│   └── ...
├── app/
│   ├── core/
│   │   └── question_bank.py        # Database operations + auto-migration
│   └── services/
│       ├── graph_agent.py          # LangGraph multi-agent pipeline
│       ├── dav_service.py          # DAV analytics & EDA engine (Step 6)
│       ├── guardian.py             # Syllabus validator (Step 5)
│       ├── metrics.py              # Generation pipeline metrics
│       ├── paper_generator.py      # Exam paper generation
│       └── rag_service.py          # Bloom-adaptive RAG engine (Step 2)
├── frontend/
│   ├── App.tsx                     # Nav + tab routing (includes Analytics tab)
│   ├── components/
│   │   ├── DAVModule.tsx           # DAV dashboard — 10-tab chart UI (Step 6)
│   │   ├── GenerationModule.tsx    # Question generation UI
│   │   ├── PaperGeneratorModule.tsx
│   │   ├── KnowledgeHubModule.tsx
│   │   ├── QuestionBankModule.tsx
│   │   ├── ProvenanceModal.tsx     # Provenance viewer (Step 4)
│   │   └── IngestModule.tsx
│   ├── services/
│   │   └── api.ts
│   └── types.ts
└── Documentation/
    └── REPORT_*.md
```

---

## Troubleshooting

**1. API key not set**
```bash
# Gemini (recommended)
echo "GEMINI_API_KEY=your-key-here" >> .env

# Or OpenAI fallback
echo "OPENAI_API_KEY=your-key-here" >> .env
```
Get a free Gemini key at [aistudio.google.com](https://aistudio.google.com) → API Keys.

**2. ChromaDB not initialized**
```bash
rm -rf chroma_db/
python main.py --upload path/to/pdf
```

**3. Frontend can't connect to backend**
- Ensure backend is running on port 8000
- Check CORS settings in `api.py`

**4. Guardian rejects all questions**
- Set `enabled: true` in `config/syllabus.yaml`
- Verify topic is listed under a unit's topics
- Lower `similarity_threshold` for looser matching

**5. DAV charts show no data**
- Generate at least a few questions first
- Confirm backend is running: `curl http://localhost:8000/api/v1/dav/overview`
- Run data cleaning: `curl -X POST http://localhost:8000/api/v1/dav/clean`

**6. Balance tab shows no rating**
- Requires at least 1 question in the bank — the balance score is computed from existing data

**7. Similarity tab shows no pairs**
- Need at least 2 questions; try lowering the threshold slider below 55%

**8. Feedback tab shows "No feedback yet"**
- Click **Load Sample Feedback Data** in the UI to inject mock data, or POST records to `/api/v1/dav/feedback`

**9. Consistency tab shows 100% with no issues**
- Expected when the DB is empty or all tags are correctly assigned; generate questions with `ENABLE_PEDAGOGY_TAGGER=true` to populate CO/PO data

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with LangGraph, LangChain, and FastAPI
- LLMs powered by Google Gemini (2.0 Flash / 2.5 Flash)
- Vector embeddings by Sentence Transformers
- Charts rendered with Recharts
- Inspired by the code-first generation paradigm

---

**Version**: 3.1.0 (full DAV spec — 10 tabs, 12 endpoints)
**Status**: Production Ready
**Last Updated**: June 2025
