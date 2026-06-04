import {
  GenerationResponse,
  UploadResponse,
  UploadedDocument,
  PaperTemplate,
  PaperCreateResponse,
  PaperGenerateResponse,
  GeneratedPaper,
  TopicSuggestion,
  ProvenanceData,
  PDFSuggestion
} from '../types';

// Configuration: Point this to your Python/Node/Go backend
// Vite exposes env vars as import.meta.env.VITE_*
const API_BASE = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000/api/v1';

// MOCK DATA for demonstration when backend is offline
const MOCK_QUESTION: GenerationResponse = {
  status: "success",
  data: {
    difficulty_rating: "Expert",
    question: "Analyze the computational complexity of the Transformer attention mechanism given a sequence length N and embedding dimension d. \n\nDerive the specific matrix multiplication costs for Query, Key, and Value projections, and the subsequent Scaled Dot-Product Attention.",
    answer: "The complexity is O(N^2 * d + N * d^2).",
    explanation: "1. Q, K, V Projections: For each of N tokens, we project to dimension d. Matrix size is (N, d) x (d, d). Cost: O(N * d^2) for each of Q, K, V.\n2. Attention Scores (Q * K^T): (N, d) x (d, N) = (N, N). Cost: O(N^2 * d).\n3. Weighted Sum (Scores * V): (N, N) x (N, d) = (N, d). Cost: O(N^2 * d).\n\nDominant terms are O(N^2 * d) (quadratic in sequence length) and O(N * d^2) (linear in sequence length but quadratic in embedding).",
    verification_code: "def attention_complexity(N, d):\n    # Projections (Q, K, V)\n    proj_cost = 3 * (N * (d**2))\n    \n    # Q * K^T (N x d) * (d x N) -> (N x N)\n    score_calc = (N**2) * d\n    \n    # Softmax * V (N x N) * (N x d) -> (N x d)\n    weighted_sum = (N**2) * d\n    \n    total = proj_cost + score_calc + weighted_sum\n    return total\n\n# Verification\nN, d = 1000, 512\nprint(f\"Ops: {attention_complexity(N, d):.2e}\")",
    source: "Attention Is All You Need",
    source_urls: ["https://arxiv.org/abs/1706.03762"],
    computed_answer: "O(N²d)",
    options: []
  },
  meta: {
    duration_seconds: 0.84,
    engine: "TRIBUNAL-V5"
  }
};

const MOCK_UPLOAD: UploadResponse = {
  filename: "manual.pdf",
  status: "success",
  ingestion: {
    chunk_count: 142,
    total_pages: 12,
    success: true,
    file_hash: "a1b2c3d4e5f6",
    processing_time_ms: 450
  }
};

/**
 * ENDPOINT: POST /generate
 * Description: Generates an evaluation question based on topic and difficulty.
 * 
 * Request Body (JSON):
 * {
 *   "topic": "string",
 *   "difficulty": "Easy" | "Medium" | "Hard" | "Expert" | "PhD"
 * }
 * 
 * Expected Response (JSON): GenerationResponse (see types.ts)
 */
