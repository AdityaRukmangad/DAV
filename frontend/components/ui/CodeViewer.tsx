import React from 'react';

interface CodeViewerProps {
  code: string;
  language?: string;
}

const CodeViewer: React.FC<CodeViewerProps> = ({ code }) => {
  return (
    <div className="w-full rounded-lg bg-ink text-warm-50 overflow-hidden shadow-inner font-mono text-sm my-2">
      <div className="p-4 overflow-x-auto custom-scrollbar">
        <pre className="leading-relaxed">
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
};

export default CodeViewer;