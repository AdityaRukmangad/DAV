import React, { useState, useEffect, useRef } from 'react';
import { generateQuestion } from '../services/api';
import { GenerationResponse } from '../types';
import { Icons } from './ui/SystemIcons';
import CodeViewer from './ui/CodeViewer';

const DIFFICULTIES = ['Easy', 'Medium', 'Hard', 'Expert', 'PhD'];

interface GenerationModuleProps {
  suggestions: string[];
  onGenerationComplete?: (data: GenerationResponse) => void;
  restoreData?: GenerationResponse | null;
}

const GenerationModule: React.FC<GenerationModuleProps> = ({ 
  suggestions, 
  onGenerationComplete,
  restoreData 
}) => {
  const [topic, setTopic] = useState('');
  const [difficulty, setDifficulty] = useState('Medium');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<GenerationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Auto-resize textarea
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [topic]);

  // Handle data restoration from history
  useEffect(() => {
    if (restoreData) {
      setData(restoreData);
      // Optional: Extract topic from question if possible, or just leave topic as is
      // For now we assume the user might want to generate something new so we don't necessarily overwrite the input
    }
  }, [restoreData]);

  const handleGenerate = async (selectedTopic?: string) => {
    const topicToUse = selectedTopic || topic;
    if (!topicToUse.trim()) return;
    
    if (selectedTopic) setTopic(selectedTopic);
    
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const res = await generateQuestion(topicToUse, difficulty);
      setData(res);
      if (onGenerationComplete) {
        onGenerationComplete(res);
      }
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

  return (
    <div className="flex flex-col space-y-16 animate-slide-up pb-20">
      
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
              placeholder="Topic e.g. 'Bayesian Inference in specialized domains'..."
              rows={1}
              className="w-full bg-transparent border-none focus:ring-0 text-ink placeholder-ink-faint text-2xl font-medium resize-none p-5 max-h-48 leading-relaxed"
            />
            
            <div className="flex items-center justify-between px-3 pb-3 pt-4">
              <div className="flex items-center gap-2 overflow-x-auto pb-1 hide-scrollbar">
                {DIFFICULTIES.map((d) => (
                  <button
                    key={d}
                    onClick={() => setDifficulty(d)}
                    className={`
                      px-4 py-2 rounded-xl text-xs font-bold tracking-wide transition-all border
                      ${difficulty === d 
                        ? 'bg-ink text-white border-ink shadow-lg shadow-ink/20 scale-105' 
                        : 'bg-warm-50 text-ink-light border-transparent hover:bg-warm-100 hover:text-ink'}
                    `}
                  >
                    {d}
                  </button>
                ))}
              </div>

              <button
                onClick={() => handleGenerate()}
                disabled={loading || !topic}
                className={`
                  ml-4 p-4 rounded-xl transition-all duration-300 flex-shrink-0
                  ${loading || !topic
                    ? 'bg-warm-100 text-warm-300'
                    : 'bg-accent text-white hover:bg-accent-hover shadow-lg shadow-accent/20 hover:scale-110 active:scale-95'}
                `}
              >
                {loading ? <Icons.Activity className="w-6 h-6 animate-spin" /> : <Icons.Zap className="w-6 h-6 fill-current" />}
              </button>
            </div>
          </div>
        </div>

        {/* SUGGESTIONS SECTION (Fills the page) */}
        {!data && !loading && (
          <div className="pt-8 space-y-6 animate-fade-in delay-100">
            <div className="flex items-center gap-3 text-ink-light">
              <div className="h-px bg-warm-200 flex-1"></div>
              <span className="text-xs font-bold uppercase tracking-widest">Available Contexts</span>
              <div className="h-px bg-warm-200 flex-1"></div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {suggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  onClick={() => handleGenerate(suggestion)}
                  className="group flex items-start gap-4 p-5 bg-white rounded-2xl border border-warm-100 hover:border-accent/30 hover:shadow-lg hover:shadow-warm-200/50 transition-all duration-300 text-left"
                >
                  <div className="mt-1 p-2 bg-warm-50 rounded-lg text-accent group-hover:bg-accent group-hover:text-white transition-colors duration-300">
                    <Icons.Book className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-display font-medium text-ink group-hover:text-accent transition-colors text-lg">{suggestion}</h3>
                    <p className="text-sm text-ink-light mt-1">Generate evaluation based on ingested material.</p>
                  </div>
                </button>
              ))}
              
              {/* Add a "More" placeholder if list is short to fill space */}
              {suggestions.length < 4 && (
                 <div className="flex flex-col items-center justify-center p-5 rounded-2xl border border-dashed border-warm-200 text-ink-faint">
                    <p className="text-sm">Upload more documents to expand context</p>
                 </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* OUTPUT SECTION */}
      {error && (
        <div className="max-w-2xl mx-auto w-full p-4 bg-red-50 text-red-700 rounded-xl text-sm flex items-start gap-3 border border-red-100 shadow-sm">
          <Icons.AlertTriangle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {data && (
        <div className="w-full max-w-4xl mx-auto animate-fade-in pb-12">
          <div className="bg-surface rounded-3xl border border-warm-100 shadow-2xl shadow-warm-200/40 p-10 md:p-14 space-y-12 relative overflow-hidden">
            
            {/* Decorative top bar */}
            <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-accent via-orange-400 to-warm-300"></div>

            {/* Header */}
            <div className="flex justify-between items-center border-b border-warm-100 pb-6">
              <div className="flex items-center gap-3">
                <span className="bg-ink text-white px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider shadow-md shadow-ink/20">{data.data.difficulty_rating} Protocol</span>
                {data.data.source && (
                  <span className="text-xs font-medium text-ink-light bg-warm-50 px-2 py-1 rounded-md border border-warm-100 truncate max-w-[150px]">{data.data.source}</span>
                )}
              </div>
              <span className="text-xs font-mono text-ink-faint flex items-center gap-1">
                <Icons.Activity className="w-3 h-3" />
                {data.meta.duration_seconds}s
              </span>
            </div>

            {/* Question */}
            <div className="relative">
              <Icons.FileText className="absolute -left-8 top-1 w-6 h-6 text-warm-200 hidden md:block" />
              <h2 className="font-display text-3xl md:text-4xl font-medium text-ink leading-tight">
                {data.data.question}
              </h2>
            </div>

            {/* Verification Code */}
            {data.data.verification_code && (
              <div className="space-y-3 bg-warm-50 p-2 rounded-2xl border border-warm-100">
                <div className="flex items-center gap-2 px-4 pt-3 text-ink-light">
                  <Icons.Terminal className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase tracking-wide">Verification Logic</span>
                </div>
                <CodeViewer code={data.data.verification_code} />
              </div>
            )}

            {/* Answer & Logic */}
            <div className="grid grid-cols-1 gap-10">
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-accent">
                  <div className="p-1 bg-accent-soft rounded-md">
                    <Icons.Check className="w-5 h-5" />
                  </div>
                  <span className="text-sm font-bold uppercase tracking-wide">Computed Answer</span>
                </div>
                <div className="text-xl text-ink font-medium pl-4 md:pl-0 leading-relaxed">
                  {data.data.computed_answer || data.data.answer}
                </div>
              </div>

              <div className="bg-warm-50/80 rounded-2xl p-8 border border-warm-100 relative group hover:bg-warm-50 transition-colors">
                 <div className="absolute top-6 left-6 w-1 h-8 bg-warm-200 rounded-full group-hover:bg-accent transition-colors"></div>
                 <div className="pl-6">
                    <div className="flex items-center gap-2 text-ink-light mb-3">
                      <span className="text-xs font-bold uppercase tracking-wide">Detailed Explanation</span>
                    </div>
                     <p className="text-ink leading-relaxed font-sans text-lg">
                       {data.data.explanation}
                     </p>
                 </div>
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  );
};

export default GenerationModule;