export const generateQuestion = async (topic: string, difficulty: string, syllabusContext?: string): Promise<GenerationResponse> => {
  try {
    console.log(`[API] Fetching ${API_BASE}/generate...`);
    const response = await fetch(`${API_BASE}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        topic, 
        difficulty,
        ...(syllabusContext && { syllabus_context: syllabusContext })
      }),
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    return response.json();
  } catch (error) {
    console.warn(`[API] Backend unreachable at ${API_BASE}/generate. Using Mock Data.`);
    await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate network latency
    
    // Return a deep copy with modified data based on input to make it feel real
    const mock = JSON.parse(JSON.stringify(MOCK_QUESTION));
    mock.data.difficulty_rating = difficulty;
    if (topic) mock.data.question = `[${topic.toUpperCase()}] ` + mock.data.question;
    return mock;
  }
};

/**
 * ENDPOINT: POST /upload
 * Description: Uploads a PDF for ingestion.
 *
 * Request Body: Multipart/Form-Data
 * Field "file": Binary PDF data
 *
 * Expected Response (JSON): UploadResponse (see types.ts)
 */
export const uploadPDF = async (file: File): Promise<UploadResponse> => {
  try {
    const formData = new FormData();
    formData.append('file', file);

    console.log(`[API] Uploading to ${API_BASE}/upload...`);
    const response = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Upload failed');
    }

    return response.json();
  } catch (error) {
    console.warn(`[API] Backend unreachable at ${API_BASE}/upload. Using Mock Data.`);
    await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate processing
    const mock = JSON.parse(JSON.stringify(MOCK_UPLOAD));
    mock.filename = file.name;
    return mock;
  }
};

/**
 * ENDPOINT: GET /suggestions
 * Description: Get topic suggestions from uploaded PDF content
 * Returns objects with {topic, examples} structure
 */
export const getSuggestions = async (): Promise<TopicSuggestion[]> => {
  try {
    console.log(`[API] Fetching ${API_BASE}/suggestions...`);
    const response = await fetch(`${API_BASE}/suggestions`);

    if (!response.ok) {
      throw new Error('Failed to fetch suggestions');
    }

    const data = await response.json();
    return data.suggestions || [];
  } catch (error) {
    console.warn(`[API] Backend unreachable at ${API_BASE}/suggestions. Using defaults.`);
    return [
      { topic: "Information Gain", examples: ["Information gain calculation", "Information gain trace"] },
      { topic: "Decision Tree", examples: ["Decision tree pruning", "ID3 algorithm"] },
      { topic: "Entropy", examples: ["Entropy calculation", "Entropy formula"] },
    ];
  }
};

/**
 * ENDPOINT: GET /suggestions-by-pdf
 * Description: Get topic suggestions grouped by PDF file
 * Returns array of {filename, suggestions, count}
 */
export const getSuggestionsByPDF = async (): Promise<PDFSuggestion[]> => {
  try {
    console.log(`[API] Fetching ${API_BASE}/suggestions-by-pdf...`);
    const response = await fetch(`${API_BASE}/suggestions-by-pdf`);

    if (!response.ok) {
      throw new Error('Failed to fetch PDF suggestions');
    }

    const data = await response.json();
    return data.pdf_suggestions || [];
  } catch (error) {
    console.warn(`[API] Backend unreachable at ${API_BASE}/suggestions-by-pdf.`);
    return [];
  }
};

/**
 * ENDPOINT: POST /context
 * Description: Get PDF context for a topic (similar to CLI --show-context)
 */
export const getPDFContext = async (topic: string): Promise<{context: string | null, chunks: number}> => {
  try {
    console.log(`[API] Fetching PDF context for: ${topic}`);
    const response = await fetch(`${API_BASE}/context`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ topic }),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch context');
    }

    const data = await response.json();
    return { context: data.context, chunks: data.chunks || 0 };
  } catch (error) {
    console.warn(`[API] Backend unreachable at ${API_BASE}/context.`);
    return { context: null, chunks: 0 };
  }
};

/**
 * ENDPOINT: GET /documents
 * Description: Get list of uploaded/ingested documents
 */
export const getDocuments = async (): Promise<UploadedDocument[]> => {
  try {
    console.log(`[API] Fetching ${API_BASE}/documents...`);
    const response = await fetch(`${API_BASE}/documents`);

    if (!response.ok) {
      throw new Error('Failed to fetch documents');
    }

    const data = await response.json();
    return data.documents || [];
  } catch (error) {
    console.warn(`[API] Backend unreachable at ${API_BASE}/documents.`);
    return [];
  }
};
/**
 * ENDPOINT: DELETE /documents/{filename}
 * Description: Deletes an uploaded PDF document.
 */
export const deleteDocument = async (filename: string): Promise<{success: boolean, message: string}> => {
  try {
    console.log(`[API] Deleting document: ${filename}`);
    const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error('Failed to delete document');
    }

    return response.json();
  } catch (error) {
    console.warn(`[API] Backend unreachable for delete operation.`);
    return { success: false, message: 'Backend unreachable' };
  }
};
// ============ PAPER GENERATOR API ============

/**
 * ENDPOINT: POST /paper/template
 * Description: Create a paper template for question generation
 */
export const createPaperTemplate = async (template: PaperTemplate): Promise<PaperCreateResponse> => {
  try {
    console.log(`[API] Creating paper template at ${API_BASE}/paper/template...`);
    const response = await fetch(`${API_BASE}/paper/template`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(template),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server error: ${response.status}`);
    }

    return response.json();
  } catch (error: any) {
    console.error(`[API] Failed to create paper template:`, error);
    throw error;
  }
};

