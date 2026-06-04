import * as React from 'react';
import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Icons } from './ui/SystemIcons';
import {
  createPaperTemplate,
  listPapers,
  exportPaper,
  getAnswerKey,
  getSuggestions,
  getSuggestionsByPDF,
  streamPaperGeneration,
  PaperStreamEvent,
  getPaperRubric,
  getAnalytics,
  getMetrics,
  resetMetrics,
  reloadConfig,
  deletePaper,
  updatePaperTitle,
  Analytics,
  Metrics,
  PaperRubric,
  QuestionRubric,
  PdfExportSettings
} from '../services/api';
import {
  PaperTemplate,
  PaperSection,
  QuestionSpec,
  GeneratedPaper,
  GeneratedQuestion,
  TopicSuggestion,
  PDFSuggestion
} from '../types';
import paperFormats from '../config/paperFormats.json';

const DIFFICULTIES = ['Easy', 'Medium', 'Hard'] as const;
const QUESTION_TYPES = [
  { value: 'short', label: 'Short Answer', marks: 2 },
  { value: 'long', label: 'Long Answer', marks: 5 },
  { value: 'mcq', label: 'Multiple Choice', marks: 1 },
  { value: 'numerical', label: 'Numerical', marks: 3 },
] as const;

type ExamType = 'CIE' | 'SEE';

type FormatConfig = {
  exam_formats?: Record<string, {
    title?: string;
    duration_minutes?: number;
    instructions?: string[];
    sections?: Array<{
      name?: string;
      section_type?: QuestionSpec['question_type'] | 'mixed';
      instructions?: string;
      questions?: Array<{
        question_type: QuestionSpec['question_type'];
        count: number;
        marks: number;
        difficulty?: Difficulty;
      }>;
    }>;
  }>;
};

type QuestionType = typeof QUESTION_TYPES[number]['value'];
type Difficulty = typeof DIFFICULTIES[number];

// Helper to format question text for better readability
const formatQuestionText = (text: string): string => {
  if (!text) return text;

  // Format MCQ options: "A) ... B) ... C) ... D) ..." -> each on new line
  let formatted = text
    .replace(/\s+([A-D])\)\s+/g, '\n\n$1) ')  // Put A), B), C), D) on new lines
    .replace(/Choose one option:\s*/gi, '\n\n**Choose one option:**\n\n')  // Highlight "Choose one"
    .replace(/Options:\s*/gi, '\n\n**Options:**\n\n');

  // Clean up multiple newlines
  formatted = formatted.replace(/\n{3,}/g, '\n\n');

  return formatted.trim();
};

interface PaperGeneratorModuleProps {
  onNavigateToIngest?: () => void;
}

