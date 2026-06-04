import React, { useState, useEffect } from 'react';
import { Icons } from './ui/SystemIcons';

interface Question {
  id: string;
  question_text: string;
  marks: number;
  difficulty: string;
  bloom_level: string;
  co: string;
  unit_number: number;
  unit_name: string;
  topic?: string;
  type?: string;
  answer?: string;
  explanation?: string;
  computed_answer?: string;
  source_filename?: string;
  source_pages?: (number | string)[];
  question_id?: number;
  generated_at: string;
}

interface QuestionsByUnit {
  [unitNumber: number]: {
    unit_name: string;
    questions: Question[];
  };
}

const QuestionBankModule: React.FC = () => {
  const [questionsByUnit, setQuestionsByUnit] = useState<QuestionsByUnit>({});
  const [expandedUnits, setExpandedUnits] = useState<Set<number>>(new Set());
  const [selectedUnit, setSelectedUnit] = useState<number | 'all'>('all');
  const [selectedType, setSelectedType] = useState<string>('all');

  useEffect(() => {
    loadQuestions();
  }, []);

  const loadQuestions = () => {
    try {
      const stored = localStorage.getItem('question_bank');
      if (stored) {
        const parsed = JSON.parse(stored);
        setQuestionsByUnit(parsed);
      }
    } catch (error) {
      console.error('Failed to load question bank:', error);
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

  const deleteQuestion = (unitNumber: number, questionId: string) => {
    const updated = { ...questionsByUnit };
    if (updated[unitNumber]) {
      updated[unitNumber].questions = updated[unitNumber].questions.filter(
        (q) => q.id !== questionId
      );
      if (updated[unitNumber].questions.length === 0) {
        delete updated[unitNumber];
      }
      localStorage.setItem('question_bank', JSON.stringify(updated));
      setQuestionsByUnit(updated);
    }
  };

  const clearUnit = (unitNumber: number) => {
    if (window.confirm(`Delete all questions from Unit ${unitNumber}?`)) {
      const updated = { ...questionsByUnit };
      delete updated[unitNumber];
      localStorage.setItem('question_bank', JSON.stringify(updated));
      setQuestionsByUnit(updated);
    }
  };

  const clearAll = () => {
    if (window.confirm('Delete all questions from the Question Bank?')) {
      localStorage.removeItem('question_bank');
      setQuestionsByUnit({});
    }
  };

  const exportQuestions = () => {
    const dataStr = JSON.stringify(questionsByUnit, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `question-bank-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const units = Object.keys(questionsByUnit)
    .map(Number)
    .sort((a, b) => a - b);

  const filteredUnits =
    selectedUnit === 'all' ? units : units.filter((u) => u === selectedUnit);

  // Get all unique question types
  const allQuestionTypes = new Set<string>();
  units.forEach((unit) => {
    questionsByUnit[unit]?.questions.forEach((q) => {
      if (q.type) {
        allQuestionTypes.add(q.type.toLowerCase());
      }
    });
  });

  const questionTypes = Array.from(allQuestionTypes).sort();

  // Filter questions by type
  const getFilteredQuestions = (questions: Question[]) => {
    if (selectedType === 'all') return questions;
    return questions.filter((q) => q.type?.toLowerCase() === selectedType);
  };

  const totalQuestions = units.reduce(
    (sum, unit) => sum + (questionsByUnit[unit]?.questions.length || 0),
    0
  );

  const filteredQuestionsCount = units.reduce((sum, unit) => {
    const questions = questionsByUnit[unit]?.questions || [];
    return sum + getFilteredQuestions(questions).length;
  }, 0);

  return (
    <div className="max-w-7xl mx-auto w-full py-10 space-y-8 animate-slide-up">
      {/* Header */}
      <div className="text-center space-y-4">
        <h2 className="font-display text-5xl font-semibold text-ink tracking-tight">
          Question Bank
        </h2>
        <p className="text-ink-light text-lg max-w-3xl mx-auto">
          All generated questions organized by units for easy access and reuse
        </p>
      </div>

      {/* Stats Bar */}
      <div className="bg-white rounded-3xl p-6 border border-warm-200 shadow-lg">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center">
                <Icons.Question className="w-6 h-6" />
              </div>
              <div>
                <p className="text-3xl font-bold text-ink">
                  {selectedType === 'all' ? totalQuestions : filteredQuestionsCount}
                </p>
                <p className="text-sm text-ink-light">
                  {selectedType === 'all' ? 'Total Questions' : 
                   selectedType === 'mcq' ? 'MCQ Questions' :
                   selectedType === 'short_ans' ? 'Short Answer' :
                   selectedType === 'long_ans' ? 'Long Answer' :
                   selectedType === 'numerical' ? 'Numerical' :
                   `${selectedType.replace(/_/g, ' ')} Questions`}
                </p>
              </div>
            </div>
            <div className="w-px h-12 bg-warm-200"></div>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-purple-100 text-purple-600 rounded-2xl flex items-center justify-center">
                <Icons.Document className="w-6 h-6" />
              </div>
              <div>
                <p className="text-3xl font-bold text-ink">{units.length}</p>
                <p className="text-sm text-ink-light">Units Covered</p>
              </div>
            </div>
            {questionTypes.length > 0 && (
              <>
                <div className="w-px h-12 bg-warm-200"></div>
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-green-100 text-green-600 rounded-2xl flex items-center justify-center">
                    <Icons.Layers className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-3xl font-bold text-ink">{questionTypes.length}</p>
                    <p className="text-sm text-ink-light">Question Types</p>
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="flex items-center gap-3">
            {totalQuestions > 0 && (
              <>
                <button
                  onClick={exportQuestions}
                  className="px-4 py-2 bg-accent text-white rounded-xl font-semibold hover:bg-accent-dark transition flex items-center gap-2"
                >
                  <Icons.Download className="w-5 h-5" />
                  Export
                </button>
                <button
                  onClick={clearAll}
                  className="px-4 py-2 bg-red-50 text-red-600 rounded-xl font-semibold hover:bg-red-100 transition flex items-center gap-2"
                >
                  <Icons.Trash className="w-5 h-5" />
                  Clear All
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Filter */}
      {units.length > 0 && (
        <div className="space-y-4">
          {/* Unit Filter */}
          {units.length > 1 && (
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-semibold text-ink-light">Filter by Unit:</span>
              <button
                onClick={() => setSelectedUnit('all')}
                className={`px-4 py-2 rounded-xl font-semibold transition ${
                  selectedUnit === 'all'
                    ? 'bg-accent text-white'
                    : 'bg-white text-ink border border-warm-200 hover:border-accent'
                }`}
              >
                All Units
              </button>
              {units.map((unit) => (
                <button
                  key={unit}
                  onClick={() => setSelectedUnit(unit)}
                  className={`px-4 py-2 rounded-xl font-semibold transition ${
                    selectedUnit === unit
                      ? 'bg-accent text-white'
                      : 'bg-white text-ink border border-warm-200 hover:border-accent'
                  }`}
                >
                  Unit {unit}
                </button>
              ))}
            </div>
          )}

          {/* Question Type Filter */}
          {questionTypes.length > 0 && (
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-semibold text-ink-light">Filter by Type:</span>
              <button
                onClick={() => setSelectedType('all')}
                className={`px-4 py-2 rounded-xl font-semibold transition ${
                  selectedType === 'all'
                    ? 'bg-green-600 text-white'
                    : 'bg-white text-ink border border-warm-200 hover:border-green-600'
                }`}
              >
                All Types
              </button>
              {questionTypes.map((type) => (
                <button
                  key={type}
                  onClick={() => setSelectedType(type)}
                  className={`px-4 py-2 rounded-xl font-semibold transition ${
                    selectedType === type
                      ? 'bg-green-600 text-white'
                      : 'bg-white text-ink border border-warm-200 hover:border-green-600'
                  }`}
                >
                  {type === 'mcq' ? 'MCQ' : 
                   type === 'short_ans' ? 'Short Answer' :
                   type === 'long_ans' ? 'Long Answer' :
                   type === 'numerical' ? 'Numerical' :
                   type.replace(/_/g, ' ').toUpperCase()}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Questions by Unit */}
      {totalQuestions === 0 ? (
        <div className="bg-white rounded-3xl p-12 border border-warm-200 shadow-lg text-center">
          <div className="w-20 h-20 bg-warm-100 text-ink-light rounded-full flex items-center justify-center mx-auto mb-6">
            <Icons.Question className="w-10 h-10" />
          </div>
          <h3 className="text-2xl font-display font-bold text-ink mb-3">
            No Questions Yet
          </h3>
          <p className="text-ink-light max-w-md mx-auto">
            Start generating questions and they will be automatically saved here, organized by units
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredUnits.map((unitNumber) => {
            const unitData = questionsByUnit[unitNumber];
            if (!unitData) return null;

            const filteredQuestions = getFilteredQuestions(unitData.questions);
            if (filteredQuestions.length === 0) return null;

            return (
              <div
                key={unitNumber}
                className="bg-white rounded-3xl border border-warm-200 shadow-lg overflow-hidden"
              >
                {/* Unit Header */}
                <button
                  onClick={() => toggleUnit(unitNumber)}
                  className="w-full p-6 flex items-center justify-between hover:bg-warm-50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-accent text-white rounded-2xl flex items-center justify-center font-bold text-xl">
                      {unitNumber}
                    </div>
                    <div className="text-left">
                      <h4 className="text-2xl font-display font-bold text-ink">
                        Unit {unitNumber}
                      </h4>
                      {unitData.unit_name && (
                        <p className="text-sm text-ink mt-1 font-semibold">{unitData.unit_name}</p>
                      )}
                      <p className="text-sm text-ink-light mt-1">
                        {filteredQuestions.length} Question{filteredQuestions.length !== 1 ? 's' : ''}
                        {selectedType !== 'all' && ` (${
                          selectedType === 'mcq' ? 'MCQ' : 
                          selectedType === 'short_ans' ? 'Short Answer' :
                          selectedType === 'long_ans' ? 'Long Answer' :
                          selectedType === 'numerical' ? 'Numerical' :
                          selectedType.replace(/_/g, ' ')
                        })`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        clearUnit(unitNumber);
                      }}
                      className="px-3 py-2 bg-red-50 text-red-600 rounded-xl font-semibold hover:bg-red-100 transition text-sm"
                    >
                      Clear Unit
                    </button>
                    <Icons.ChevronRight
                      className={`w-6 h-6 text-ink-light transition-transform duration-300 ${
                        expandedUnits.has(unitNumber) ? 'rotate-90' : ''
                      }`}
                    />
                  </div>
                </button>

                {/* Unit Questions */}
                {expandedUnits.has(unitNumber) && (
                  <div className="px-6 pb-6 space-y-4 animate-fade-in">
                    {filteredQuestions.map((question, idx) => (
                      <div
                        key={question.id}
                        className="p-5 bg-warm-50 rounded-2xl border border-warm-100"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1 space-y-3">
                            <div className="flex items-start gap-3">
                              <span className="px-3 py-1 bg-accent text-white rounded-lg font-bold text-sm flex-shrink-0">
                                Q{idx + 1}
                              </span>
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-2">
                                  <span className="px-3 py-1 bg-accent/10 text-accent rounded-lg font-bold text-sm border-2 border-accent">
                                    Unit {question.unit_number || unitNumber}
                                  </span>
                                  {question.type && (
                                    <span className="px-3 py-1 bg-green-100 text-green-700 rounded-lg font-bold text-sm border border-green-300 capitalize">
                                      {question.type === 'mcq' ? 'MCQ' : 
                                       question.type === 'short_ans' ? 'Short Answer' :
                                       question.type === 'long_ans' ? 'Long Answer' :
                                       question.type === 'numerical' ? 'Numerical' :
                                       question.type.replace(/_/g, ' ')}
                                    </span>
                                  )}
                                </div>
                                <p className="text-ink font-medium leading-relaxed">
                                  {question.question_text}
                                </p>
                              </div>
                            </div>

                            <div className="flex flex-wrap items-center gap-2 ml-12">
                              <span className="px-2 py-1 bg-blue-100 text-blue-600 rounded text-xs font-semibold">
                                {question.marks} Mark{question.marks !== 1 ? 's' : ''}
                              </span>
                              <span className="px-2 py-1 bg-purple-100 text-purple-600 rounded text-xs font-semibold">
                                {question.co}
                              </span>
                              <span className="px-2 py-1 bg-orange-100 text-orange-600 rounded text-xs font-semibold capitalize">
                                {question.difficulty}
                              </span>
                              <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs font-semibold">
                                {question.bloom_level}
                              </span>
                              {question.topic && (
                                <span className="px-2 py-1 bg-warm-100 text-ink rounded text-xs font-semibold">
                                  {question.topic}
                                </span>
                              )}
                              <span className="text-xs text-ink-light ml-2">
                                {new Date(question.generated_at).toLocaleDateString()}
                              </span>
                            </div>

                            {(question.answer || question.computed_answer) && (
                              <div className="ml-12 mt-3 p-3 bg-green-50 border border-green-100 rounded-xl text-sm text-green-800">
                                <span className="font-semibold text-green-700">Answer:</span> {question.answer || question.computed_answer}
                              </div>
                            )}
                            {question.explanation && (
                              <div className="ml-12 mt-2 p-3 bg-blue-50 border border-blue-100 rounded-xl text-sm text-blue-800">
                                <span className="font-semibold text-blue-700">Explanation:</span> {question.explanation}
                              </div>
                            )}
                            {(question.source_filename || (question.source_pages && question.source_pages.length > 0)) && (
                              <div className="ml-12 mt-2 flex items-center flex-wrap gap-2 text-xs text-ink-light">
                                <span className="font-semibold text-ink">Sources:</span>
                                {question.source_filename && (
                                  <span className="px-2 py-1 bg-white border border-warm-200 rounded-lg text-ink text-xs">
                                    {question.source_filename}
                                  </span>
                                )}
                                {question.source_pages && question.source_pages.length > 0 && (
                                  <span className="px-2 py-1 bg-warm-100 text-ink rounded-lg text-xs">
                                    Pages: {question.source_pages.join(', ')}
                                  </span>
                                )}
                                {question.question_id && (
                                  <span className="px-2 py-1 bg-accent-soft text-accent rounded-lg text-xs font-semibold">
                                    ID: {question.question_id}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>

                          <button
                            onClick={() => deleteQuestion(unitNumber, question.id)}
                            className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition"
                            title="Delete question"
                          >
                            <Icons.Trash className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default QuestionBankModule;