/**
 * ENDPOINT: POST /paper/generate/{paper_id}
 * Description: Generate all questions for a paper template
 */
export const generatePaper = async (paperId: string): Promise<PaperGenerateResponse> => {
  try {
    console.log(`[API] Generating paper ${paperId}...`);
    const response = await fetch(`${API_BASE}/paper/generate/${paperId}`, {
      method: 'POST',
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server error: ${response.status}`);
    }

    return response.json();
  } catch (error: any) {
    console.error(`[API] Failed to generate paper:`, error);
    throw error;
  }
};

/**
 * ENDPOINT: GET /paper/{paper_id}
 * Description: Get a generated paper by ID
 */
export const getPaper = async (paperId: string): Promise<GeneratedPaper> => {
  try {
    console.log(`[API] Fetching paper ${paperId}...`);
    const response = await fetch(`${API_BASE}/paper/${paperId}`);

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    return data.paper;
  } catch (error: any) {
    console.error(`[API] Failed to fetch paper:`, error);
    throw error;
  }
};

/**
 * ENDPOINT: GET /paper/papers
 * Description: List all generated papers
 */
export const listPapers = async (): Promise<GeneratedPaper[]> => {
  try {
    console.log(`[API] Fetching papers list...`);
    const response = await fetch(`${API_BASE}/paper/papers`);

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    return data.papers || [];
  } catch (error) {
    console.warn(`[API] Backend unreachable at ${API_BASE}/paper/papers.`);
    return [];
  }
};

/**
 * ENDPOINT: DELETE /paper/{paper_id}
 * Description: Delete a generated paper
 */
export const deletePaper = async (paperId: string): Promise<{success: boolean, message: string}> => {
  try {
    console.log(`[API] Deleting paper ${paperId}...`);
    const response = await fetch(`${API_BASE}/paper/${paperId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error('Failed to delete paper');
    }

    return response.json();
  } catch (error) {
    console.warn(`[API] Backend unreachable for delete operation.`);
    return { success: false, message: 'Backend unreachable' };
  }
};

/**
 * ENDPOINT: PATCH /paper/{paper_id}
 * Description: Update paper title
 */
export const updatePaperTitle = async (paperId: string, title: string): Promise<{success: boolean, message: string}> => {
  try {
    console.log(`[API] Updating paper ${paperId} title...`);
    const response = await fetch(`${API_BASE}/paper/${paperId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ title }),
    });

    if (!response.ok) {
      throw new Error('Failed to update paper');
    }

    return response.json();
  } catch (error) {
    console.warn(`[API] Backend unreachable for update operation.`);
    return { success: false, message: 'Backend unreachable' };
  }
};

/**
 * ENDPOINT: GET /paper/{paper_id}/export?format=markdown|pdf&with_answers=true|false
 * Description: Export paper as markdown or PDF
 */
export interface PdfExportSettings {
  course_code?: string;
  semester?: string;
  academic_year?: string;
  ug_pg?: string;
  faculty?: string;
  department?: string;
}

export const exportPaper = async (
  paperId: string,
  format: 'markdown' | 'pdf' = 'markdown',
  withAnswers: boolean = false,
  pdfSettings?: PdfExportSettings
): Promise<Blob | string> => {
  try {
    console.log(`[API] Exporting paper ${paperId} as ${format}...`);

    // Build query params
    const params = new URLSearchParams({
      format,
      with_answers: String(withAnswers)
    });

    // Add PDF settings if provided
    if (format === 'pdf' && pdfSettings) {
      if (pdfSettings.course_code) params.append('course_code', pdfSettings.course_code);
      if (pdfSettings.semester) params.append('semester', pdfSettings.semester);
      if (pdfSettings.academic_year) params.append('academic_year', pdfSettings.academic_year);
      if (pdfSettings.ug_pg) params.append('ug_pg', pdfSettings.ug_pg);
      if (pdfSettings.faculty) params.append('faculty', pdfSettings.faculty);
      if (pdfSettings.department) params.append('department', pdfSettings.department);
    }

    const response = await fetch(`${API_BASE}/paper/${paperId}/export?${params}`, {
      headers: format === 'pdf' ? { 'Accept': 'application/pdf' } : { 'Accept': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(`Export failed: ${response.status}`);
    }

    if (format === 'pdf') {
      return response.blob();
    } else {
      const data = await response.json();
      return data.markdown;
    }
  } catch (error: any) {
    console.error(`[API] Failed to export paper:`, error);
    throw error;
  }
};

/**
 * ENDPOINT: GET /paper/{paper_id}/answer-key
 * Description: Get separate answer key for a paper
 */
export const getAnswerKey = async (paperId: string): Promise<string> => {
  try {
    console.log(`[API] Fetching answer key for ${paperId}...`);
    const response = await fetch(`${API_BASE}/paper/${paperId}/answer-key`);

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    return data.answer_key;
  } catch (error: any) {
    console.error(`[API] Failed to fetch answer key:`, error);
    throw error;
  }
};

// ============ STREAMING API ============

export interface PaperStreamEvent {
  type: 'start' | 'section_start' | 'question_start' | 'question_complete' |
        'question_error' | 'section_complete' | 'finalizing' | 'complete' |
        'result' | 'error' | 'done';
  message: string;
  progress?: number;
  total_questions?: number;
  section_index?: number;
  section_name?: string;
  question_number?: number;
  topic?: string;
  difficulty?: string;
  preview?: string;
  from_cache?: boolean;
  questions_in_section?: number;
  paper_id?: string;
  paper?: GeneratedPaper;
  error?: string;
}

/**
 * ENDPOINT: GET /paper/generate/{paper_id}/stream
 * Description: Stream paper generation progress via SSE
 * Returns an EventSource that emits PaperStreamEvent objects
 */
export const streamPaperGeneration = (
  paperId: string,
  onEvent: (event: PaperStreamEvent) => void,
  onError?: (error: Error) => void,
  onComplete?: (paper: GeneratedPaper | null) => void
): (() => void) => {
  const url = `${API_BASE}/paper/generate/${paperId}/stream`;
  console.log(`[API] Opening SSE stream: ${url}`);

  const eventSource = new EventSource(url);
  let paper: GeneratedPaper | null = null;

  eventSource.onmessage = (event) => {
    try {
      const data: PaperStreamEvent = JSON.parse(event.data);
      console.log(`[SSE] Event:`, data.type, data.message);

      // Capture the final paper if we get a result event
      if (data.type === 'result' && data.paper) {
        paper = data.paper;
      }

      onEvent(data);

      // Close on completion or error
      if (data.type === 'done' || data.type === 'error') {
        eventSource.close();
        if (onComplete) {
          onComplete(paper);
        }
      }
    } catch (e) {
      console.warn('[SSE] Failed to parse event:', event.data);
    }
  };

  eventSource.onerror = (err) => {
    console.error('[SSE] Connection error:', err);
    eventSource.close();
    if (onError) {
      onError(new Error('Stream connection failed'));
    }
  };

  // Return cleanup function
  return () => {
    console.log('[SSE] Closing stream');
    eventSource.close();
  };
};

// ============ RUBRIC & ANALYTICS API ============

export interface RubricCriterion {
  criterion: string;
  marks: number;
  description: string;
}

export interface QuestionRubric {
  question_number: number;
  topic: string;
  total_marks: number;
  criteria: RubricCriterion[];
  model_answer?: string;
}

export interface PaperRubric {
  paper_id: string;
  title: string;
  subject: string;
  total_marks: number;
  sections: {
    name: string;
    questions: QuestionRubric[];
  }[];
}

export interface Analytics {
  papers: {
    total: number;
    by_subject: Record<string, number>;
  };
  templates: {
    total: number;
  };
  questions: {
    total_in_bank: number;
    by_topic: { topic: string; count: number }[];
    by_difficulty: Record<string, number>;
  };
  generation: {
    total_generated: number;
    cache_hits: number;
    cache_hit_rate: number;
  };
}

/**
 * ENDPOINT: GET /paper/{paper_id}/rubric
 * Description: Get marking rubric for a paper
 */
export const getPaperRubric = async (paperId: string, format: 'json' | 'markdown' = 'json'): Promise<PaperRubric | string> => {
  try {
    console.log(`[API] Fetching rubric for ${paperId}...`);
    const response = await fetch(`${API_BASE}/paper/${paperId}/rubric?format=${format}`);

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    if (format === 'markdown') {
      return data.content;
    }
    return data.rubric;
  } catch (error: any) {
    console.error(`[API] Failed to fetch rubric:`, error);
    throw error;
  }
};

/**
 * ENDPOINT: GET /analytics
 * Description: Get analytics dashboard data
 */
export const getAnalytics = async (): Promise<Analytics> => {
  try {
    console.log(`[API] Fetching analytics...`);
    const response = await fetch(`${API_BASE}/analytics`);

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    return data.analytics;
  } catch (error: any) {
    console.error(`[API] Failed to fetch analytics:`, error);
    throw error;
  }
};

// =============================================================================
// METRICS (Observability)
// =============================================================================

export interface NodePerformance {
  calls: number;
  avg_ms: number;
  success_rate: number;
}

export interface MetricsSummary {
  total_runs: number;
  successful: number;
  failed: number;
  success_rate: number;
  avg_duration_ms: number;
}

export interface Metrics {
  summary: MetricsSummary;
  node_performance: Record<string, NodePerformance>;
  common_paths: [string, number][];
  recent_errors: { topic: string; error: string | null }[];
}

export interface SlowRun {
  run_id: string;
  topic: string;
  duration_ms: number;
  slowest_node: string;
  path: string[];
}

/**
 * ENDPOINT: GET /metrics
 * Description: Get generation metrics and performance stats
 */
export const getMetrics = async (): Promise<Metrics> => {
  try {
    console.log(`[API] Fetching metrics...`);
    const response = await fetch(`${API_BASE}/metrics`);

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    return data.metrics;
  } catch (error: any) {
    console.error(`[API] Failed to fetch metrics:`, error);
    throw error;
  }
};

/**
 * ENDPOINT: GET /metrics/slow
 * Description: Get slow generation runs
 */
export const getSlowRuns = async (thresholdMs: number = 30000): Promise<SlowRun[]> => {
  try {
    const response = await fetch(`${API_BASE}/metrics/slow?threshold_ms=${thresholdMs}`);

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    return data.slow_runs;
  } catch (error: any) {
    console.error(`[API] Failed to fetch slow runs:`, error);
    throw error;
  }
};

/**
 * ENDPOINT: POST /metrics/reset
 * Description: Reset all metrics
 */
export const resetMetrics = async (): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE}/metrics/reset`, { method: 'POST' });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }
  } catch (error: any) {
    console.error(`[API] Failed to reset metrics:`, error);
    throw error;
  }
};

/**
 * ENDPOINT: POST /config/reload
 * Description: Hot-reload prompts and tags config
 */
export const reloadConfig = async (): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE}/config/reload`, { method: 'POST' });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }
  } catch (error: any) {
    console.error(`[API] Failed to reload config:`, error);
    throw error;
  }
};

// =============================================================================
// PROVENANCE & EXPLAINABILITY (STEP 4)
// =============================================================================

/**
 * ENDPOINT: GET /question/{question_id}/explain
 * Description: Get provenance data for a question (bloom level, CO/PO, source documents)
 * READ-ONLY - no regeneration allowed
 */
export const explainQuestion = async (questionId: number): Promise<ProvenanceData> => {
  try {
    console.log(`[API] Fetching provenance for question ${questionId}...`);
    const response = await fetch(`${API_BASE}/question/${questionId}/explain`);

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Question not found');
      }
      throw new Error(`Server error: ${response.status}`);
    }

    return response.json();
  } catch (error: any) {
    console.error(`[API] Failed to fetch provenance:`, error);
    throw error;
  }
};

// =============================================================================
// KNOWLEDGE HUB - Syllabus & PYQ Papers
// =============================================================================

export interface SyllabusInfo {
  course_info: {
    name: string;
    code: string;
    semester: string;
    category: string;
  };
  units: Array<{
    unit_number: number;
    unit_name: string;
    hours: number;
    topics: Array<{
      name: string;
      subtopics: string[];
    }>;
    co_mapping: string[];
    bloom_levels: string[];
  }>;
  course_outcomes: Record<string, string>;
  co_po_mapping: Record<string, Record<string, number>>;
  total_units: number;
  credits: {
    lecture: number;
    tutorial: number;
    practical: number;
  };
}

export interface PYQPaper {
  filename: string;
  exam_name: string;
  academic_year: string;
  semester: string;
  total_questions: number;
  total_marks: number;
  duration_minutes: number;
  type_distribution: Record<string, number>;
  difficulty_distribution: Record<string, number>;
  co_distribution: Record<string, number>;
}

export interface PYQPapersResponse {
  papers: PYQPaper[];
  patterns_summary: {
    total_papers_analyzed: number;
    total_questions_analyzed: number;
    co_patterns: Record<string, {
      question_types: Record<string, number>;
      marks_distribution: Record<string, number>;
    }>;
  };
  total_papers: number;
}

/**
 * ENDPOINT: GET /knowledge-hub/syllabus
 * Description: Get complete syllabus information
 */
export const getSyllabusInfo = async (): Promise<SyllabusInfo | null> => {
  try {
    console.log(`[API] Fetching syllabus info...`);
    const response = await fetch(`${API_BASE}/knowledge-hub/syllabus`);

    if (!response.ok) {
      throw new Error('Failed to fetch syllabus');
    }

    const data = await response.json();
    if (data.error) {
      console.error('[API] Syllabus error:', data.error);
      return null;
    }
    return data;
  } catch (error) {
    console.error(`[API] Failed to fetch syllabus:`, error);
    return null;
  }
};

/**
 * ENDPOINT: GET /knowledge-hub/pyq-papers
 * Description: Get previous year question papers with statistics
 */
export const getPYQPapers = async (): Promise<PYQPapersResponse> => {
  try {
    console.log(`[API] Fetching PYQ papers...`);
    const response = await fetch(`${API_BASE}/knowledge-hub/pyq-papers`);

    if (!response.ok) {
      throw new Error('Failed to fetch PYQ papers');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`[API] Failed to fetch PYQ papers:`, error);
    return {
      papers: [],
      patterns_summary: {
        total_papers_analyzed: 0,
        total_questions_analyzed: 0,
        co_patterns: {}
      },
      total_papers: 0
    };
  }
};