const PaperGeneratorModule: React.FC<PaperGeneratorModuleProps> = ({ onNavigateToIngest }) => {
  // Paper metadata
  const [title, setTitle] = useState('Mid-Term Examination');
  const [subject, setSubject] = useState('Machine Learning');
  const [duration, setDuration] = useState(120);
  const [instructions, setInstructions] = useState<string[]>([
    'Answer all questions',
    'Show your working for partial credit'
  ]);

  // Sections & Questions
  const [sections, setSections] = useState<PaperSection[]>([
    {
      name: 'Section A - Short Answer Questions',
      instructions: 'Answer briefly in 2-3 sentences',
      questions: [],
      section_type: 'short'
    }
  ]);

  // UI State
  const [suggestions, setSuggestions] = useState<PDFSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [collapsedPdfs, setCollapsedPdfs] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState('');
  const [progressPercent, setProgressPercent] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState<{num: number, topic: string, preview?: string} | null>(null);
  const [completedQuestions, setCompletedQuestions] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [autoExamType, setAutoExamType] = useState<ExamType>('CIE');
  const [autoTopics, setAutoTopics] = useState<string>('');
  const [autoError, setAutoError] = useState<string | null>(null);

  // Generated papers
  const [papers, setPapers] = useState<GeneratedPaper[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<GeneratedPaper | null>(null);
  const [showAnswers, setShowAnswers] = useState(false);

  // View mode: 'create' | 'view' | 'analytics'
  const [viewMode, setViewMode] = useState<'create' | 'view' | 'analytics'>('create');

  // Analytics state
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  // Metrics state (observability)
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [metricsTab, setMetricsTab] = useState<'overview' | 'nodes' | 'errors'>('overview');

  // Rubric state
  const [showRubric, setShowRubric] = useState(false);
  const [rubric, setRubric] = useState<PaperRubric | null>(null);
  const [loadingRubric, setLoadingRubric] = useState(false);

  // PDF Export settings modal
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportWithAnswers, setExportWithAnswers] = useState(false);
  const [pdfSettings, setPdfSettings] = useState({
    course_code: '',
    semester: 'V',
    academic_year: '2024-2025',
    ug_pg: 'UG',
    faculty: '',
    department: 'DEPARTMENT OF INFORMATION SCIENCE AND ENGINEERING'
  });

  // Accordion state for sections
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set([0]));

  // Section type modal
  const [showSectionTypeModal, setShowSectionTypeModal] = useState(false);
  const [pendingSectionType, setPendingSectionType] = useState<'short' | 'long' | 'mcq' | 'numerical' | 'mixed'>('short');

  // Fetch suggestions on mount
  useEffect(() => {
    fetchSuggestions();
    fetchPapers();
  }, []);

  const fetchSuggestions = async () => {
    setLoadingSuggestions(true);
    try {
      console.log('[Suggestions] Fetching PDF-grouped suggestions from API...');
      const suggs = await getSuggestionsByPDF();
      console.log('[Suggestions] Received:', suggs);
      if (Array.isArray(suggs) && suggs.length > 0) {
        setSuggestions(suggs);
        console.log('[Suggestions] Set', suggs.length, 'PDF groups with suggestions');
      } else {
        console.warn('[Suggestions] Received empty or invalid suggestions:', suggs);
        setSuggestions([]);
      }
    } catch (err) {
      console.error('[Suggestions] Failed to fetch suggestions:', err);
      setSuggestions([]);
    }
    setLoadingSuggestions(false);
  };

  const fetchPapers = async () => {
    try {
      const paperList = await listPapers();
      setPapers(paperList);
    } catch (err) {
      console.error('Failed to fetch papers:', err);
    }
  };

  const handleDeletePaper = async (paperId: string) => {
    if (!window.confirm('Delete this paper? This action cannot be undone.')) {
      return;
    }

    try {
      const result = await deletePaper(paperId);
      if (result.success) {
        setPapers(papers.filter(p => p.paper_id !== paperId));
        if (selectedPaper?.paper_id === paperId) {
          setSelectedPaper(null);
        }
      } else {
        alert(`Failed to delete: ${result.message}`);
      }
    } catch (error) {
      console.error('Delete error:', error);
      alert('Failed to delete paper');
    }
  };

  const handleRenamePaper = async (paperId: string, currentTitle: string) => {
    const newTitle = prompt('Enter new paper title:', currentTitle);
    if (!newTitle || newTitle === currentTitle) {
      return;
    }

    try {
      const result = await updatePaperTitle(paperId, newTitle);
      if (result.success) {
        setPapers(papers.map(p => 
          p.paper_id === paperId ? { ...p, title: newTitle } : p
        ));
        if (selectedPaper?.paper_id === paperId) {
          setSelectedPaper({ ...selectedPaper, title: newTitle });
        }
      } else {
        alert(`Failed to rename: ${result.message}`);
      }
    } catch (error) {
      console.error('Rename error:', error);
      alert('Failed to rename paper');
    }
  };

  const fetchAnalytics = async () => {
    setLoadingAnalytics(true);
    try {
      const data = await getAnalytics();
      setAnalytics(data);
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
    }
    setLoadingAnalytics(false);
  };

  const fetchMetrics = async () => {
    setLoadingMetrics(true);
    try {
      const data = await getMetrics();
      setMetrics(data);
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    }
    setLoadingMetrics(false);
  };

  const handleResetMetrics = async () => {
    try {
      await resetMetrics();
      await fetchMetrics();
    } catch (err) {
      console.error('Failed to reset metrics:', err);
    }
  };

  const handleReloadConfig = async () => {
    try {
      await reloadConfig();
      alert('Configuration reloaded successfully');
    } catch (err) {
      console.error('Failed to reload config:', err);
    }
  };

  const fetchRubric = async (paperId: string) => {
    setLoadingRubric(true);
    try {
      const data = await getPaperRubric(paperId, 'json') as PaperRubric;
      setRubric(data);
      setShowRubric(true);
    } catch (err) {
      console.error('Failed to fetch rubric:', err);
      setError('Failed to load rubric');
    }
    setLoadingRubric(false);
  };

  // Calculate total marks
  const totalMarks = sections.reduce(
    (sum, s) => sum + s.questions.reduce((qsum, q) => qsum + q.marks, 0),
    0
  );

  const totalQuestions = sections.reduce((sum, s) => sum + s.questions.length, 0);

  // Section management
  const addSection = () => {
    setShowSectionTypeModal(true);
  };

  const createSectionWithType = (sectionType: 'short' | 'long' | 'mcq' | 'numerical' | 'mixed') => {
    const typeNames = {
      short: 'Short Answer Questions',
      long: 'Long Answer Questions',
      mcq: 'Multiple Choice Questions',
      numerical: 'Numerical Problems',
      mixed: 'Mixed Questions'
    };

    setSections([
      ...sections,
      {
        name: `Section ${String.fromCharCode(65 + sections.length)} - ${typeNames[sectionType]}`,
        instructions: sectionType === 'short' ? 'Answer briefly in 2-3 sentences' :
                      sectionType === 'long' ? 'Answer in detail with examples' :
                      sectionType === 'mcq' ? 'Choose the correct option' :
                      sectionType === 'numerical' ? 'Show your calculations' : '',
        questions: [],
        section_type: sectionType
      }
    ]);
    setExpandedSections(new Set([...expandedSections, sections.length]));
    setShowSectionTypeModal(false);
  };

  const removeSection = (idx: number) => {
    if (sections.length <= 1) return;
    setSections(sections.filter((_, i) => i !== idx));
  };

  const updateSection = (idx: number, updates: Partial<PaperSection>) => {
    setSections(sections.map((s, i) => (i === idx ? { ...s, ...updates } : s)));
  };

  // Question management
  const addQuestion = (sectionIdx: number, topic: string = '') => {
    const section = sections[sectionIdx];
    const sectionType = section.section_type || 'short';
    
    // Default marks by type
    const defaultMarks = {
      short: 2,
      long: 5,
      mcq: 1,
      numerical: 3,
      mixed: 2
    };

    const newQ: QuestionSpec = {
      topic: topic,
      question_type: sectionType === 'mixed' ? 'short' : sectionType as any,
      difficulty: 'Medium',
      marks: defaultMarks[sectionType]
    };
    const updated = [...sections];
    updated[sectionIdx].questions.push(newQ);
    setSections(updated);
  };

  const normalizeQuestionType = (
    raw: string | undefined,
    sectionType: QuestionSpec['question_type'] | 'mixed'
  ): QuestionSpec['question_type'] => {
    const t = (raw || '').toLowerCase();
    if (sectionType === 'mcq') return 'mcq';
    if (sectionType === 'numerical') return 'numerical';
    if (t.includes('mcq')) return 'mcq';
    if (t.includes('numerical') || t.includes('problem')) return 'numerical';
    if (t.includes('long') || t.includes('descriptive')) return 'long';
    return sectionType === 'long' ? 'long' : 'short';
  };

  // Build a marks array that sums to target using allowed marks and a max length
  const buildMarksDistribution = (
    allowed: number[],
    target: number,
    desiredCount?: number
  ): number[] => {
    const uniq = Array.from(new Set(allowed)).filter((x) => x > 0).sort((a, b) => a - b);
    const min = uniq[0] || 1;
    const maxCountFromMin = Math.max(1, Math.floor(target / min));

    const countsToTry: number[] = [];
    if (desiredCount && desiredCount > 0) {
      countsToTry.push(desiredCount);
    }
    // Try around desired count if needed
    for (let c = Math.max(1, (desiredCount || maxCountFromMin) - 5); c <= (desiredCount || maxCountFromMin) + 5; c++) {
      if (!countsToTry.includes(c)) countsToTry.push(c);
    }

    const memo = new Map<string, number[] | null>();
    const choose = (count: number, sum: number): number[] | null => {
      const key = `${count}|${sum}`;
      if (memo.has(key)) return memo.get(key) || null;
      if (count === 0) return sum === 0 ? [] : null;
      for (const m of uniq) {
        if (m > sum) continue;
        const rec = choose(count - 1, sum - m);
        if (rec) {
          memo.set(key, [m, ...rec]);
          return memo.get(key)!;
        }
      }
      memo.set(key, null);
      return null;
    };

    for (const cnt of countsToTry) {
      if (cnt <= 0) continue;
      const res = choose(cnt, target);
      if (res && res.length === cnt) return res;
    }

    // Fallback: fill greedily with largest marks until close to target, then adjust
    const greedy = [] as number[];
    let remaining = target;
    while (remaining > 0) {
      const m = uniq.filter((x) => x <= remaining).pop() || min;
      greedy.push(m);
      remaining -= m;
    }
    return greedy;
  };

  // Helper: detect question type from section name
  const getQTypeForSection = (sectionName: string, fallback: string): QuestionSpec['question_type'] => {
    const lower = (sectionName || '').toLowerCase();
    if (lower.includes('short') || lower.includes('definition') || lower.includes('fill')) return 'short';
    if (lower.includes('mcq')) return 'mcq';
    if (lower.includes('numerical') || lower.includes('problem')) return 'numerical';
    if (lower.includes('descriptive') || lower.includes('analytical') || lower.includes('long')) return 'long';
    return fallback as QuestionSpec['question_type'];
  };

  const buildSectionsFromTemplate = (examType: ExamType, topicsInput: string) => {
    setAutoError(null);
    const cfg = (paperFormats as FormatConfig).exam_formats?.[examType];
    if (!cfg || !cfg.sections || cfg.sections.length === 0) {
      setAutoError(`No template found for ${examType}. Update frontend/config/paperFormats.json.`);
      return;
    }

    const topicList = topicsInput
      .split(/[,\n]/)
      .map((t) => t.trim())
      .filter(Boolean);

    // Topics cycle through provided list; questions differ based on type/marks
    const pickTopic = (idx: number): string => {
      if (topicList.length === 0) return 'General topic';
      return topicList[idx % topicList.length];
    };

    const newSections: PaperSection[] = [];

    cfg.sections.forEach((section, sIdx) => {
      const sectionQuestions: QuestionSpec[] = [];

      const pattern: any = (section as any).question_pattern;
      if (pattern) {
        const desiredCount = pattern.number_of_questions || pattern.questions_to_answer || pattern.total_questions_listed || 0;
        const allowedMarks: number[] = Array.isArray(pattern.marks_per_question) && pattern.marks_per_question.length > 0
          ? pattern.marks_per_question
          : [1];
        const totalMarks: number = pattern.total_marks || 0;

        // Special handling: SEE structured sections
        if (pattern.structure && Array.isArray(pattern.structure)) {
          const chosenCount = pattern.questions_to_answer || desiredCount || 5;
          // Derive per-question totals: compulsory + each choice pair’s total
          const perQuestionTotals: number[] = [];
          for (const item of pattern.structure) {
            if (item.compulsory && Array.isArray(item.sub_questions)) {
              const sum = item.sub_questions.reduce((s: number, sq: any) => s + (sq.marks || 0), 0);
              perQuestionTotals.push(sum);
            }
            if (Array.isArray(item.choice_pairs)) {
              for (const pair of item.choice_pairs) {
                const sum = (pair.pattern || []).reduce((s: number, p: any) => s + (p.marks || 0), 0);
                perQuestionTotals.push(sum);
              }
            }
          }
          // Choose the first N totals to match questions_to_answer; if total_marks present, ensure sum aligns
          const selected = perQuestionTotals.slice(0, chosenCount);
          const sumSelected = selected.reduce((a, b) => a + b, 0);
          const scale = totalMarks && sumSelected !== totalMarks ? totalMarks / sumSelected : 1;
          const normalized = selected.map((m) => Math.round(m * scale));
          const sectionName = section.name || `Section ${String.fromCharCode(65 + sIdx)}`;
          const qType = getQTypeForSection(sectionName, section.section_type as any);
          console.log(`SEE Section "${sectionName}": generated ${normalized.length} questions with marks [${normalized.join(', ')}], sum=${normalized.reduce((a,b)=>a+b,0)}, target=${totalMarks}`);
          normalized.forEach((m, i) => {
            sectionQuestions.push({
              topic: pickTopic(i + sIdx),
              question_type: qType,
              difficulty: 'Medium',
              marks: m,
            });
          });
        } else {
          // Generic pattern using marks_per_question and total_marks
          const distribution = totalMarks > 0
            ? buildMarksDistribution(allowedMarks, totalMarks, desiredCount)
            : new Array(Math.max(1, desiredCount || 1)).fill(allowedMarks[0]);

          const sectionName2 = section.name || `Section ${String.fromCharCode(65 + sIdx)}`;
          const qType2 = getQTypeForSection(sectionName2, section.section_type as any);
          console.log(`Section "${sectionName2}" (type: ${qType2}): generated ${distribution.length} questions with marks [${distribution.join(', ')}], sum=${distribution.reduce((a,b)=>a+b,0)}, target=${totalMarks}`);
          distribution.forEach((m, i) => {
            sectionQuestions.push({
              topic: pickTopic(i + sIdx),
              question_type: qType2,
              difficulty: 'Medium',
              marks: m,
            });
          });
        }
      }

      // Fallback to any legacy questions array
      if (sectionQuestions.length === 0 && (section as any).questions) {
        (section as any).questions.forEach((qBlock: any) => {
          const count = Math.max(1, qBlock.count || 1);
          for (let i = 0; i < count; i++) {
            sectionQuestions.push({
              topic: pickTopic(sectionQuestions.length + sIdx),
              question_type: qBlock.question_type,
              difficulty: qBlock.difficulty || 'Medium',
              marks: qBlock.marks || 1,
            });
          }
        });
      }

      newSections.push({
        name: section.name || `Section ${String.fromCharCode(65 + newSections.length)}`,
        instructions: section.instructions || '',
        section_type: section.section_type as any,
        questions: sectionQuestions,
      });
    });

    setSections(newSections);
    if (cfg.instructions && cfg.instructions.length > 0) {
      setInstructions(cfg.instructions);
    }
    if (cfg.duration_minutes) {
      setDuration(cfg.duration_minutes);
    }
    if (cfg.title) {
      setTitle(cfg.title);
    }
    if (topicList.length > 0) {
      setSubject((prev) => prev || `${examType} Paper`);
    }
  };

  const handleAutoBuild = async (shouldGenerate: boolean) => {
    buildSectionsFromTemplate(autoExamType, autoTopics);
    if (shouldGenerate) {
      // Defer generate to next tick to ensure state is applied
      setTimeout(() => {
        handleGenerate();
      }, 0);
    }
  };

  const removeQuestion = (sectionIdx: number, qIdx: number) => {
    const updated = [...sections];
    updated[sectionIdx].questions = updated[sectionIdx].questions.filter((_, i) => i !== qIdx);
    setSections(updated);
  };

  const updateQuestion = (sectionIdx: number, qIdx: number, updates: Partial<QuestionSpec>) => {
    const updated = [...sections];
    updated[sectionIdx].questions[qIdx] = { ...updated[sectionIdx].questions[qIdx], ...updates };
    setSections(updated);
  };

  // Toggle section expansion
  const toggleSection = (idx: number) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(idx)) {
      newExpanded.delete(idx);
    } else {
      newExpanded.add(idx);
    }
    setExpandedSections(newExpanded);
  };

  // Generate paper with real-time streaming progress
  const handleGenerate = async () => {
    if (totalQuestions === 0) {
      setError('Please add at least one question to the paper');
      return;
    }

    setError(null);
    setGenerating(true);
    setGenerationProgress('Validating paper structure...');
    setProgressPercent(0);
    setCurrentQuestion(null);
    setCompletedQuestions([]);

    try {
      const template: PaperTemplate = {
        title,
        subject,
        duration_minutes: duration,
        total_marks: totalMarks,
        instructions,
        sections
      };

      // Step 1: Create template
      setGenerationProgress('Saving template to server...');
      setProgressPercent(5);
      const createRes = await createPaperTemplate(template);

      // Step 2: Generate questions with real-time streaming
      setGenerationProgress('Starting question generation...');

      // Use streaming API for real-time progress
      await new Promise<void>((resolve, reject) => {
        const cleanup = streamPaperGeneration(
          createRes.paper_id,
          // onEvent - handle each streaming event
          (event: PaperStreamEvent) => {
            setProgressPercent(event.progress || 0);

            switch (event.type) {
              case 'start':
                setGenerationProgress(`Starting: ${event.total_questions} questions to generate`);
                break;
              case 'section_start':
                setGenerationProgress(`Section: ${event.section_name}`);
                break;
              case 'question_start':
                setGenerationProgress(`Generating Q${event.question_number}: ${event.topic}`);
                setCurrentQuestion({
                  num: event.question_number || 0,
                  topic: event.topic || ''
                });
                break;
              case 'question_complete':
                setGenerationProgress(`Completed Q${event.question_number}: ${event.topic}`);
                setCurrentQuestion({
                  num: event.question_number || 0,
                  topic: event.topic || '',
                  preview: event.preview
                });
                setCompletedQuestions(prev => [...prev, event.question_number || 0]);
                break;
              case 'question_error':
                setGenerationProgress(`Error on Q${event.question_number}: ${event.error?.slice(0, 30)}`);
                break;
              case 'section_complete':
                setGenerationProgress(`Completed ${event.section_name} (${event.questions_in_section} questions)`);
                break;
              case 'finalizing':
                setGenerationProgress('Finalizing paper...');
                break;
              case 'complete':
                setGenerationProgress('Paper generation complete!');
                break;
              case 'error':
                setError(event.message || 'Generation failed');
                break;
            }
          },
          // onError
          (error) => {
            cleanup();
            reject(error);
          },
          // onComplete
          async (paper) => {
            if (paper) {
              await fetchPapers();
              setSelectedPaper(paper);
              setViewMode('view');
            }
            resolve();
          }
        );
      });

    } catch (err: any) {
      setError(err.message || 'Failed to generate paper');
    } finally {
      setGenerating(false);
      setGenerationProgress('');
      setProgressPercent(0);
      setCurrentQuestion(null);
    }
  };

  // Export handlers
  // Open PDF export modal
  const openPdfExportModal = (withAnswers: boolean) => {
    setExportWithAnswers(withAnswers);
    setShowExportModal(true);
  };

  // Handle actual PDF export with settings
  const handlePdfExport = async () => {
    if (!selectedPaper) return;

    try {
      const result = await exportPaper(selectedPaper.paper_id, 'pdf', exportWithAnswers, pdfSettings);
      const blob = result as Blob;

      // Validate blob
      if (!blob || blob.size === 0) {
        throw new Error('Empty PDF received from server');
      }
      if (blob.type && blob.type !== 'application/pdf') {
        // Try to read error text for better diagnostics
        const text = await blob.text().catch(() => '');
        throw new Error(text || `Unexpected response type: ${blob.type}`);
      }

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeTitle = (selectedPaper.title || 'paper').replace(/\s+/g, '_');
      a.download = `${safeTitle}_${exportWithAnswers ? 'with_answers' : 'questions_only'}.pdf`;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      // Give the browser a moment to start the download before revoking
      setTimeout(() => {
        URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }, 1000);
      setShowExportModal(false);
    } catch (err: any) {
      setError(`Export failed: ${err.message}`);
    }
  };

  // Handle markdown export (no modal needed)
  const handleExport = async (format: 'markdown' | 'pdf', withAnswers: boolean) => {
    if (!selectedPaper) return;

    // For PDF, open the settings modal
    if (format === 'pdf') {
      openPdfExportModal(withAnswers);
      return;
    }

    // For markdown, export directly
    try {
      const result = await exportPaper(selectedPaper.paper_id, format, withAnswers);
      const markdown = result as string;
      const blob = new Blob([markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedPaper.title.replace(/\s+/g, '_')}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(`Export failed: ${err.message}`);
    }
  };

  const handleExportAnswerKey = async () => {
    if (!selectedPaper) return;

    try {
      const answerKey = await getAnswerKey(selectedPaper.paper_id);
      const blob = new Blob([answerKey], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedPaper.title.replace(/\s+/g, '_')}_answer_key.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(`Export failed: ${err.message}`);
    }
  };

  const handleExportRubric = async () => {
    if (!selectedPaper) return;

    try {
      const rubric = await getPaperRubric(selectedPaper.paper_id, 'markdown') as string;
      const blob = new Blob([rubric], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedPaper.title.replace(/\s+/g, '_')}_rubric.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(`Export failed: ${err.message}`);
    }
  };

  // Render question type badge
  const QuestionTypeBadge: React.FC<{ type: QuestionType }> = ({ type }) => {
    const config = QUESTION_TYPES.find(t => t.value === type);
    const colors: Record<string, string> = {
      short: 'bg-blue-100 text-blue-700 border-blue-200',
      long: 'bg-purple-100 text-purple-700 border-purple-200',
      mcq: 'bg-green-100 text-green-700 border-green-200',
      numerical: 'bg-orange-100 text-orange-700 border-orange-200'
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${colors[type]}`}>
        {config?.label}
      </span>
    );
  };

  // Render difficulty badge
  const DifficultyBadge: React.FC<{ difficulty: Difficulty }> = ({ difficulty }) => {
    const colors: Record<string, string> = {
      Easy: 'bg-green-100 text-green-700',
      Medium: 'bg-yellow-100 text-yellow-700',
      Hard: 'bg-red-100 text-red-700'
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${colors[difficulty]}`}>
        {difficulty}
      </span>
    );
  };

  return (
    <div className="flex flex-col space-y-8 animate-slide-up pb-20">
      {/* Header */}
      <div className="text-center space-y-4">
        <h1 className="font-display text-5xl font-medium text-ink tracking-tight flex items-center justify-center gap-3">
          <Icons.ClipboardList className="w-12 h-12 text-accent" />
          Paper Generator
        </h1>
        <p className="text-ink-light text-lg">Create comprehensive question papers with AI-generated questions</p>
      </div>

      {/* View Toggle */}
      <div className="flex justify-center">
        <div className="flex bg-white/50 backdrop-blur-md p-1.5 rounded-full border border-white/60 shadow-sm">
          <button
            onClick={() => setViewMode('create')}
            className={`px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${
              viewMode === 'create'
                ? 'bg-accent text-white shadow-lg shadow-accent/25'
                : 'text-ink-light hover:text-accent'
            }`}
          >
            <Icons.Plus className="w-4 h-4 inline mr-2" />
            Create Paper
          </button>
          <button
            onClick={() => setViewMode('view')}
            className={`px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${
              viewMode === 'view'
                ? 'bg-accent text-white shadow-lg shadow-accent/25'
                : 'text-ink-light hover:text-accent'
            }`}
          >
            <Icons.Eye className="w-4 h-4 inline mr-2" />
            View Papers ({papers.length})
          </button>
          <button
            onClick={() => {
              setViewMode('analytics');
              fetchAnalytics();
              fetchMetrics();
            }}
            className={`px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${
              viewMode === 'analytics'
                ? 'bg-accent text-white shadow-lg shadow-accent/25'
                : 'text-ink-light hover:text-accent'
            }`}
          >
            <Icons.Activity className="w-4 h-4 inline mr-2" />
            Analytics
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="max-w-4xl mx-auto w-full p-4 bg-red-50 text-red-700 rounded-xl text-sm flex items-start gap-3 border border-red-100">
          <Icons.AlertTriangle className="w-5 h-5 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <Icons.X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* CREATE MODE */}
      {viewMode === 'create' && (
        <div className="max-w-4xl mx-auto w-full space-y-8">
          {/* Paper Metadata */}
          <div className="bg-surface rounded-2xl border border-warm-100 shadow-xl p-6 space-y-6">
            <h2 className="font-display text-xl font-semibold text-ink flex items-center gap-2">
              <Icons.Settings className="w-5 h-5 text-accent" />
              Paper Settings
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-ink-light mb-2">Paper Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-warm-200 focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition-all"
                  placeholder="Mid-Term Examination"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-ink-light mb-2">Subject</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-warm-200 focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition-all"
                  placeholder="Machine Learning"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-ink-light mb-2">Duration (minutes)</label>
                <input
                  type="number"
                  value={duration}
                  onChange={(e) => setDuration(parseInt(e.target.value) || 60)}
                  className="w-full px-4 py-3 rounded-xl border border-warm-200 focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition-all"
                  min={15}
                  max={300}
                />
              </div>
              <div className="flex items-end">
                <div className="bg-accent-soft/50 rounded-xl px-4 py-3 w-full">
                  <div className="text-xs text-accent font-medium uppercase tracking-wide">Total Marks</div>
                  <div className="text-2xl font-bold text-accent">{totalMarks}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Intelligent Topic Suggestions */}
          <div className="bg-gradient-to-r from-accent-soft/30 via-warm-50 to-accent-soft/30 rounded-2xl border border-accent/20 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-ink flex items-center gap-2">
                <Icons.Sparkles className="w-5 h-5 text-accent" />
                Topic Suggestions from Your PDFs
              </h2>
              <button
                onClick={fetchSuggestions}
                disabled={loadingSuggestions}
                className="text-accent hover:text-accent-hover text-sm font-medium flex items-center gap-1"
              >
                {loadingSuggestions ? (
                  <Icons.Activity className="w-4 h-4 animate-spin" />
                ) : (
                  <Icons.Zap className="w-4 h-4" />
                )}
                Refresh
              </button>
            </div>

            {suggestions.length > 0 ? (
              <div className="space-y-4">
                {suggestions.map((pdfGroup, pdfIdx) => {
                  const isCollapsed = collapsedPdfs.has(pdfGroup.filename);
                  const totalTopics = suggestions.reduce((sum, pdf) => sum + pdf.count, 0);
                  
                  return (
                    <div key={pdfIdx} className="border border-accent/20 rounded-xl overflow-hidden bg-white">
                      {/* PDF Header */}
                      <button
                        onClick={() => {
                          const newCollapsed = new Set(collapsedPdfs);
                          if (isCollapsed) {
                            newCollapsed.delete(pdfGroup.filename);
                          } else {
                            newCollapsed.add(pdfGroup.filename);
                          }
                          setCollapsedPdfs(newCollapsed);
                        }}
                        className="w-full flex items-center justify-between p-4 hover:bg-accent/5 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <Icons.File className="w-5 h-5 text-accent" />
                          <div className="text-left">
                            <div className="font-medium text-ink">{pdfGroup.filename}</div>
                            <div className="flex items-center gap-2 text-xs text-ink-faint mt-0.5">
                              {pdfGroup.unit_name && (
                                <span className="px-2 py-0.5 bg-accent/10 rounded text-accent font-medium">
                                  Unit {pdfGroup.unit_number}: {pdfGroup.unit_name}
                                </span>
                              )}
                              <span>{pdfGroup.count} topic{pdfGroup.count !== 1 ? 's' : ''}</span>
                              {pdfGroup.co_mapping && pdfGroup.co_mapping.length > 0 && (
                                <span className="text-ink-faint">• {pdfGroup.co_mapping.join(', ')}</span>
                              )}
                            </div>
                          </div>
                        </div>
                        {isCollapsed ? (
                          <Icons.ChevronRight className="w-5 h-5 text-ink-light" />
                        ) : (
                          <Icons.ChevronDown className="w-5 h-5 text-ink-light" />
                        )}
                      </button>

                      {/* Topics Grid */}
                      {!isCollapsed && (
                        <div className="px-4 pb-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                          {pdfGroup.suggestions.map((suggestion, idx) => (
                            <button
                              key={idx}
                              onClick={() => {
                                if (sections.length > 0) {
                                  addQuestion(0, suggestion.topic);
                                }
                              }}
                              className="group p-3 bg-gray-50 rounded-lg border border-accent/10 text-left hover:border-accent hover:bg-white hover:shadow-md transition-all duration-200"
                              title={suggestion.examples?.length > 0 ? `Examples: ${suggestion.examples.join(', ')}` : ''}
                            >
                              <div className="flex items-start gap-2">
                                <Icons.Plus className="w-4 h-4 text-accent opacity-50 group-hover:opacity-100 mt-0.5 flex-shrink-0" />
                                <div className="min-w-0">
                                  <div className="font-medium text-sm text-ink truncate">{suggestion.topic}</div>
                                  {suggestion.examples?.length > 0 && (
                                    <div className="text-xs text-ink-faint mt-0.5 truncate">
                                      {suggestion.examples[0]}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-6 text-ink-light">
                <Icons.Database className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No suggestions available.</p>
                <button
                  onClick={onNavigateToIngest}
                  className="text-accent hover:text-accent-hover text-sm font-medium mt-1"
                >
                  Upload a PDF to get topic suggestions
                </button>
              </div>
            )}
            <p className="text-xs text-ink-faint">
              Click a topic to add it as a question • Found {suggestions.reduce((sum, pdf) => sum + pdf.count, 0)} topics across {suggestions.length} document{suggestions.length !== 1 ? 's' : ''}
            </p>
          </div>

          {/* Auto Paper Builder */}
          <div className="bg-white rounded-2xl border border-warm-200 shadow-lg p-6 space-y-4">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <Icons.ClipboardList className="w-5 h-5 text-accent" />
                <h2 className="font-display text-lg font-semibold text-ink">Auto Paper Builder</h2>
              </div>
              <div className="flex items-center gap-3">
                <label className="text-sm font-medium text-ink-light">Exam Type</label>
                <select
                  value={autoExamType}
                  onChange={(e) => setAutoExamType(e.target.value as ExamType)}
                  className="px-3 py-2 rounded-lg border border-warm-200 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20"
                >
                  <option value="CIE">CIE</option>
                  <option value="SEE">SEE</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-ink-light mb-2">Important topics to cover</label>
              <textarea
                value={autoTopics}
                onChange={(e) => setAutoTopics(e.target.value)}
                rows={3}
                placeholder="Comma or newline separated topics (e.g., Search strategies, Agents, Informed search)"
                className="w-full rounded-xl border border-warm-200 px-3 py-2 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20"
              />
              <p className="text-xs text-ink-faint mt-1">Templates live at frontend/config/paperFormats.json. Update that file to change sections, counts, and marks.</p>
            </div>

            {autoError && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                {autoError}
              </div>
            )}

            <div className="flex items-center gap-3 flex-wrap">
              <button
                onClick={() => handleAutoBuild(false)}
                className="px-4 py-2 bg-accent text-white rounded-xl font-semibold hover:bg-accent-hover transition flex items-center gap-2"
              >
                <Icons.Layers className="w-4 h-4" />
                Auto-build paper
              </button>
              <button
                onClick={() => handleAutoBuild(true)}
                className="px-4 py-2 bg-ink text-white rounded-xl font-semibold hover:bg-ink/90 transition flex items-center gap-2"
                disabled={generating}
              >
                <Icons.Zap className="w-4 h-4" />
                Auto-build & generate
              </button>
            </div>
          </div>

          {/* Sections */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-xl font-semibold text-ink flex items-center gap-2">
                <Icons.Layers className="w-5 h-5 text-accent" />
                Sections ({sections.length})
              </h2>
              <button
                onClick={addSection}
                className="px-4 py-2 bg-accent text-white rounded-xl text-sm font-medium hover:bg-accent-hover transition-all shadow-lg shadow-accent/20 flex items-center gap-2"
              >
                <Icons.Plus className="w-4 h-4" />
                Add Section
              </button>
            </div>

            {sections.map((section, sectionIdx) => (
              <div
                key={sectionIdx}
                className="bg-surface rounded-2xl border border-warm-100 shadow-lg overflow-hidden"
              >
                {/* Section Header */}
                <div
                  className="flex items-center justify-between px-6 py-4 bg-warm-50/50 cursor-pointer hover:bg-warm-50 transition-colors"
                  onClick={() => toggleSection(sectionIdx)}
                >
                  <div className="flex items-center gap-3">
                    {expandedSections.has(sectionIdx) ? (
                      <Icons.ChevronDown className="w-5 h-5 text-ink-light" />
                    ) : (
                      <Icons.ChevronRight className="w-5 h-5 text-ink-light" />
                    )}
                    <input
                      type="text"
                      value={section.name}
                      onChange={(e) => {
                        e.stopPropagation();
                        updateSection(sectionIdx, { name: e.target.value });
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="font-display font-semibold text-ink bg-transparent border-none focus:ring-0 p-0"
                    />
                    {section.section_type && (
                      <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                        section.section_type === 'short' ? 'bg-blue-50 text-blue-700' :
                        section.section_type === 'long' ? 'bg-purple-50 text-purple-700' :
                        section.section_type === 'mcq' ? 'bg-green-50 text-green-700' :
                        section.section_type === 'numerical' ? 'bg-orange-50 text-orange-700' :
                        'bg-pink-50 text-pink-700'
                      }`}>
                        {section.section_type === 'mcq' ? 'MCQ' : section.section_type.charAt(0).toUpperCase() + section.section_type.slice(1)}
                      </span>
                    )}
                    <span className="text-xs text-ink-faint bg-warm-100 px-2 py-1 rounded-full">
                      {section.questions.length} questions
                    </span>
                  </div>
                  {sections.length > 1 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeSection(sectionIdx);
                      }}
                      className="text-red-400 hover:text-red-600 p-1"
                    >
                      <Icons.Trash className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Section Content */}
                {expandedSections.has(sectionIdx) && (
                  <div className="p-6 space-y-4">
                    {/* Section Instructions */}
                    <div>
                      <label className="block text-xs font-medium text-ink-light mb-1">Section Instructions (optional)</label>
                      <input
                        type="text"
                        value={section.instructions || ''}
                        onChange={(e) => updateSection(sectionIdx, { instructions: e.target.value })}
                        className="w-full px-3 py-2 rounded-lg border border-warm-200 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20 outline-none"
                        placeholder="Answer all questions in this section..."
                      />
                    </div>

                    {/* Questions List */}
                    <div className="space-y-3">
                      {section.questions.map((q, qIdx) => (
                        <div
                          key={qIdx}
                          className="flex items-start gap-3 p-4 bg-warm-50/50 rounded-xl border border-warm-100 group hover:border-accent/30 transition-all"
                        >
                          <span className="text-xs font-bold text-ink-faint bg-warm-100 px-2 py-1 rounded-full">
                            Q{qIdx + 1}
                          </span>
                          <div className="flex-1 space-y-3">
                            {/* Topic Input */}
                            <input
                              type="text"
                              value={q.topic}
                              onChange={(e) => updateQuestion(sectionIdx, qIdx, { topic: e.target.value })}
                              className="w-full px-3 py-2 rounded-lg border border-warm-200 focus:border-accent focus:ring-1 focus:ring-accent/20 outline-none text-sm"
                              placeholder="Enter topic (e.g., 'decision tree pruning')"
                            />
                            {/* Question Options */}
                            <div className="flex flex-wrap items-center gap-2">
                              {/* Question Type */}
                              <select
                                value={q.question_type}
                                onChange={(e) => {
                                  const type = e.target.value as QuestionType;
                                  const defaultMarks = QUESTION_TYPES.find(t => t.value === type)?.marks || 2;
                                  updateQuestion(sectionIdx, qIdx, { question_type: type, marks: defaultMarks });
                                }}
                                className="px-3 py-1.5 rounded-lg border border-warm-200 text-xs bg-white focus:border-accent outline-none"
                              >
                                {QUESTION_TYPES.map((t) => (
                                  <option key={t.value} value={t.value}>{t.label}</option>
                                ))}
                              </select>
                              {/* Difficulty */}
                              <select
                                value={q.difficulty}
                                onChange={(e) => updateQuestion(sectionIdx, qIdx, { difficulty: e.target.value as Difficulty })}
                                className="px-3 py-1.5 rounded-lg border border-warm-200 text-xs bg-white focus:border-accent outline-none"
                              >
                                {DIFFICULTIES.map((d) => (
                                  <option key={d} value={d}>{d}</option>
                                ))}
                              </select>
                              {/* Marks */}
                              <div className="flex items-center gap-1">
                                <span className="text-xs text-ink-light">Marks:</span>
                                <input
                                  type="number"
                                  value={q.marks}
                                  onChange={(e) => updateQuestion(sectionIdx, qIdx, { marks: parseInt(e.target.value) || 1 })}
                                  className="w-14 px-2 py-1 rounded-lg border border-warm-200 text-xs text-center focus:border-accent outline-none"
                                  min={1}
                                  max={20}
                                />
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={() => removeQuestion(sectionIdx, qIdx)}
                            className="text-red-400 hover:text-red-600 p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <Icons.X className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* Add Question Button */}
                    <button
                      onClick={() => addQuestion(sectionIdx)}
                      className="w-full py-3 border-2 border-dashed border-warm-200 rounded-xl text-ink-light hover:border-accent hover:text-accent transition-all flex items-center justify-center gap-2 text-sm font-medium"
                    >
                      <Icons.Plus className="w-4 h-4" />
                      Add Question
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Generate Button */}
          <div className="flex justify-center pt-4">
            <button
              onClick={handleGenerate}
              disabled={generating || totalQuestions === 0}
              className={`px-8 py-4 rounded-2xl text-lg font-bold transition-all duration-300 flex items-center gap-3 ${
                generating || totalQuestions === 0
                  ? 'bg-warm-200 text-warm-400 cursor-not-allowed'
                  : 'bg-accent text-white hover:bg-accent-hover shadow-xl shadow-accent/30 hover:scale-105 active:scale-95'
              }`}
            >
              <Icons.Zap className="w-6 h-6" />
              Generate Paper ({totalQuestions} questions)
            </button>
          </div>
        </div>
      )}

      {/* Generation Progress - Top Right Notification */}
      {generating && (
        <div className="fixed top-24 right-6 z-50 w-96 animate-slide-up">
          <div className="bg-white rounded-2xl shadow-2xl border border-warm-100 overflow-hidden">
            {/* Header */}
            <div className="bg-gradient-to-r from-accent to-orange-400 px-4 py-3 flex items-center gap-3">
              <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                <Icons.ClipboardList className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-white font-semibold text-sm truncate">{title}</div>
                <div className="text-white/80 text-xs">{subject}</div>
              </div>
              <div className="text-white font-bold text-lg">{progressPercent}%</div>
            </div>

            {/* Progress Bar */}
            <div className="h-1.5 bg-warm-100">
              <div
                className="h-full bg-gradient-to-r from-accent to-green-500 transition-all duration-300 ease-out"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            {/* Progress Details */}
            <div className="p-4 space-y-3">
              {/* Current Status */}
              <div className="flex items-center gap-2 text-sm bg-warm-50 rounded-lg px-3 py-2">
                <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
                <span className="text-ink-light truncate">{generationProgress || 'Initializing...'}</span>
              </div>

              {/* Current Question Preview */}
              {currentQuestion && (
                <div className="bg-accent-soft/30 rounded-lg p-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="bg-accent text-white text-xs font-bold px-2 py-0.5 rounded-full">
                      Q{currentQuestion.num}
                    </span>
                    <span className="text-sm font-medium text-ink truncate">{currentQuestion.topic}</span>
                  </div>
                  {currentQuestion.preview && (
                    <p className="text-xs text-ink-light line-clamp-2 italic">
                      "{currentQuestion.preview}"
                    </p>
                  )}
                </div>
              )}

              {/* Completed Questions */}
              {completedQuestions.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-ink-faint">Completed:</span>
                  {completedQuestions.slice(-5).map(num => (
                    <span key={num} className="bg-green-100 text-green-700 text-xs font-medium px-2 py-0.5 rounded-full">
                      Q{num}
                    </span>
                  ))}
                  {completedQuestions.length > 5 && (
                    <span className="text-xs text-ink-faint">+{completedQuestions.length - 5} more</span>
                  )}
                </div>
              )}

              {/* Stats Row */}
              <div className="flex items-center justify-between text-xs pt-1 border-t border-warm-100">
                <div className="flex items-center gap-1.5 text-ink-faint">
                  <Icons.ListOrdered className="w-3.5 h-3.5" />
                  <span>{completedQuestions.length}/{totalQuestions}</span>
                </div>
                <div className="flex items-center gap-1.5 text-ink-faint">
                  <Icons.Layers className="w-3.5 h-3.5" />
                  <span>{sections.length} sections</span>
                </div>
                <div className="flex items-center gap-1.5 text-ink-faint">
                  <Icons.GraduationCap className="w-3.5 h-3.5" />
                  <span>{totalMarks} marks</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW MODE */}
      {viewMode === 'view' && (
        <div className="max-w-5xl mx-auto w-full space-y-6">
          {/* Papers List */}
          {!selectedPaper && (
            <div className="space-y-4">
              {papers.length === 0 ? (
                <div className="text-center py-16 bg-warm-50/50 rounded-2xl border border-dashed border-warm-200">
                  <Icons.ClipboardList className="w-16 h-16 text-warm-300 mx-auto mb-4" />
                  <p className="text-ink-light mb-2">No papers generated yet</p>
                  <button
                    onClick={() => setViewMode('create')}
                    className="text-accent hover:text-accent-hover font-medium"
                  >
                    Create your first paper
                  </button>
                </div>
              ) : (
                papers.map((paper) => (
                  <div
                    key={paper.paper_id}
                    className="bg-surface rounded-2xl border border-warm-100 p-6 hover:border-accent/30 hover:shadow-lg transition-all group"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div 
                        onClick={() => setSelectedPaper(paper)}
                        className="flex-1 cursor-pointer"
                      >
                        <h3 className="font-display text-xl font-semibold text-ink group-hover:text-accent transition-colors">
                          {paper.title}
                        </h3>
                        <p className="text-ink-light text-sm">{paper.subject}</p>
                        <div className="flex items-center gap-4 mt-3 text-xs text-ink-faint">
                          <span className="flex items-center gap-1">
                            <Icons.Clock className="w-3 h-3" />
                            {paper.duration_minutes} min
                          </span>
                          <span className="flex items-center gap-1">
                            <Icons.ListOrdered className="w-3 h-3" />
                            {paper.sections.reduce((sum, s) => sum + s.questions.length, 0)} questions
                          </span>
                          <span className="flex items-center gap-1">
                            <Icons.GraduationCap className="w-3 h-3" />
                            {paper.total_marks} marks
                          </span>
                        </div>
                      </div>
                      <div className="flex flex-col gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRenamePaper(paper.paper_id, paper.title);
                          }}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition"
                          title="Rename paper"
                        >
                          <Icons.Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeletePaper(paper.paper_id);
                          }}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition"
                          title="Delete paper"
                        >
                          <Icons.Trash className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Selected Paper View */}
          {selectedPaper && (
            <div className="space-y-6">
              {/* Back Button & Actions */}
              <div className="flex items-center justify-between flex-wrap gap-4">
                <button
                  onClick={() => setSelectedPaper(null)}
                  className="text-ink-light hover:text-ink flex items-center gap-2 text-sm font-medium"
                >
                  <Icons.ArrowRight className="w-4 h-4 rotate-180" />
                  Back to Papers
                </button>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => setShowAnswers(!showAnswers)}
                    className={`px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2 border transition-all ${
                      showAnswers
                        ? 'bg-accent text-white border-accent'
                        : 'bg-white text-ink-light border-warm-200 hover:border-accent hover:text-accent'
                    }`}
                  >
                    {showAnswers ? <Icons.EyeOff className="w-4 h-4" /> : <Icons.Eye className="w-4 h-4" />}
                    {showAnswers ? 'Hide Answers' : 'Show Answers'}
                  </button>
                  <button
                    onClick={() => fetchRubric(selectedPaper.paper_id)}
                    disabled={loadingRubric}
                    className="px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2 border border-warm-200 bg-white text-ink-light hover:border-purple-400 hover:text-purple-600 transition-all"
                  >
                    {loadingRubric ? (
                      <Icons.Activity className="w-4 h-4 animate-spin" />
                    ) : (
                      <Icons.ListOrdered className="w-4 h-4" />
                    )}
                    View Rubric
                  </button>
                  <div className="relative group">
                    <button className="px-4 py-2 bg-accent text-white rounded-xl text-sm font-medium flex items-center gap-2 hover:bg-accent-hover transition-all shadow-lg shadow-accent/20">
                      <Icons.Download className="w-4 h-4" />
                      Export
                      <Icons.ChevronDown className="w-3 h-3" />
                    </button>
                    <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-xl border border-warm-100 py-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                      <button
                        onClick={() => handleExport('markdown', false)}
                        className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-warm-50 flex items-center gap-2"
                      >
                        <Icons.FileText className="w-4 h-4" />
                        Markdown (Questions Only)
                      </button>
                      <button
                        onClick={() => handleExport('markdown', true)}
                        className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-warm-50 flex items-center gap-2"
                      >
                        <Icons.FileText className="w-4 h-4" />
                        Markdown (With Answers)
                      </button>
                      <button
                        onClick={() => handleExport('pdf', false)}
                        className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-warm-50 flex items-center gap-2"
                      >
                        <Icons.FileDown className="w-4 h-4" />
                        PDF (Questions Only)
                      </button>
                      <button
                        onClick={() => handleExport('pdf', true)}
                        className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-warm-50 flex items-center gap-2"
                      >
                        <Icons.FileDown className="w-4 h-4" />
                        PDF (With Answers)
                      </button>
                      <hr className="my-2 border-warm-100" />
                      <button
                        onClick={handleExportAnswerKey}
                        className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-warm-50 flex items-center gap-2"
                      >
                        <Icons.ClipboardList className="w-4 h-4" />
                        Separate Answer Key
                      </button>
                      <button
                        onClick={handleExportRubric}
                        className="w-full px-4 py-2 text-left text-sm text-ink hover:bg-warm-50 flex items-center gap-2"
                      >
                        <Icons.ListOrdered className="w-4 h-4" />
                        Marking Rubric
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Paper Header */}
              <div className="bg-surface rounded-3xl border border-warm-100 shadow-2xl p-8 space-y-6">
                <div className="text-center space-y-2 border-b border-warm-100 pb-6">
                  <h1 className="font-display text-3xl font-bold text-ink">{selectedPaper.title}</h1>
                  <p className="text-ink-light">{selectedPaper.subject}</p>
                  <div className="flex items-center justify-center gap-6 mt-4 text-sm text-ink-faint">
                    <span className="flex items-center gap-1">
                      <Icons.Clock className="w-4 h-4" />
                      Duration: {selectedPaper.duration_minutes} minutes
                    </span>
                    <span className="flex items-center gap-1">
                      <Icons.GraduationCap className="w-4 h-4" />
                      Total Marks: {selectedPaper.total_marks}
                    </span>
                  </div>
                </div>

                {/* Instructions */}
                {selectedPaper.instructions.length > 0 && (
                  <div className="bg-warm-50 rounded-xl p-4">
                    <h3 className="text-sm font-bold text-ink uppercase tracking-wide mb-2">Instructions</h3>
                    <ul className="list-disc list-inside text-sm text-ink-light space-y-1">
                      {selectedPaper.instructions.map((inst, idx) => (
                        <li key={idx}>{inst}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Sections & Questions */}
                {selectedPaper.sections.map((section, sIdx) => (
                  <div key={sIdx} className="space-y-4">
                    <h2 className="font-display text-xl font-semibold text-ink border-b border-warm-100 pb-2">
                      {section.name}
                    </h2>
                    {section.instructions && (
                      <p className="text-sm text-ink-light italic">{section.instructions}</p>
                    )}

                    {section.questions.map((q: GeneratedQuestion, qIdx: number) => (
                      <div key={qIdx} className="bg-warm-50/50 rounded-xl p-5 space-y-3">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex items-start gap-3">
                            <span className="bg-ink text-white text-xs font-bold px-2 py-1 rounded-full">
                              {q.question_number || qIdx + 1}
                            </span>
                            <div className="flex-1">
                              <div className="prose prose-sm max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {formatQuestionText(q.question_text) || 'No question text'}
                                </ReactMarkdown>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <QuestionTypeBadge type={q.question_type} />
                            <DifficultyBadge difficulty={q.difficulty} />
                            <span className="text-xs font-bold text-ink bg-warm-100 px-2 py-1 rounded-full">
                              {q.marks} marks
                            </span>
                          </div>
                        </div>

                        {/* Tags */}
                        {q.tags && q.tags.length > 0 && (
                          <div className="flex items-center gap-2 flex-wrap">
                            <Icons.Tag className="w-3 h-3 text-ink-faint" />
                            {q.tags.map((tag, tIdx) => (
                              <span key={tIdx} className="text-xs text-ink-faint bg-warm-100 px-2 py-0.5 rounded-full">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Answer (if showing) */}
                        {showAnswers && (
                          <div className="mt-4 pt-4 border-t border-warm-200 space-y-3">
                            <div>
                              <span className="text-xs font-bold text-green-600 uppercase tracking-wide">Answer</span>
                              <div className="mt-1 text-sm text-ink font-medium">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {q.answer || 'No answer provided'}
                                </ReactMarkdown>
                              </div>
                            </div>
                            {q.explanation && (
                              <div>
                                <span className="text-xs font-bold text-blue-600 uppercase tracking-wide">Explanation</span>
                                <div className="mt-1 text-sm text-ink-light">
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {q.explanation}
                                  </ReactMarkdown>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ANALYTICS MODE */}
      {viewMode === 'analytics' && (
        <div className="max-w-5xl mx-auto w-full space-y-6">
          {loadingAnalytics ? (
            <div className="flex items-center justify-center py-16">
              <Icons.Activity className="w-8 h-8 text-accent animate-spin" />
              <span className="ml-3 text-ink-light">Loading analytics...</span>
            </div>
          ) : analytics ? (
            <>
              {/* Stats Cards Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {/* Total Papers */}
                <div className="bg-surface rounded-2xl border border-warm-100 shadow-lg p-5">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-accent-soft rounded-xl flex items-center justify-center">
                      <Icons.ClipboardList className="w-6 h-6 text-accent" />
                    </div>
                    <div>
                      <div className="text-3xl font-bold text-ink">{analytics.papers.total}</div>
                      <div className="text-xs text-ink-light">Papers Generated</div>
                    </div>
                  </div>
                </div>

                {/* Total Questions in Bank */}
                <div className="bg-surface rounded-2xl border border-warm-100 shadow-lg p-5">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                      <Icons.Database className="w-6 h-6 text-blue-600" />
                    </div>
                    <div>
                      <div className="text-3xl font-bold text-ink">{analytics.questions.total_in_bank}</div>
                      <div className="text-xs text-ink-light">Questions in Bank</div>
                    </div>
                  </div>
                </div>

                {/* Total Generated */}
                <div className="bg-surface rounded-2xl border border-warm-100 shadow-lg p-5">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                      <Icons.Zap className="w-6 h-6 text-green-600" />
                    </div>
                    <div>
                      <div className="text-3xl font-bold text-ink">{analytics.generation.total_generated}</div>
                      <div className="text-xs text-ink-light">Total Generated</div>
                    </div>
                  </div>
                </div>

                {/* Cache Hit Rate */}
                <div className="bg-surface rounded-2xl border border-warm-100 shadow-lg p-5">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                      <Icons.Activity className="w-6 h-6 text-purple-600" />
                    </div>
                    <div>
                      <div className="text-3xl font-bold text-ink">{(analytics.generation.cache_hit_rate * 100).toFixed(0)}%</div>
                      <div className="text-xs text-ink-light">Cache Hit Rate</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Cache Performance */}
              <div className="bg-surface rounded-2xl border border-warm-100 shadow-xl p-6 space-y-4">
                <h2 className="font-display text-lg font-semibold text-ink flex items-center gap-2">
                  <Icons.Zap className="w-5 h-5 text-accent" />
                  Cache Performance
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-green-50 rounded-xl p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">{analytics.generation.cache_hits}</div>
                    <div className="text-sm text-green-700">Cache Hits</div>
                    <div className="text-xs text-green-600/70 mt-1">Questions from bank</div>
                  </div>
                  <div className="bg-orange-50 rounded-xl p-4 text-center">
                    <div className="text-2xl font-bold text-orange-600">
                      {analytics.generation.total_generated - analytics.generation.cache_hits}
                    </div>
                    <div className="text-sm text-orange-700">Fresh Generated</div>
                    <div className="text-xs text-orange-600/70 mt-1">New AI generations</div>
                  </div>
                  <div className="bg-purple-50 rounded-xl p-4 text-center">
                    <div className="text-2xl font-bold text-purple-600">
                      {(analytics.generation.cache_hit_rate * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-purple-700">Efficiency</div>
                    <div className="text-xs text-purple-600/70 mt-1">Cache utilization</div>
                  </div>
                </div>
                {/* Progress bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-ink-light">
                    <span>Cache Usage</span>
                    <span>{analytics.generation.cache_hits} / {analytics.generation.total_generated}</span>
                  </div>
                  <div className="h-3 bg-warm-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full transition-all duration-500"
                      style={{ width: `${analytics.generation.cache_hit_rate * 100}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Difficulty Distribution & Topics Row */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Difficulty Distribution */}
                <div className="bg-surface rounded-2xl border border-warm-100 shadow-xl p-6 space-y-4">
                  <h2 className="font-display text-lg font-semibold text-ink flex items-center gap-2">
                    <Icons.Layers className="w-5 h-5 text-accent" />
                    Difficulty Distribution
                  </h2>
                  <div className="space-y-3">
                    {Object.entries(analytics.questions.by_difficulty).map(([diff, count]) => {
                      const total = Object.values(analytics.questions.by_difficulty).reduce((a, b) => a + b, 0);
                      const percent = total > 0 ? (count / total) * 100 : 0;
                      const colors: Record<string, string> = {
                        Easy: 'bg-green-500',
                        Medium: 'bg-yellow-500',
                        Hard: 'bg-red-500'
                      };
                      return (
                        <div key={diff} className="space-y-1">
                          <div className="flex justify-between text-sm">
                            <span className="text-ink font-medium">{diff}</span>
                            <span className="text-ink-light">{count} ({percent.toFixed(0)}%)</span>
                          </div>
                          <div className="h-2 bg-warm-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${colors[diff] || 'bg-accent'} rounded-full transition-all duration-500`}
                              style={{ width: `${percent}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Top Topics */}
                <div className="bg-surface rounded-2xl border border-warm-100 shadow-xl p-6 space-y-4">
                  <h2 className="font-display text-lg font-semibold text-ink flex items-center gap-2">
                    <Icons.Tag className="w-5 h-5 text-accent" />
                    Top Topics
                  </h2>
                  <div className="space-y-2">
                    {analytics.questions.by_topic.length === 0 ? (
                      <p className="text-ink-light text-sm py-4 text-center">No topics yet</p>
                    ) : (
                      analytics.questions.by_topic.slice(0, 8).map((item, idx) => (
                        <div key={idx} className="flex items-center justify-between py-2 border-b border-warm-50 last:border-0">
                          <div className="flex items-center gap-2">
                            <span className="w-6 h-6 bg-accent-soft text-accent text-xs font-bold rounded-full flex items-center justify-center">
                              {idx + 1}
                            </span>
                            <span className="text-sm text-ink truncate max-w-[180px]">{item.topic}</span>
                          </div>
                          <span className="text-sm font-medium text-ink-light bg-warm-100 px-2 py-0.5 rounded-full">
                            {item.count}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Papers by Subject */}
              {Object.keys(analytics.papers.by_subject).length > 0 && (
                <div className="bg-surface rounded-2xl border border-warm-100 shadow-xl p-6 space-y-4">
                  <h2 className="font-display text-lg font-semibold text-ink flex items-center gap-2">
                    <Icons.GraduationCap className="w-5 h-5 text-accent" />
                    Papers by Subject
                  </h2>
                  <div className="flex flex-wrap gap-3">
                    {Object.entries(analytics.papers.by_subject).map(([subject, count]) => (
                      <div key={subject} className="bg-warm-50 rounded-xl px-4 py-3 flex items-center gap-3">
                        <span className="text-ink font-medium">{subject}</span>
                        <span className="bg-accent text-white text-xs font-bold px-2 py-1 rounded-full">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Performance Metrics */}
              {metrics && (
                <div className="bg-surface rounded-2xl border border-warm-100 shadow-xl p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="font-display text-lg font-semibold text-ink flex items-center gap-2">
                      <Icons.Activity className="w-5 h-5 text-accent" />
                      Performance Metrics
                    </h2>
                    <div className="flex gap-2">
                      {(['overview', 'nodes', 'errors'] as const).map((tab) => (
                        <button
                          key={tab}
                          onClick={() => setMetricsTab(tab)}
                          className={`px-3 py-1 text-xs rounded-lg font-medium transition-all ${
                            metricsTab === tab
                              ? 'bg-accent text-white'
                              : 'bg-warm-100 text-ink-light hover:bg-warm-200'
                          }`}
                        >
                          {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>

                  {metricsTab === 'overview' && metrics.summary && (
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      <div className="bg-blue-50 rounded-xl p-3 text-center">
                        <div className="text-xl font-bold text-blue-600">{metrics.summary.total_runs}</div>
                        <div className="text-xs text-blue-700">Total Runs</div>
                      </div>
                      <div className="bg-green-50 rounded-xl p-3 text-center">
                        <div className="text-xl font-bold text-green-600">{metrics.summary.successful}</div>
                        <div className="text-xs text-green-700">Successful</div>
                      </div>
                      <div className="bg-red-50 rounded-xl p-3 text-center">
                        <div className="text-xl font-bold text-red-600">{metrics.summary.failed}</div>
                        <div className="text-xs text-red-700">Failed</div>
                      </div>
                      <div className="bg-purple-50 rounded-xl p-3 text-center">
                        <div className="text-xl font-bold text-purple-600">{metrics.summary.success_rate}%</div>
                        <div className="text-xs text-purple-700">Success Rate</div>
                      </div>
                      <div className="bg-orange-50 rounded-xl p-3 text-center">
                        <div className="text-xl font-bold text-orange-600">{(metrics.summary.avg_duration_ms / 1000).toFixed(1)}s</div>
                        <div className="text-xs text-orange-700">Avg Duration</div>
                      </div>
                    </div>
                  )}

                  {metricsTab === 'nodes' && metrics.node_performance && (
                    <div className="space-y-2">
                      <div className="grid grid-cols-4 gap-2 text-xs font-medium text-ink-light px-3 py-2 bg-warm-50 rounded-lg">
                        <span>Node</span>
                        <span className="text-right">Calls</span>
                        <span className="text-right">Avg Time</span>
                        <span className="text-right">Success</span>
                      </div>
                      {Object.entries(metrics.node_performance).map(([node, perf]) => (
                        <div key={node} className="grid grid-cols-4 gap-2 text-sm px-3 py-2 rounded-lg hover:bg-warm-50 transition-colors">
                          <span className="font-medium text-ink">{node}</span>
                          <span className="text-right text-ink-light">{perf.calls}</span>
                          <span className="text-right text-ink-light">{(perf.avg_ms / 1000).toFixed(2)}s</span>
                          <span className={`text-right font-medium ${perf.success_rate >= 90 ? 'text-green-600' : perf.success_rate >= 70 ? 'text-yellow-600' : 'text-red-600'}`}>
                            {perf.success_rate}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {metricsTab === 'errors' && (
                    <div className="space-y-2">
                      {metrics.recent_errors && metrics.recent_errors.length > 0 ? (
                        metrics.recent_errors.map((err, idx) => (
                          <div key={idx} className="bg-red-50 rounded-lg p-3 text-sm">
                            <div className="font-medium text-red-800">{err.topic}</div>
                            <div className="text-red-600 text-xs mt-1 font-mono">{err.error || 'Unknown error'}</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-8 text-ink-light">
                          <Icons.Check className="w-8 h-8 mx-auto mb-2 text-green-500" />
                          No recent errors
                        </div>
                      )}
                    </div>
                  )}

                  {/* Action buttons */}
                  <div className="flex gap-2 pt-2 border-t border-warm-100">
                    <button
                      onClick={handleResetMetrics}
                      className="px-3 py-1.5 text-xs bg-warm-100 text-ink-light rounded-lg hover:bg-warm-200 transition-colors"
                    >
                      Reset Metrics
                    </button>
                    <button
                      onClick={handleReloadConfig}
                      className="px-3 py-1.5 text-xs bg-warm-100 text-ink-light rounded-lg hover:bg-warm-200 transition-colors"
                    >
                      Reload Prompts
                    </button>
                  </div>
                </div>
              )}

              {loadingMetrics && (
                <div className="flex items-center justify-center py-4">
                  <Icons.Activity className="w-5 h-5 text-accent animate-spin" />
                  <span className="ml-2 text-sm text-ink-light">Loading metrics...</span>
                </div>
              )}

              {/* Refresh Button */}
              <div className="flex justify-center">
                <button
                  onClick={() => { fetchAnalytics(); fetchMetrics(); }}
                  className="px-6 py-3 bg-accent text-white rounded-xl font-medium hover:bg-accent-hover transition-all shadow-lg shadow-accent/20 flex items-center gap-2"
                >
                  <Icons.Zap className="w-4 h-4" />
                  Refresh All
                </button>
              </div>
            </>
          ) : (
            <div className="text-center py-16 bg-warm-50/50 rounded-2xl border border-dashed border-warm-200">
              <Icons.Activity className="w-16 h-16 text-warm-300 mx-auto mb-4" />
              <p className="text-ink-light mb-4">Failed to load analytics data</p>
              <button
                onClick={fetchAnalytics}
                className="text-accent hover:text-accent-hover font-medium"
              >
                Try Again
              </button>
            </div>
          )}
        </div>
      )}

      {/* PDF EXPORT SETTINGS MODAL */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden">
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-accent to-orange-400 px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white">PDF Export Settings</h2>
                <p className="text-white/80 text-sm">
                  {exportWithAnswers ? 'Exporting with answers' : 'Exporting questions only'}
                </p>
              </div>
              <button
                onClick={() => setShowExportModal(false)}
                className="text-white/80 hover:text-white p-2"
              >
                <Icons.X className="w-6 h-6" />
              </button>
            </div>

            {/* Form Fields */}
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-ink-light mb-1">Course Code</label>
                  <input
                    type="text"
                    value={pdfSettings.course_code}
                    onChange={(e) => setPdfSettings({...pdfSettings, course_code: e.target.value})}
                    className="w-full px-3 py-2 rounded-lg border border-warm-200 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20 outline-none"
                    placeholder="e.g., IS353IA"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-ink-light mb-1">Semester</label>
                  <select
                    value={pdfSettings.semester}
                    onChange={(e) => setPdfSettings({...pdfSettings, semester: e.target.value})}
                    className="w-full px-3 py-2 rounded-lg border border-warm-200 text-sm focus:border-accent outline-none"
                  >
                    {['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'].map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-ink-light mb-1">Academic Year</label>
                  <input
                    type="text"
                    value={pdfSettings.academic_year}
                    onChange={(e) => setPdfSettings({...pdfSettings, academic_year: e.target.value})}
                    className="w-full px-3 py-2 rounded-lg border border-warm-200 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20 outline-none"
                    placeholder="e.g., 2024-2025"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-ink-light mb-1">UG/PG</label>
                  <select
                    value={pdfSettings.ug_pg}
                    onChange={(e) => setPdfSettings({...pdfSettings, ug_pg: e.target.value})}
                    className="w-full px-3 py-2 rounded-lg border border-warm-200 text-sm focus:border-accent outline-none"
                  >
                    <option value="UG">UG</option>
                    <option value="PG">PG</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-ink-light mb-1">Faculty Name(s)</label>
                <input
                  type="text"
                  value={pdfSettings.faculty}
                  onChange={(e) => setPdfSettings({...pdfSettings, faculty: e.target.value})}
                  className="w-full px-3 py-2 rounded-lg border border-warm-200 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20 outline-none"
                  placeholder="e.g., Dr. Smith / Prof. Jones"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-ink-light mb-1">Department</label>
                <input
                  type="text"
                  value={pdfSettings.department}
                  onChange={(e) => setPdfSettings({...pdfSettings, department: e.target.value})}
                  className="w-full px-3 py-2 rounded-lg border border-warm-200 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20 outline-none"
                  placeholder="e.g., Department of Computer Science"
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div className="border-t border-warm-100 px-6 py-4 flex justify-end gap-3">
              <button
                onClick={() => setShowExportModal(false)}
                className="px-4 py-2 bg-warm-100 text-ink rounded-xl text-sm font-medium hover:bg-warm-200 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handlePdfExport}
                className="px-4 py-2 bg-accent text-white rounded-xl text-sm font-medium hover:bg-accent-hover transition-all flex items-center gap-2"
              >
                <Icons.Download className="w-4 h-4" />
                Export PDF
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RUBRIC MODAL */}
      {showRubric && rubric && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-accent to-orange-400 px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white">Marking Rubric</h2>
                <p className="text-white/80 text-sm">{rubric.title} - {rubric.subject}</p>
              </div>
              <button
                onClick={() => {
                  setShowRubric(false);
                  setRubric(null);
                }}
                className="text-white/80 hover:text-white p-2"
              >
                <Icons.X className="w-6 h-6" />
              </button>
            </div>

            {/* Total Marks Banner */}
            <div className="bg-accent-soft/50 px-6 py-3 flex items-center justify-between border-b border-warm-100">
              <span className="text-ink font-medium">Total Paper Marks</span>
              <span className="text-2xl font-bold text-accent">{rubric.total_marks}</span>
            </div>

            {/* Rubric Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {rubric.sections.map((section, sIdx) => (
                <div key={sIdx} className="space-y-4">
                  <h3 className="font-display text-lg font-semibold text-ink border-b border-warm-100 pb-2">
                    {section.name}
                  </h3>
                  {section.questions.map((q: QuestionRubric, qIdx: number) => (
                    <div key={qIdx} className="bg-warm-50/50 rounded-xl p-4 space-y-3">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-3">
                          <span className="bg-ink text-white text-xs font-bold px-2 py-1 rounded-full">
                            Q{q.question_number}
                          </span>
                          <div>
                            <span className="text-sm font-medium text-ink">{q.topic}</span>
                            <span className="text-xs text-ink-faint ml-2">({q.total_marks} marks)</span>
                          </div>
                        </div>
                      </div>
                      {/* Criteria Table */}
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-warm-200">
                              <th className="text-left py-2 text-ink-light font-medium">Criterion</th>
                              <th className="text-center py-2 text-ink-light font-medium w-20">Marks</th>
                              <th className="text-left py-2 text-ink-light font-medium">Description</th>
                            </tr>
                          </thead>
                          <tbody>
                            {q.criteria.map((c, cIdx) => (
                              <tr key={cIdx} className="border-b border-warm-100 last:border-0">
                                <td className="py-2 text-ink font-medium">{c.criterion}</td>
                                <td className="py-2 text-center">
                                  <span className="bg-accent text-white text-xs font-bold px-2 py-0.5 rounded-full">
                                    {c.marks}
                                  </span>
                                </td>
                                <td className="py-2 text-ink-light">{c.description}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      {/* Model Answer */}
                      {q.model_answer && (
                        <div className="bg-green-50 rounded-lg p-3 mt-2">
                          <span className="text-xs font-bold text-green-700 uppercase">Model Answer</span>
                          <p className="text-sm text-green-800 mt-1">{q.model_answer}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>

            {/* Modal Footer */}
            <div className="border-t border-warm-100 px-6 py-4 flex justify-end gap-3">
              <button
                onClick={handleExportRubric}
                className="px-4 py-2 bg-accent text-white rounded-xl text-sm font-medium hover:bg-accent-hover transition-all flex items-center gap-2"
              >
                <Icons.Download className="w-4 h-4" />
                Download Markdown
              </button>
              <button
                onClick={() => {
                  setShowRubric(false);
                  setRubric(null);
                }}
                className="px-4 py-2 bg-warm-100 text-ink rounded-xl text-sm font-medium hover:bg-warm-200 transition-all"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Section Type Selection Modal */}
      {showSectionTypeModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-warm-50 rounded-2xl shadow-2xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="border-b border-warm-100 px-6 py-4">
              <h2 className="font-display text-2xl font-bold text-ink flex items-center gap-2">
                <Icons.Layers className="w-6 h-6 text-accent" />
                Choose Section Type
              </h2>
              <p className="text-sm text-ink-light mt-1">Select the type of questions for this section</p>
            </div>

            <div className="p-6 space-y-3">
              {/* Short Answer Section */}
              <button
                onClick={() => createSectionWithType('short')}
                className="w-full p-4 bg-white rounded-xl border-2 border-accent/20 hover:border-accent hover:shadow-lg transition-all text-left group"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-blue-200 transition-colors">
                    <Icons.FileText className="w-6 h-6 text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink text-lg">Short Answer Questions</h3>
                    <p className="text-sm text-ink-light mt-1">Brief answers in 2-3 sentences • 2 marks each</p>
                    <div className="flex gap-2 mt-2">
                      <span className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded-full font-medium">2 Marks</span>
                      <span className="text-xs px-2 py-1 bg-warm-100 text-ink-faint rounded-full">Short Type</span>
                    </div>
                  </div>
                </div>
              </button>

              {/* Long Answer Section */}
              <button
                onClick={() => createSectionWithType('long')}
                className="w-full p-4 bg-white rounded-xl border-2 border-accent/20 hover:border-accent hover:shadow-lg transition-all text-left group"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-purple-200 transition-colors">
                    <Icons.Book className="w-6 h-6 text-purple-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink text-lg">Long Answer Questions</h3>
                    <p className="text-sm text-ink-light mt-1">Detailed answers with examples and explanations • 5 marks each</p>
                    <div className="flex gap-2 mt-2">
                      <span className="text-xs px-2 py-1 bg-purple-50 text-purple-700 rounded-full font-medium">5 Marks</span>
                      <span className="text-xs px-2 py-1 bg-warm-100 text-ink-faint rounded-full">Long Type</span>
                    </div>
                  </div>
                </div>
              </button>

              {/* MCQ Section */}
              <button
                onClick={() => createSectionWithType('mcq')}
                className="w-full p-4 bg-white rounded-xl border-2 border-accent/20 hover:border-accent hover:shadow-lg transition-all text-left group"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-green-200 transition-colors">
                    <Icons.Check className="w-6 h-6 text-green-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink text-lg">Multiple Choice Questions</h3>
                    <p className="text-sm text-ink-light mt-1">Choose the correct option from 4 choices • 1 mark each</p>
                    <div className="flex gap-2 mt-2">
                      <span className="text-xs px-2 py-1 bg-green-50 text-green-700 rounded-full font-medium">1 Mark</span>
                      <span className="text-xs px-2 py-1 bg-warm-100 text-ink-faint rounded-full">MCQ Type</span>
                    </div>
                  </div>
                </div>
              </button>

              {/* Numerical Section */}
              <button
                onClick={() => createSectionWithType('numerical')}
                className="w-full p-4 bg-white rounded-xl border-2 border-accent/20 hover:border-accent hover:shadow-lg transition-all text-left group"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-orange-200 transition-colors">
                    <Icons.Code className="w-6 h-6 text-orange-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink text-lg">Numerical Problems</h3>
                    <p className="text-sm text-ink-light mt-1">Calculations and problem-solving with steps • 3 marks each</p>
                    <div className="flex gap-2 mt-2">
                      <span className="text-xs px-2 py-1 bg-orange-50 text-orange-700 rounded-full font-medium">3 Marks</span>
                      <span className="text-xs px-2 py-1 bg-warm-100 text-ink-faint rounded-full">Numerical Type</span>
                    </div>
                  </div>
                </div>
              </button>

              {/* Mixed Section */}
              <button
                onClick={() => createSectionWithType('mixed')}
                className="w-full p-4 bg-white rounded-xl border-2 border-accent/20 hover:border-accent hover:shadow-lg transition-all text-left group"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-pink-100 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-pink-200 transition-colors">
                    <Icons.Sparkles className="w-6 h-6 text-pink-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink text-lg">Mixed Questions</h3>
                    <p className="text-sm text-ink-light mt-1">Flexible section with different question types • Variable marks</p>
                    <div className="flex gap-2 mt-2">
                      <span className="text-xs px-2 py-1 bg-pink-50 text-pink-700 rounded-full font-medium">Variable</span>
                      <span className="text-xs px-2 py-1 bg-warm-100 text-ink-faint rounded-full">Mixed Type</span>
                    </div>
                  </div>
                </div>
              </button>
            </div>

            <div className="border-t border-warm-100 px-6 py-4 flex justify-end">
              <button
                onClick={() => setShowSectionTypeModal(false)}
                className="px-4 py-2 bg-warm-100 text-ink rounded-xl text-sm font-medium hover:bg-warm-200 transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PaperGeneratorModule;
