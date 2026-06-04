import React from 'react';
import { Icons } from './ui/SystemIcons';

interface PDFContextViewerProps {
  topic: string;
  context: string;
  chunks: number;
  onClose: () => void;
}

const PDFContextViewer: React.FC<PDFContextViewerProps> = ({ topic, context, chunks, onClose }) => {
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-warm-100">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-accent-soft rounded-lg">
              <Icons.Book className="w-5 h-5 text-accent" />
            </div>
            <div>
              <h2 className="font-display text-xl font-medium text-ink">PDF Context</h2>
              <p className="text-sm text-ink-light">Topic: {topic}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-warm-50 rounded-lg transition-colors"
          >
            <Icons.X className="w-5 h-5 text-ink-light" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <div className="flex items-center gap-2 text-sm text-ink-light">
            <Icons.FileText className="w-4 h-4" />
            <span>Retrieved {chunks} chunks from uploaded PDF</span>
          </div>

          <div className="bg-warm-50 rounded-xl p-6 border border-warm-100">
            <pre className="text-sm text-ink leading-relaxed whitespace-pre-wrap font-sans">
              {context}
            </pre>
          </div>

          <div className="text-xs text-ink-faint italic">
            This is the exact context that the LLM will use to generate the question.
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-warm-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default PDFContextViewer;
