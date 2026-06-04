export interface QuestionData {
  question: string;
  answer: string;
  explanation: string;
  options?: string[];
  verification_code?: string;
  difficulty_rating: string;
  source?: string;
  source_urls?: string[];
  source_pages?: number[];  // Page numbers from PDF
  source_filename?: string;  // PDF filename
  computed_answer?: string;
  answer_warning?: string;
  quality_score?: number;  // Critic score 0-10
  question_id?: number;  // Database ID for provenance lookup
  bloom_level?: number | string;  // Bloom's taxonomy level
  course_outcome?: string;  // CO tags
  program_outcome?: string;  // PO tags
  unit_number?: number;
  unit_name?: string;
  question_type?: string;
  co?: string;
  topic?: string;
}

export interface UploadedDocument {
  filename: string;
  path: string;
  chunks: number;
  hash: string;
}

export interface GenerationResponse {
  status: string;
  data: QuestionData;
  meta: {
    duration_seconds: number;
    engine: string;
  };
}

export interface IngestionStats {
  chunk_count: number;
  total_pages: number;
  success: boolean;
  error_message?: string;
  file_hash: string;
  processing_time_ms: number;
}

export interface UploadResponse {
  filename: string;
  status: string;
  ingestion: IngestionStats;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';
  message: string;
}

// Topic Suggestions
export interface TopicSuggestion {
  topic: string;
  examples: string[];
}
export interface PDFSuggestion {
  filename: string;
  unit_name?: string;
  unit_number?: number;
  suggestions: TopicSuggestion[];
  count: number;
  co_mapping?: string[];
  bloom_levels?: string[];
}
// Paper Generator Types
export interface QuestionSpec {
  topic: string;
  question_type: 'short' | 'long' | 'mcq' | 'numerical';
  difficulty: 'Easy' | 'Medium' | 'Hard';
  marks: number;
}

export interface PaperSection {
  name: string;
  instructions?: string;
  questions: QuestionSpec[];
  section_type?: 'short' | 'long' | 'mcq' | 'numerical' | 'mixed';
}

export interface PaperTemplate {
  title: string;
  subject: string;
  duration_minutes: number;
  total_marks: number;
  instructions: string[];
  sections: PaperSection[];
}

// Backend returns question data directly (not nested in spec)
export interface GeneratedQuestion {
  question_number: number;
  part_of_section: string;
  topic: string;
  question_type: 'short' | 'long' | 'mcq' | 'numerical';
  difficulty: 'Easy' | 'Medium' | 'Hard';
  marks: number;
  parts_marks: Array<{ part: string; marks: number; description: string }>;
  question_text: string;  // Backend uses question_text
  answer: string;
  explanation: string;
  verification_code?: string;
  tags?: string[];
}

export interface GeneratedSection {
  name: string;
  instructions?: string;
  questions: GeneratedQuestion[];
}

export interface GeneratedPaper {
  paper_id: string;
  title: string;
  subject: string;
  duration_minutes: number;
  total_marks: number;
  instructions: string[];
  sections: GeneratedSection[];
  generated_at: string;
}

export interface PaperCreateResponse {
  paper_id: string;
  status: string;
  template: PaperTemplate;
}

export interface PaperGenerateResponse {
  status: string;
  paper: GeneratedPaper;
  generation_time_seconds: number;
}

// Provenance & Explainability Types (Step 4)
export interface SourceChunk {
  chunk_id: string;
  content_preview: string;
  page: number | string;
}

export interface SourceDocument {
  doc_id: string;
  chunk_count: number;
  chunks: SourceChunk[];
}

export interface ProvenanceData {
  question_id: number;
  question_text: string;
  answer: string;
  topic: string;
  difficulty: string;
  bloom_level: number | null;
  course_outcome: string | null;
  program_outcome: string | null;
  source_type: string;
  source_documents: SourceDocument[];
  total_chunks_used: number;
}

export interface SyllabusInfo {
  course_info: {
    code: string;
    name: string;
    semester: number | string;
    credits?: number | string;
    category?: string;
  };
  course_outcomes: { code: string; description: string }[];
  co_po_mapping?: Record<string, Record<string, number>>;
  units: {
    unit_number: number;
    unit_name: string;
    co_mapping: string[];
    topics: {
      name: string;
      subtopics?: string[];
      bloom_levels?: string[];
    }[];
  }[];
}

export interface PYQPapersResponse {
  patterns_summary?: {
    total_questions?: number;
    unique_topics?: number;
    total_papers_analyzed?: number;
    total_questions_analyzed?: number;
    co_patterns?: Record<
      string,
      {
        question_types?: Record<string, number>;
        marks_distribution?: Record<string, number>;
      }
    >;
  };
  papers: PYQPaper[];
}

export interface PYQPaper {
  exam_name?: string;
  academic_year?: string;
  pdf_url?: string;
  file_url?: string;
  url?: string;
  link?: string;
  stats?: {
    total_questions: number;
    total_marks: number;
    unique_cos: number;
    type_distribution?: Record<string, number>;
    difficulty_distribution?: Record<string, number>;
    co_distribution?: Record<string, number>;
  };
  total_questions?: number;
  total_marks?: number;
  unique_cos?: number;
  type_distribution?: Record<string, number>;
  difficulty_distribution?: Record<string, number>;
  co_distribution?: Record<string, number>;
}