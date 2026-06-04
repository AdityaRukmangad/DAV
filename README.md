# Tribunal: AI Questionnaire Generator

An intelligent, multi-agent system for generating high-quality evaluation questions with verification code, provenance tracking, and syllabus validation.

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

## Installation

### Prerequisites
- Python 3.9+
- Node.js 18+
- Git

### Backend Setup

```bash
# Clone repository
git clone https://github.com/yourusername/AI-Questionnaire-Generator.git
cd AI-Questionnaire-Generator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export GROQ_API_KEY="your-groq-api-key"
export ENABLE_PEDAGOGY_TAGGER="false"  # Optional
export ENABLE_GUARDIAN="false"         # Optional

# Initialize database
python -c "from app.core.question_bank import init_db; init_db()"

# Start backend server
uvicorn api:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Access the UI at `http://localhost:5173`

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
# Get provenance data for question ID 1
curl http://localhost:8000/api/v1/question/1/explain
```

### 4. Generate a Paper

```bash
python main.py --paper templates/midterm_template.json
```

## Configuration

### Syllabus Configuration (Guardian)

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

### Environment Variables

```bash
# Required
GROQ_API_KEY=your-api-key

# Optional Features (default: false)
ENABLE_PEDAGOGY_TAGGER=true   # Enable CO/PO tagging
ENABLE_GUARDIAN=true          # Enable syllabus validation

# Model Configuration
DEFAULT_LLM_MODEL=llama-3.3-70b-versatile
FAST_LLM_MODEL=llama-3.1-8b-instant
```

## API Endpoints

### Question Generation
- `POST /api/v1/generate` - Generate single question
- `GET /api/v1/generate/stream` - Stream generation progress (SSE)
- `POST /api/v1/context` - Get PDF context for topic

### Provenance (Step 4)
- `GET /api/v1/question/{id}/explain` - Get question provenance

### Document Management
- `POST /api/v1/upload` - Upload PDF
- `GET /api/v1/documents` - List uploaded documents
- `GET /api/v1/suggestions` - Get topic suggestions

### Paper Generation
- `POST /api/v1/paper/template` - Create paper template
- `POST /api/v1/paper/generate/{paper_id}` - Generate paper
- `GET /api/v1/paper/generate/{paper_id}/stream` - Stream paper generation
- `GET /api/v1/paper/{paper_id}` - Retrieve generated paper
- `GET /api/v1/paper/{paper_id}/export` - Export as PDF/Markdown

### Metrics & Analytics
- `GET /api/v1/metrics` - Generation metrics
- `GET /api/v1/analytics` - Question bank analytics

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

### Technology Stack

**Backend:**
- FastAPI (REST API & SSE streaming)
- LangGraph (multi-agent orchestration)
- LangChain (LLM integration)
- ChromaDB (vector store)
- SQLite (question bank)
- Groq (LLM provider)

**Frontend:**
- React + TypeScript
- Vite (build tool)
- TailwindCSS (styling)
- React Markdown (rendering)

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
```

## Development

### Running Tests

```bash
# Backend tests
pytest

# Quality verification
python verify_quality.py
```

### Code Structure

```
.
├── api.py                      # FastAPI application
├── main.py                     # CLI interface
├── app/
│   ├── core/
│   │   └── question_bank.py    # Database operations
│   ├── services/
│   │   ├── graph_agent.py      # LangGraph pipeline
│   │   ├── guardian.py         # Step 5: Syllabus validator
│   │   └── paper_generator.py  # Paper generation
│   ├── rag.py                  # RAG engine
│   └── tools/
│       └── utils.py            # Utilities
├── config/
│   ├── prompts.yaml            # LLM prompts
│   ├── syllabus.yaml           # Guardian config
│   └── tags.yaml               # CO/PO mappings
├── frontend/
│   ├── components/
│   │   ├── GenerationModule.tsx
│   │   └── ProvenanceModal.tsx  # Step 4: Provenance UI
│   ├── services/
│   │   └── api.ts              # API client
│   └── types.ts                # TypeScript types
└── docs/
    └── REPORT_*.md             # Project documentation
```

## Troubleshooting

### Common Issues

**1. GROQ_API_KEY not set**
```bash
export GROQ_API_KEY="your-key-here"
```

**2. ChromaDB not initialized**
```bash
rm -rf chroma_db/
python main.py --upload path/to/pdf
```

**3. Frontend can't connect to backend**
- Ensure backend is running on port 8000
- Check CORS settings in `api.py`

**4. Guardian rejects all questions**
- Check `config/syllabus.yaml` enabled: true
- Verify topic is in syllabus units
- Lower similarity_threshold for looser matching

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
- LLMs powered by Groq (Llama 3.3 70B)
- Vector embeddings by Sentence Transformers
- Inspired by code-first generation paradigm

## Citation

If you use this project in your research, please cite:

```bibtex
@software{tribunal_questionnaire_generator,
  title={Tribunal: AI Questionnaire Generator},
  author={Your Name},
  year={2024},
  url={https://github.com/yourusername/AI-Questionnaire-Generator}
}
```

---

**Version**: 2.0.0 (with Provenance & Guardian)
**Status**: Production Ready
**Last Updated**: January 2025
