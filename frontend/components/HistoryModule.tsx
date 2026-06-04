import React from 'react';
import { GenerationResponse } from '../types';
import { Icons } from './ui/SystemIcons';

export interface HistoryItem {
  id: string;
  timestamp: number;
  data: GenerationResponse;
}

interface HistoryModuleProps {
  history: HistoryItem[];
  onRestore: (item: GenerationResponse) => void;
}

const HistoryModule: React.FC<HistoryModuleProps> = ({ history, onRestore }) => {
  if (history.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-ink-light opacity-60 animate-fade-in">
        <div className="p-6 bg-warm-100 rounded-full mb-6">
           <Icons.History className="w-12 h-12 text-warm-300" />
        </div>
        <h3 className="text-xl font-display font-medium text-ink">No history recorded</h3>
        <p className="text-ink-light mt-2">Generate your first evaluation to see it here.</p>
      </div>
    );
  }

  // Sort by timestamp descending (newest first)
  const sortedHistory = [...history].sort((a, b) => b.timestamp - a.timestamp);

  return (
    <div className="max-w-4xl mx-auto w-full animate-slide-up pb-12">
      <div className="text-center space-y-4 mb-12">
        <h2 className="font-display text-4xl font-semibold text-ink">Session History</h2>
        <p className="text-ink-light text-lg">Review and revisit previously generated assessments.</p>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {sortedHistory.map((item) => (
          <div 
            key={item.id} 
            onClick={() => onRestore(item.data)}
            className="group bg-white rounded-2xl p-6 border border-warm-100 shadow-sm hover:shadow-lg hover:border-accent/30 transition-all duration-300 flex items-start justify-between gap-6 cursor-pointer relative overflow-hidden" 
          >
            {/* Hover Indicator */}
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-transparent group-hover:bg-accent transition-colors duration-300"></div>

            <div className="space-y-3 flex-1">
              <div className="flex items-center gap-3">
                 <span className={`text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-md ${
                   item.data.data.difficulty_rating === 'PhD' ? 'bg-purple-100 text-purple-700' :
                   item.data.data.difficulty_rating === 'Expert' ? 'bg-red-100 text-red-700' :
                   'bg-warm-100 text-ink-light'
                 }`}>
                   {item.data.data.difficulty_rating}
                 </span>
                 <div className="flex items-center gap-1.5 text-xs text-ink-faint font-mono">
                   <Icons.Clock className="w-3 h-3" />
                   {new Date(item.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                 </div>
              </div>
              <h3 className="font-display text-xl font-medium text-ink leading-snug group-hover:text-accent transition-colors">
                {item.data.data.question}
              </h3>
              <p className="text-sm text-ink-light line-clamp-1">
                {item.data.data.computed_answer || item.data.data.answer}
              </p>
            </div>

            <div className="self-center flex-shrink-0">
               <div className="w-10 h-10 rounded-full bg-warm-50 text-warm-300 flex items-center justify-center group-hover:bg-accent group-hover:text-white transition-all duration-300 group-hover:scale-110">
                 <Icons.ArrowRight className="w-5 h-5" />
               </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default HistoryModule;