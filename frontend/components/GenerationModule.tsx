import * as React from 'react';
import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { generateQuestion, getDocuments, explainQuestion, getSyllabusInfo } from '../services/api';
import { GenerationResponse, UploadedDocument, ProvenanceData } from '../types';
import { Icons } from './ui/SystemIcons';
import CodeViewer from './ui/CodeViewer';
import ProvenanceModal from './ProvenanceModal';
import { saveQuestionToBank } from '../services/questionBank';

// Markdown component styles
const markdownComponents = {
  h1: ({ children }: any) => <h1 className="text-3xl font-display font-bold text-ink mb-4 mt-6">{children}</h1>,
  h2: ({ children }: any) => <h2 className="text-2xl font-display font-semibold text-ink mb-3 mt-5">{children}</h2>,
  h3: ({ children }: any) => <h3 className="text-xl font-display font-semibold text-ink mb-2 mt-4">{children}</h3>,
  h4: ({ children }: any) => <h4 className="text-lg font-display font-medium text-ink mb-2 mt-3">{children}</h4>,
  p: ({ children }: any) => <p className="text-ink leading-relaxed mb-4">{children}</p>,
  ul: ({ children }: any) => <ul className="list-disc list-inside mb-4 space-y-1 text-ink">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal list-inside mb-4 space-y-1 text-ink">{children}</ol>,
  li: ({ children }: any) => <li className="text-ink">{children}</li>,
  strong: ({ children }: any) => <strong className="font-bold text-ink">{children}</strong>,
  em: ({ children }: any) => <em className="italic">{children}</em>,
  code: ({ children, className }: any) => {
    const isInline = !className;
    return isInline ? (
      <code className="bg-warm-100 text-accent px-1.5 py-0.5 rounded text-sm font-mono">{children}</code>
    ) : (
      <code className="block bg-warm-50 p-4 rounded-xl text-sm font-mono overflow-x-auto">{children}</code>
    );
  },
  pre: ({ children }: any) => <pre className="bg-warm-50 p-4 rounded-xl overflow-x-auto mb-4 border border-warm-100">{children}</pre>,
  table: ({ children }: any) => (
    <div className="overflow-x-auto mb-6 rounded-xl border border-warm-200">
      <table className="min-w-full divide-y divide-warm-200">{children}</table>
    </div>
  ),
  thead: ({ children }: any) => <thead className="bg-warm-100">{children}</thead>,
  tbody: ({ children }: any) => <tbody className="bg-white divide-y divide-warm-100">{children}</tbody>,
  tr: ({ children }: any) => <tr className="hover:bg-warm-50 transition-colors">{children}</tr>,
  th: ({ children }: any) => <th className="px-4 py-3 text-left text-xs font-bold text-ink uppercase tracking-wider">{children}</th>,
  td: ({ children }: any) => <td className="px-4 py-3 text-sm text-ink font-mono">{children}</td>,
  blockquote: ({ children }: any) => (
    <blockquote className="border-l-4 border-accent pl-4 italic text-ink-light my-4">{children}</blockquote>
  ),
  hr: () => <hr className="my-6 border-warm-200" />,
};

const DIFFICULTIES = ['Easy', 'Medium', 'Hard'];

interface GenerationModuleProps {
  onGenerationComplete?: (data: GenerationResponse) => void;
  onNavigateToIngest?: () => void;
}

