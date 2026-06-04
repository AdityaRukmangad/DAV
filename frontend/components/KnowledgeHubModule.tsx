import React, { useState, useEffect, useMemo } from 'react';
import { getSyllabusInfo, getPYQPapers, getDocuments, deleteDocument } from '../services/api';
import { SyllabusInfo, PYQPapersResponse, UploadedDocument } from '../types';
import { Icons } from './ui/SystemIcons';

const KnowledgeHubModule: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'syllabus' | 'pyq' | 'documents'>('syllabus');
  const [syllabusData, setSyllabusData] = useState<SyllabusInfo | null>(null);
  const [pyqData, setPyqData] = useState<PYQPapersResponse | null>(null);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedUnits, setExpandedUnits] = useState<Set<number>>(new Set([1]));

  const guessUnitFromFilename = (filename: string): number | null => {
    const match = filename.match(/unit\s*([0-9]+)/i) || filename.match(/u(?:nit)?[_-]?([0-9]+)/i);
    if (match && match[1]) {
      const num = parseInt(match[1], 10);
      return Number.isFinite(num) ? num : null;
    }
    return null;
  };

  const documentsByUnit = useMemo(() => {
    const buckets: Record<string, { unitNumber: number | null; unitName: string; docs: UploadedDocument[] }> = {};

    // Pre-create buckets for known units
    syllabusData?.units?.forEach((u) => {
      const key = String(u.unit_number);
      if (!buckets[key]) {
        buckets[key] = { unitNumber: u.unit_number, unitName: u.unit_name, docs: [] };
      }
    });

    documents.forEach((doc) => {
      const guessed = guessUnitFromFilename(doc.filename);
      const key = guessed !== null ? String(guessed) : 'unassigned';
      const unitName = guessed !== null
        ? syllabusData?.units?.find((u) => u.unit_number === guessed)?.unit_name || `Unit ${guessed}`
        : 'Unassigned';

      if (!buckets[key]) {
        buckets[key] = { unitNumber: guessed, unitName, docs: [] };
      }
      buckets[key].docs.push(doc);
    });

    return Object.values(buckets).sort((a, b) => {
      if (a.unitNumber === null) return 1;
      if (b.unitNumber === null) return -1;
      return (a.unitNumber || 0) - (b.unitNumber || 0);
    });
  }, [documents, syllabusData]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const [syllabus, pyq, docs] = await Promise.all([
        getSyllabusInfo(),
        getPYQPapers(),
        getDocuments()
      ]);
      
      console.log('Raw PYQ data:', pyq);
      
      // Ensure the data structure is correct
      const processedSyllabus: SyllabusInfo = {
        course_info: syllabus.course_info || { code: '', name: '', semester: 0, credits: 0 },
        course_outcomes: Array.isArray(syllabus.course_outcomes) ? syllabus.course_outcomes : [],
        co_po_mapping: syllabus.co_po_mapping || {},
        units: Array.isArray(syllabus.units) ? syllabus.units : []
      };
      
      // Process PYQ data with safe defaults
      const processedPyq: PYQPapersResponse = {
        patterns_summary: pyq?.patterns_summary || undefined,
        papers: Array.isArray(pyq?.papers) ? pyq.papers : []
      };
      
      setSyllabusData(processedSyllabus);
      setPyqData(processedPyq);
      setDocuments(docs || []);
    } catch (err: any) {
      console.error('Error loading data:', err);
      setError(err.message || 'Failed to load knowledge hub data');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDocument = async (filename: string) => {
    if (!window.confirm(`Delete "${filename}"? This will remove all its content from the knowledge base.`)) {
      return;
    }

    try {
      const result = await deleteDocument(filename);
      if (result.success) {
        setDocuments(docs => docs.filter(d => d.filename !== filename));
      } else {
        alert(`Failed to delete: ${result.message}`);
      }
    } catch (error) {
      console.error('Delete error:', error);
      alert('Failed to delete document');
    }
  };

  const toggleUnit = (unitNum: number) => {
    const newExpanded = new Set(expandedUnits);
    if (newExpanded.has(unitNum)) {
      newExpanded.delete(unitNum);
    } else {
      newExpanded.add(unitNum);
    }
    setExpandedUnits(newExpanded);
  };

  const deriveStats = (paper: any) => {
    // try to gather questions from common shapes
    const rawQuestions =
      paper.questions ||
      paper.question_list ||
      paper.items ||
      (paper.groups ? paper.groups.flatMap((g: any) => g.questions || g.items || []) : []) ||
      [];

    const questions: any[] = Array.isArray(rawQuestions) ? rawQuestions : [];

    const totalQuestions =
      paper.stats?.total_questions ??
      paper.total_questions ??
      questions.length ??
      0;

    const totalMarks =
      paper.stats?.total_marks ??
      paper.total_marks ??
      questions.reduce((sum, q) => sum + (q.marks ?? q.mark ?? q.total_marks ?? 0), 0);

    const uniqueCos =
      paper.stats?.unique_cos ??
      paper.unique_cos ??
      new Set(
        questions
          .map((q) => q.co || q.co_code || q.co_mapping || q.co_id)
          .filter(Boolean)
      ).size;

    const type_distribution =
      paper.stats?.type_distribution ??
      paper.type_distribution ??
      undefined;

    const difficulty_distribution =
      paper.stats?.difficulty_distribution ??
      paper.difficulty_distribution ??
      undefined;

    const co_distribution =
      paper.stats?.co_distribution ??
      paper.co_distribution ??
      (() => {
        if (!questions.length) return undefined;
        return questions.reduce((acc: Record<string, number>, q) => {
          const co = (q.co || q.co_code || q.co_mapping || q.co_id) as string | undefined;
          if (!co) return acc;
          acc[co] = (acc[co] || 0) + 1;
          return acc;
        }, {});
      })();

    return {
      total_questions: totalQuestions,
      total_marks: totalMarks,
      unique_cos: uniqueCos,
      type_distribution,
      difficulty_distribution,
      co_distribution,
    };
  };

  const categorizePaper = (paper: any): 'CIE' | 'MQP' | 'SEE' | null => {
    const name = (paper.exam_name || paper.title || paper.name || '').toLowerCase();
    if (name.includes('cie')) return 'CIE';
    if (name.includes('see')) return 'SEE';
    if (name.includes('mqp') || name.includes('model') || name.includes('mock')) return 'MQP';
    return null;
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto w-full py-10 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-6">
          <div className="relative w-16 h-16">
            <div className="absolute inset-0 border-4 border-warm-200 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-accent rounded-full border-t-transparent animate-spin"></div>
          </div>
          <p className="text-ink-light text-lg">Loading knowledge hub...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto w-full py-10">
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6 flex items-center gap-4">
          <Icons.Error className="w-6 h-6 text-red-600" />
          <div>
            <p className="font-semibold text-red-900">Failed to load knowledge hub</p>
            <p className="text-red-700 text-sm mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!syllabusData) {
    return null;
  }

  return (
    <div className="max-w-7xl mx-auto w-full py-10 space-y-8 animate-slide-up">
      
      {/* Header */}
      <div className="text-center space-y-4">
        <h2 className="font-display text-5xl font-semibold text-ink tracking-tight">Knowledge Hub</h2>
        <p className="text-ink-light text-lg max-w-3xl mx-auto">
          View the course syllabus and previous year question papers that guide the question generation system
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center justify-center gap-4">
        <button
          onClick={() => setActiveTab('syllabus')}
          className={`
            px-8 py-4 rounded-2xl font-semibold text-lg transition-all duration-300
            ${activeTab === 'syllabus' 
              ? 'bg-accent text-white shadow-lg shadow-accent/30' 
              : 'bg-white text-ink border border-warm-200 hover:border-accent hover:bg-warm-50'
            }
          `}
        >
          <div className="flex items-center gap-3">
            <Icons.Document className="w-6 h-6" />
            <span>Syllabus</span>
            {syllabusData.units.length > 0 && (
              <span className="px-2 py-1 bg-white/20 rounded-full text-xs">
                {syllabusData.units.length} Units
              </span>
            )}
          </div>
        </button>

        <button
          onClick={() => setActiveTab('pyq')}
          className={`
            px-8 py-4 rounded-2xl font-semibold text-lg transition-all duration-300
            ${activeTab === 'pyq' 
              ? 'bg-accent text-white shadow-lg shadow-accent/30' 
              : 'bg-white text-ink border border-warm-200 hover:border-accent hover:bg-warm-50'
            }
          `}
        >
          <div className="flex items-center gap-3">
            <Icons.Question className="w-6 h-6" />
            <span>PYQ Papers</span>
            {pyqData?.papers && pyqData.papers.length > 0 && (
              <span className="px-2 py-1 bg-white/20 rounded-full text-xs">
                {pyqData.papers.length}
              </span>
            )}
          </div>
        </button>

        <button
          onClick={() => setActiveTab('documents')}
          className={`
            px-8 py-4 rounded-2xl font-semibold text-lg transition-all duration-300
            ${activeTab === 'documents' 
              ? 'bg-accent text-white shadow-lg shadow-accent/30' 
              : 'bg-white text-ink border border-warm-200 hover:border-accent hover:bg-warm-50'
            }
          `}
        >
          <div className="flex items-center gap-3">
            <Icons.Upload className="w-6 h-6" />
            <span>Documents</span>
            {documents.length > 0 && (
              <span className="px-2 py-1 bg-white/20 rounded-full text-xs">
                {documents.length}
              </span>
            )}
          </div>
        </button>
      </div>

      {/* Content Area */}
      <div className="mt-8">
        {activeTab === 'syllabus' && (
          <div className="space-y-6">
            
            {/* Course Info Card */}
            <div className="bg-white rounded-3xl p-8 border border-warm-200 shadow-lg">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="text-3xl font-display font-bold text-ink mb-2">
                    {syllabusData.course_info.code}: {syllabusData.course_info.name}
                  </h3>
                  <div className="flex flex-wrap items-center gap-4 mt-4">
                    <div className="px-4 py-2 bg-accent-soft text-accent rounded-xl font-semibold">
                      Semester {syllabusData.course_info.semester}
                    </div>
                    <div className="px-4 py-2 bg-warm-100 text-ink rounded-xl font-semibold">
                      {syllabusData.course_info.credits} Credits
                    </div>
                    <div className="px-4 py-2 bg-blue-50 text-blue-600 rounded-xl font-semibold">
                      {syllabusData.units.length} Units
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* CO-PO Mapping */}
            {syllabusData.course_outcomes.length > 0 && (
              <div className="bg-white rounded-3xl p-8 border border-warm-200 shadow-lg">
                <h4 className="text-xl font-display font-bold text-ink mb-4 flex items-center gap-3">
                  <div className="w-10 h-10 bg-purple-100 text-purple-600 rounded-xl flex items-center justify-center">
                    <Icons.Target className="w-6 h-6" />
                  </div>
                  Course Outcomes Mapping
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                  {syllabusData.course_outcomes.map((co) => (
                    <div key={co.code} className="p-4 bg-warm-50 rounded-xl border border-warm-100">
                      <div className="flex items-start gap-3">
                        <span className="px-3 py-1 bg-purple-100 text-purple-600 rounded-lg font-bold text-sm">
                          {co.code}
                        </span>
                        <p className="text-sm text-ink-light flex-1">{co.description}</p>
                      </div>
                      {syllabusData.co_po_mapping?.[co.code] && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {Object.entries(syllabusData.co_po_mapping[co.code]).map(([po, level]) => (
                            <span key={po} className="px-2 py-1 bg-white rounded text-xs font-medium text-ink">
                              {po}: {level}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Units */}
            {syllabusData.units.length > 0 && (
              <div className="space-y-4">
                {syllabusData.units.map((unit) => (
                  <div key={unit.unit_number} className="bg-white rounded-3xl border border-warm-200 shadow-lg overflow-hidden">
                    
                    {/* Unit Header */}
                    <button
                      onClick={() => toggleUnit(unit.unit_number)}
                      className="w-full p-6 flex items-center justify-between hover:bg-warm-50 transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-accent text-white rounded-2xl flex items-center justify-center font-bold text-xl">
                          {unit.unit_number}
                        </div>
                        <div className="text-left">
                          <h4 className="text-2xl font-display font-bold text-ink">{unit.unit_name}</h4>
                          <div className="flex items-center gap-3 mt-2">
                            <span className="text-sm text-ink-light">{unit.topics?.length || 0} Topics</span>
                            {unit.co_mapping && unit.co_mapping.length > 0 && (
                              <>
                                <span className="text-sm text-ink-light">•</span>
                                <div className="flex gap-1">
                                  {unit.co_mapping.map((co) => (
                                    <span key={co} className="px-2 py-0.5 bg-purple-100 text-purple-600 rounded text-xs font-semibold">
                                      {co}
                                    </span>
                                  ))}
                                </div>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      <Icons.ChevronRight 
                        className={`w-6 h-6 text-ink-light transition-transform duration-300 ${
                          expandedUnits.has(unit.unit_number) ? 'rotate-90' : ''
                        }`}
                      />
                    </button>

                    {/* Unit Content */}
                    {expandedUnits.has(unit.unit_number) && unit.topics && (
                      <div className="px-6 pb-6 space-y-4 animate-fade-in">
                        {unit.topics.map((topic, idx) => (
                          <div key={idx} className="p-4 bg-warm-50 rounded-2xl border border-warm-100">
                            <h5 className="font-semibold text-ink mb-2">{topic.name}</h5>
                            {topic.subtopics && topic.subtopics.length > 0 && (
                              <ul className="ml-4 space-y-1">
                                {topic.subtopics.map((subtopic, subIdx) => (
                                  <li key={subIdx} className="text-sm text-ink-light flex items-start gap-2">
                                    <span className="text-accent mt-1">•</span>
                                    <span>{subtopic}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                            {topic.bloom_levels && topic.bloom_levels.length > 0 && (
                              <div className="flex flex-wrap gap-2 mt-3">
                                {topic.bloom_levels.map((bloom, bloomIdx) => (
                                  <span key={bloomIdx} className="px-2 py-1 bg-blue-100 text-blue-600 rounded text-xs font-medium">
                                    {bloom}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'pyq' && pyqData && (
          <div className="space-y-6">
            {(!pyqData.papers || pyqData.papers.length === 0) ? (
              <div className="bg-white rounded-3xl p-12 border border-warm-200 shadow-lg text-center">
                <div className="w-20 h-20 bg-warm-100 text-ink-light rounded-full flex items-center justify-center mx-auto mb-6">
                  <Icons.Question className="w-10 h-10" />
                </div>
                <h3 className="text-2xl font-display font-bold text-ink mb-3">No PYQ Papers Available</h3>
                <p className="text-ink-light max-w-md mx-auto">
                  Upload previous year question papers to help the system learn patterns and generate better questions
                </p>
              </div>
            ) : (
              <>
                {/* Pattern Summary - Only show if data exists */}
                {pyqData.patterns_summary && 
                 typeof pyqData.patterns_summary.total_questions === 'number' && 
                 typeof pyqData.patterns_summary.unique_topics === 'number' && (
                  <div className="bg-gradient-to-br from-accent to-accent-dark text-white rounded-3xl p-8 shadow-2xl">
                    <h3 className="text-3xl font-display font-bold mb-6 flex items-center gap-3">
                      <Icons.Sparkles className="w-8 h-8" />
                      Learned Patterns
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="bg-white/10 backdrop-blur rounded-2xl p-6">
                        <p className="text-white/80 text-sm font-semibold mb-2">Total Questions</p>
                        <p className="text-4xl font-bold">{pyqData.patterns_summary.total_questions}</p>
                      </div>
                      <div className="bg-white/10 backdrop-blur rounded-2xl p-6">
                        <p className="text-white/80 text-sm font-semibold mb-2">Unique Topics</p>
                        <p className="text-4xl font-bold">{pyqData.patterns_summary.unique_topics}</p>
                      </div>
                      <div className="bg-white/10 backdrop-blur rounded-2xl p-6">
                        <p className="text-white/80 text-sm font-semibold mb-2">Papers Analyzed</p>
                        <p className="text-4xl font-bold">{pyqData.papers.length}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* PYQ Paper Cards */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {pyqData.papers.map((paper, idx) => (
                    <div key={idx} className="bg-white rounded-3xl border border-warm-200 shadow-lg overflow-hidden">
                      
                      {/* Paper Header */}
                      <div className="bg-gradient-to-r from-accent-soft to-warm-100 p-6 flex items-start justify-between gap-3">
                        <div>
                          <h4 className="text-2xl font-display font-bold text-ink mb-2">{paper.exam_name}</h4>
                          <p className="text-ink-light font-semibold">{paper.academic_year}</p>
                        </div>
                        {(() => {
                          const pdfUrl =
                            paper.pdf_url ||
                            paper.file_url ||
                            paper.url ||
                            paper.link;
                          if (!pdfUrl) return null;
                          return (
                            <a
                              href={pdfUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-white text-ink border border-warm-200 hover:border-accent hover:text-accent transition"
                            >
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                className="w-5 h-5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth={2}
                              >
                                <path d="M1.5 12s3.5-7 10.5-7 10.5 7 10.5 7-3.5 7-10.5 7S1.5 12 1.5 12Z" />
                                <circle cx="12" cy="12" r="3.5" />
                              </svg>
                              <span className="text-sm font-semibold">View PDF</span>
                            </a>
                          );
                        })()}
                      </div>

                      {/* Paper Stats */}
                      <div className="p-6 space-y-6">
                        
                        {/* Basic Stats */}
                        {(() => {
                          const stats = { ...deriveStats(paper) };
                          const category = categorizePaper(paper);

                          if (category === 'CIE') {
                            stats.total_marks = 60;
                          }
                          if (category === 'SEE' || category === 'MQP') {
                            stats.total_marks = 100;
                            stats.total_questions = 35;
                          }

                          return (
                            <>
                              <div className="grid grid-cols-3 gap-4">
                                <div className="text-center p-3 bg-blue-50 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600">{stats.total_questions}</p>
                                  <p className="text-xs text-blue-600/70 font-semibold mt-1">Questions</p>
                                </div>
                                <div className="text-center p-3 bg-green-50 rounded-xl">
                                  <p className="text-2xl font-bold text-green-600">{stats.total_marks}</p>
                                  <p className="text-xs text-green-600/70 font-semibold mt-1">Total Marks</p>
                                </div>
                                <div className="text-center p-3 bg-purple-50 rounded-xl">
                                  <p className="text-2xl font-bold text-purple-600">{stats.unique_cos}</p>
                                  <p className="text-xs text-purple-600/70 font-semibold mt-1">COs Covered</p>
                                </div>
                              </div>

                              {stats.type_distribution && Object.keys(stats.type_distribution).length > 0 && (
                                <div>
                                  <p className="text-sm font-semibold text-ink-light mb-3">Question Types</p>
                                  <div className="flex flex-wrap gap-2">
                                    {Object.entries(stats.type_distribution).map(([type, count]) => (
                                      <div key={type} className="px-3 py-2 bg-warm-50 rounded-lg border border-warm-100">
                                        <span className="font-semibold text-ink capitalize">{type}</span>
                                        <span className="ml-2 text-accent font-bold">×{count}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {stats.difficulty_distribution && Object.keys(stats.difficulty_distribution).length > 0 && (
                                <div>
                                  <p className="text-sm font-semibold text-ink-light mb-3">Difficulty Levels</p>
                                  <div className="space-y-2">
                                    {Object.entries(stats.difficulty_distribution).map(([difficulty, count]) => {
                                      const total = stats.total_questions || 1;
                                      const percentage = ((count / total) * 100).toFixed(0);
                                      const colors: Record<string, string> = {
                                        easy: 'bg-green-500',
                                        medium: 'bg-yellow-500',
                                        hard: 'bg-red-500',
                                      };
                                      const bgColor = colors[difficulty.toLowerCase()] || 'bg-gray-500';
                                      return (
                                        <div key={difficulty} className="flex items-center gap-3">
                                          <span className="text-sm font-medium text-ink w-20 capitalize">{difficulty}</span>
                                          <div className="flex-1 h-6 bg-warm-100 rounded-full overflow-hidden">
                                            <div
                                              className={`h-full ${bgColor} transition-all duration-500 flex items-center justify-end pr-2`}
                                              style={{ width: `${percentage}%` }}
                                            >
                                              {percentage !== '0' && (
                                                <span className="text-xs text-white font-bold">{count}</span>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}

                              {stats.co_distribution && Object.keys(stats.co_distribution).length > 0 && (
                                <div>
                                  <p className="text-sm font-semibold text-ink-light mb-3">Course Outcome Coverage</p>
                                  <div className="flex flex-wrap gap-2">
                                    {Object.entries(stats.co_distribution)
                                      .sort(([a], [b]) => a.localeCompare(b))
                                      .map(([co, count]) => (
                                        <div key={co} className="px-3 py-2 bg-purple-50 rounded-lg border border-purple-100">
                                          <span className="font-bold text-purple-600">{co}</span>
                                          <span className="ml-2 text-purple-600">×{count}</span>
                                        </div>
                                      ))}
                                  </div>
                                </div>
                              )}
                            </>
                          );
                        })()}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'documents' && (
          <div className="space-y-6">
            {documents.length === 0 ? (
              <div className="bg-white rounded-3xl p-12 border border-warm-200 shadow-lg text-center">
                <div className="w-20 h-20 bg-warm-100 text-ink-light rounded-full flex items-center justify-center mx-auto mb-6">
                  <Icons.Upload className="w-10 h-10" />
                </div>
                <h3 className="text-2xl font-display font-bold text-ink mb-3">No Documents Uploaded</h3>
                <p className="text-ink-light max-w-md mx-auto">
                  Upload PDF documents to build the knowledge base for question generation
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {documentsByUnit.map((bucket, idx) => (
                  <div
                    key={`${bucket.unitNumber ?? 'unassigned'}-${idx}`}
                    className="bg-white rounded-3xl border border-warm-200 shadow-lg overflow-hidden"
                  >
                    <div className="p-5 flex items-center justify-between bg-warm-50 border-b border-warm-200">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-2xl bg-accent text-white flex items-center justify-center font-bold text-xl">
                          {bucket.unitNumber !== null ? bucket.unitNumber : '?'}
                        </div>
                        <div>
                          <h4 className="text-lg font-display font-bold text-ink">
                            {bucket.unitNumber !== null ? `Unit ${bucket.unitNumber}` : 'Unassigned'}
                          </h4>
                          <p className="text-sm text-ink-light">{bucket.unitName}</p>
                        </div>
                      </div>
                      <div className="text-sm text-ink-light">
                        {bucket.docs.length} file{bucket.docs.length !== 1 ? 's' : ''}
                      </div>
                    </div>

                    <div className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {bucket.docs.map((doc, docIdx) => (
                        <div
                          key={docIdx}
                          className="rounded-2xl border border-warm-200 shadow-sm hover:shadow-md transition-all bg-white overflow-hidden"
                        >
                          <div className="bg-gradient-to-r from-red-50 to-red-100 p-4 flex items-start gap-3">
                            <div className="w-12 h-14 bg-gradient-to-br from-red-500 to-red-600 rounded-lg flex items-center justify-center text-white font-bold shadow-sm">
                              PDF
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-semibold text-ink text-sm truncate" title={doc.filename}>{doc.filename}</p>
                              <div className="text-xs text-ink-light flex items-center gap-2 mt-1">
                                <Icons.Database className="w-3 h-3" />
                                {doc.chunks} chunks
                              </div>
                            </div>
                          </div>
                          <div className="p-4 space-y-3">
                            <div className="flex items-center justify-between text-[11px]">
                              <span className="text-ink-light">Hash</span>
                              <span className="font-mono text-ink font-semibold truncate max-w-[160px]">{doc.hash}</span>
                            </div>
                            <button
                              onClick={() => handleDeleteDocument(doc.filename)}
                              className="w-full px-3 py-2 bg-red-50 text-red-600 rounded-lg font-semibold hover:bg-red-100 transition flex items-center justify-center gap-2 border border-red-200 text-sm"
                            >
                              <Icons.Trash className="w-4 h-4" />
                              Delete
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeHubModule;