const GenerationModule: React.FC<GenerationModuleProps> = ({
  onGenerationComplete,
  onNavigateToIngest
}) => {
  const [topic, setTopic] = useState('');
  const [difficulty, setDifficulty] = useState('Medium');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<GenerationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [syllabusContext, setSyllabusContext] = useState<string>('');

  // Provenance Modal State (Step 4)
  const [showProvenance, setShowProvenance] = useState(false);
  const [provenanceData, setProvenanceData] = useState<ProvenanceData | null>(null);
  const [provenanceLoading, setProvenanceLoading] = useState(false);
  const [provenanceError, setProvenanceError] = useState<string | null>(null);

  // Fetch uploaded documents on mount
  useEffect(() => {
    const fetchDocs = async () => {
      const docs = await getDocuments();
      setDocuments(docs);
    };
    fetchDocs();
  }, []);

  // Fetch syllabus context on mount
  useEffect(() => {
    const fetchSyllabusTopics = async () => {
      try {
        const syllabus = await getSyllabusInfo();
        let fullSyllabusText = '';

        // Build syllabus context text and flatten topics
        if (syllabus?.units && Array.isArray(syllabus.units)) {
          syllabus.units.forEach((unit: any) => {
            fullSyllabusText += `Unit ${unit.unit_number}: ${unit.unit_name}\n`;
            if (unit.topics && Array.isArray(unit.topics)) {
              unit.topics.forEach((topic: any) => {
                if (topic.name) {
                  fullSyllabusText += `- ${topic.name}\n`;
                }
                if (topic.subtopics && Array.isArray(topic.subtopics)) {
                  topic.subtopics.forEach((subtopic: string) => {
                    fullSyllabusText += `  • ${subtopic}\n`;
                  });
                }
              });
            }
            fullSyllabusText += '\n';
          });
        }
        setSyllabusContext(fullSyllabusText);
      } catch (error) {
        console.error('Failed to load syllabus topics:', error);
      }
    };
    fetchSyllabusTopics();
  }, []);

  // Auto-resize textarea
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [topic]);

  const handleGenerate = async (selectedTopic?: string) => {
    const topicToUse = selectedTopic || topic;
    if (!topicToUse.trim()) return;

    if (selectedTopic) setTopic(selectedTopic);

    setLoading(true);
    setError(null);
    setData(null);

    // Create abort controller for cancellation
    const controller = new AbortController();
    setAbortController(controller);

    try {
      const res = await generateQuestion(topicToUse, difficulty, syllabusContext);
      if (!controller.signal.aborted) {
        setData(res);
        if (onGenerationComplete) {
          onGenerationComplete(res);
        }
        // Save to question bank
        if (res.data) {
          const unitNumber = (res.data.unit_number as number | undefined) ?? 1;
          const unitName = res.data.unit_name || `Unit ${unitNumber}`;
          const bloom = res.data.bloom_level !== undefined ? String(res.data.bloom_level) : 'Apply';
          const coTag = res.data.course_outcome || res.data.co || 'CO1';
          const marks = (res.data as any).marks ?? 10;

          saveQuestionToBank({
            question_text: res.data.question,
            marks,
            difficulty: res.data.difficulty_rating || difficulty,
            bloom_level: bloom,
            co: coTag,
            unit_number: unitNumber,
            unit_name: unitName,
            topic: res.data.topic || topicToUse,
            type: res.data.question_type || 'Conceptual',
            answer: res.data.answer || res.data.computed_answer,
            computed_answer: res.data.computed_answer,
            explanation: res.data.explanation,
            source_filename: res.data.source_filename,
            source_pages: res.data.source_pages,
            question_id: res.data.question_id,
          });
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError' || controller.signal.aborted) {
        setError("Generation cancelled by user.");
      } else {
        setError(err.message || "Something went wrong.");
      }
    } finally {
      setLoading(false);
      setAbortController(null);
    }
  };

  const handleAbort = () => {
    if (abortController) {
      abortController.abort();
      setLoading(false);
      setAbortController(null);
      setError("Generation cancelled.");
    }
  };

  const handleExplain = async () => {
    if (!data?.data?.question_id) {
      setProvenanceError('Question ID not available. Question may not have been saved.');
      setShowProvenance(true);
      return;
    }

    setShowProvenance(true);
    setProvenanceLoading(true);
    setProvenanceError(null);
    setProvenanceData(null);

    try {
      const provData = await explainQuestion(data.data.question_id);
      setProvenanceData(provData);
    } catch (err: any) {
      setProvenanceError(err.message || 'Failed to load provenance data');
    } finally {
      setProvenanceLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

  // Quality score color coding
  const getQualityColor = (score?: number) => {
    if (!score) return 'text-ink-faint';
    if (score >= 8) return 'text-green-600';
    if (score >= 7) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getQualityBg = (score?: number) => {
    if (!score) return 'bg-warm-50';
    if (score >= 8) return 'bg-green-50';
    if (score >= 7) return 'bg-yellow-50';
    return 'bg-red-50';
  };

  return (
    <div className="flex flex-col space-y-8 animate-slide-up pb-20">

      {/* INPUT SECTION */}
      <div className="max-w-3xl mx-auto w-full space-y-8">
        <div className="text-center space-y-4">
          <h1 className="font-display text-5xl font-medium text-ink tracking-tight">Generate Evaluation</h1>
          <p className="text-ink-light text-lg">Define parameters for stochastic assessment generation.</p>
        </div>

        <div className="relative group z-10">
          <div className="absolute -inset-1 bg-gradient-to-r from-accent-soft via-warm-100 to-warm-200 rounded-3xl opacity-40 blur-lg transition duration-500 group-hover:opacity-70"></div>
          <div className="relative bg-surface rounded-2xl shadow-xl shadow-warm-100/50 border border-warm-100 p-3 transition-shadow duration-300 group-hover:shadow-2xl group-hover:shadow-accent/5">

            <textarea
              ref={textareaRef}
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Topic e.g. 'pessimistic error estimation'..."
              rows={1}
              className="w-full bg-transparent border-none focus:ring-0 text-ink placeholder-ink-faint text-2xl font-medium resize-none p-5 max-h-48 leading-relaxed"
              disabled={loading}
            />

            <div className="flex items-center justify-between px-3 pb-3 pt-4">
              <div className="flex items-center gap-2 overflow-x-auto pb-1 hide-scrollbar">
                {DIFFICULTIES.map((d) => (
                  <button
                    key={d}
                    onClick={() => setDifficulty(d)}
                    disabled={loading}
                    className={`
                      px-4 py-2 rounded-xl text-xs font-bold tracking-wide transition-all border
                      ${difficulty === d
                        ? 'bg-ink text-white border-ink shadow-lg shadow-ink/20 scale-105'
                        : 'bg-warm-50 text-ink-light border-transparent hover:bg-warm-100 hover:text-ink'}
                      ${loading ? 'opacity-50 cursor-not-allowed' : ''}
                    `}
                  >
                    {d}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                {loading && (
                  <button
                    onClick={handleAbort}
                    className="p-4 rounded-xl transition-all duration-300 flex-shrink-0 bg-red-500 text-white hover:bg-red-600 shadow-lg shadow-red-500/20"
                    title="Cancel generation"
                  >
                    <Icons.X className="w-6 h-6" />
                  </button>
                )}
                <button
                  onClick={() => handleGenerate()}
                  disabled={loading || !topic}
                  className={`
                    p-4 rounded-xl transition-all duration-300 flex-shrink-0
                    ${loading || !topic
                      ? 'bg-warm-100 text-warm-300 cursor-not-allowed'
                      : 'bg-accent text-white hover:bg-accent-hover shadow-lg shadow-accent/20 hover:scale-110 active:scale-95'}
                  `}
                >
                  {loading ? <Icons.Activity className="w-6 h-6 animate-spin" /> : <Icons.Zap className="w-6 h-6 fill-current" />}
                </button>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* ERROR SECTION */}
      {error && (
        <div className="max-w-2xl mx-auto w-full p-4 bg-red-50 text-red-700 rounded-xl text-sm flex items-start gap-3 border border-red-100 shadow-sm">
          <Icons.AlertTriangle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* OUTPUT SECTION */}
      {data && (
        <div className="w-full max-w-5xl mx-auto animate-fade-in pb-12">
          <div className="bg-surface rounded-3xl border border-warm-100 shadow-2xl shadow-warm-200/40 p-10 md:p-14 space-y-12 relative overflow-hidden">

            {/* Decorative top bar */}
            <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-accent via-orange-400 to-warm-300"></div>

            {/* Header with Quality Score and Explain Button */}
            <div className="flex justify-between items-start border-b border-warm-100 pb-6 flex-wrap gap-4">
              <div>
                <h3 className="text-2xl font-display font-bold text-ink mb-3">Generated Question</h3>
                <div className="flex items-center gap-3 flex-wrap">
                <span className="bg-ink text-white px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider shadow-md shadow-ink/20">
                  {data.data.difficulty_rating}
                </span>
                {data.data.quality_score !== undefined && (
                  <span className={`text-xs font-bold px-3 py-1 rounded-full ${getQualityBg(data.data.quality_score)} ${getQualityColor(data.data.quality_score)} border ${data.data.quality_score >= 7 ? 'border-green-200' : 'border-red-200'}`}>
                    Quality: {data.data.quality_score}/10
                  </span>
                )}
                <span className="text-xs font-mono text-ink-faint flex items-center gap-1">
                  <Icons.Activity className="w-3 h-3" />
                  {data.meta.duration_seconds}s
                </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {data.data.question_id && (
                  <button
                    onClick={handleExplain}
                    className="flex items-center gap-2 px-4 py-2 bg-accent/10 hover:bg-accent/20 border border-accent/30 hover:border-accent rounded-xl text-sm font-medium text-accent transition-all"
                    title="View provenance and source documents"
                  >
                    <Icons.Book className="w-4 h-4" />
                    Explain
                  </button>
                )}
              </div>
            </div>

            {/* Source References */}
            {(data.data.source_filename || (data.data.source_pages && data.data.source_pages.length > 0)) && (
              <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4">
                <div className="flex items-center gap-2 text-blue-700 mb-2">
                  <Icons.Book className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase tracking-wide">Source References</span>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {data.data.source_filename && (
                    <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-blue-200">
                      <Icons.FileText className="w-4 h-4 text-red-500" />
                      <span className="text-sm font-medium text-ink">{data.data.source_filename}</span>
                    </div>
                  )}
                  {data.data.source_pages && data.data.source_pages.length > 0 && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-blue-600 font-medium">Pages:</span>
                      <div className="flex flex-wrap gap-1">
                        {data.data.source_pages.map((page, idx) => (
                          <span
                            key={idx}
                            className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-mono font-bold"
                          >
                            {page}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Warning if low quality */}
            {data.data.quality_score !== undefined && data.data.quality_score < 7 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex items-start gap-3">
                <Icons.AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-yellow-800">
                  <strong>Low Quality Warning:</strong> This question scored below threshold. Consider regenerating or manually reviewing.
                </div>
              </div>
            )}

            {/* Question */}
            <div className="relative bg-warm-50/50 rounded-2xl p-8 border border-warm-100">
              <div className="flex items-center gap-2 text-accent mb-4">
                <Icons.FileText className="w-5 h-5" />
                <span className="text-sm font-bold uppercase tracking-wide">Question</span>
              </div>
              <div className="prose prose-lg max-w-none text-ink">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {data.data.question}
                </ReactMarkdown>
              </div>
            </div>

            {/* Answer & Explanation */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-green-50/50 rounded-2xl p-6 border border-green-100">
                <div className="flex items-center gap-2 text-accent">
                  <Icons.Check className="w-5 h-5 text-green-600" />
                  <span className="text-sm font-bold uppercase tracking-wide">Computed Answer</span>
                </div>
                <div className="text-2xl text-green-700 font-bold mt-4">{data.data.computed_answer || data.data.answer}</div>
              </div>

              <div className="bg-blue-50/50 rounded-2xl p-6 border border-blue-100">
                <div className="flex items-center gap-2 text-blue-600 mb-3">
                  <Icons.Book className="w-5 h-5" />
                  <span className="text-sm font-bold uppercase tracking-wide">Explanation</span>
                </div>
                <div className="prose prose-sm max-w-none text-ink-light">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={markdownComponents}
                  >
                    {data.data.explanation}
                  </ReactMarkdown>
                </div>
              </div>
            </div>

            {/* Warning message if present */}
            {data.data.answer_warning && (
              <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 flex items-start gap-3">
                <Icons.AlertTriangle className="w-5 h-5 text-orange-600 flex-shrink-0" />
                <p className="text-sm text-orange-800">{data.data.answer_warning}</p>
              </div>
            )}

          </div>
        </div>
      )}

      {/* STEP 4: Provenance Modal */}
      <ProvenanceModal
        isOpen={showProvenance}
        onClose={() => setShowProvenance(false)}
        data={provenanceData}
        loading={provenanceLoading}
        error={provenanceError}
      />
    </div>
  );
};

export default GenerationModule;
