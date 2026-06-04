import React, { useState, useRef } from 'react';
import { uploadPDF } from '../services/api';
import { UploadResponse } from '../types';
import { Icons } from './ui/SystemIcons';

interface IngestModuleProps {
  onIngest: (topic: string) => void;
}

const IngestModule: React.FC<IngestModuleProps> = ({ onIngest }) => {
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    
    const file = files[0];
    if (file.type !== 'application/pdf') {
      setError('Please upload a valid PDF document.');
      return;
    }

    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const response = await uploadPDF(file);
      setResult(response);
      // Notify parent component to update suggestions
      onIngest(response.filename);
    } catch (err: any) {
      setError(err.message || 'Ingestion failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="max-w-4xl mx-auto w-full flex flex-col items-center animate-slide-up py-10">
      
      {!result ? (
        <div className="w-full flex flex-col items-center space-y-12">
          <div className="text-center space-y-4">
            <h2 className="font-display text-5xl font-semibold text-ink tracking-tight">Knowledge Ingestion</h2>
            <p className="text-ink-light text-lg max-w-xl mx-auto">Upload technical documentation, manuals, or textbooks to expand the system's reasoning capabilities and domain expertise.</p>
          </div>

          <div 
            className={`
              w-full max-w-2xl aspect-[2.5/1] flex flex-col items-center justify-center rounded-3xl border-2 border-dashed transition-all duration-300 group
              ${dragActive ? 'border-accent bg-accent-soft scale-[1.02]' : 'border-warm-200 bg-white/60 hover:border-accent/50 hover:bg-white hover:shadow-xl hover:shadow-warm-200/40'}
              ${uploading ? 'opacity-50 cursor-wait' : 'cursor-pointer'}
            `}
            onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
            onDragOver={(e) => { e.preventDefault(); }}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input 
              ref={fileInputRef}
              type="file" 
              accept=".pdf" 
              className="hidden" 
              onChange={(e) => handleFiles(e.target.files)}
            />
            
            {uploading ? (
              <div className="flex flex-col items-center gap-6">
                 <div className="relative w-16 h-16">
                   <div className="absolute inset-0 border-4 border-warm-200 rounded-full"></div>
                   <div className="absolute inset-0 border-4 border-accent rounded-full border-t-transparent animate-spin"></div>
                 </div>
                 <div className="text-center">
                   <p className="font-medium text-ink text-lg">Analyzing document structure...</p>
                   <p className="text-sm text-ink-light mt-1">Vectorizing content</p>
                 </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-6 transition-transform duration-300 group-hover:-translate-y-2">
                <div className="w-20 h-20 bg-accent-soft text-accent rounded-3xl flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow">
                  <Icons.Upload className="w-10 h-10" />
                </div>
                <div className="text-center space-y-2">
                  <p className="font-bold text-2xl text-ink">Click to upload PDF</p>
                  <p className="text-base text-ink-light">or drag and drop file here</p>
                </div>
              </div>
            )}
          </div>
          
          {error && (
            <div className="p-4 bg-red-50 text-red-600 rounded-xl text-sm flex items-center gap-3 border border-red-100 shadow-sm animate-fade-in">
              <Icons.Error className="w-5 h-5" />
              {error}
            </div>
          )}

          {/* Filler content for emptiness */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl mt-8 opacity-60">
             {[1,2,3].map((i) => (
               <div key={i} className="h-24 bg-white/40 rounded-xl border border-warm-100"></div>
             ))}
          </div>
        </div>
      ) : (
        <div className="w-full max-w-3xl bg-white rounded-[2rem] p-10 border border-warm-100 shadow-2xl shadow-warm-200/50 animate-fade-in flex flex-col md:flex-row gap-10 items-center md:items-start">
          
          {/* Visual Document Preview */}
          <div className="relative w-40 aspect-[1/1.4] bg-white border border-warm-200 rounded-xl shadow-lg p-4 flex flex-col gap-2 transform rotate-3 hover:rotate-0 transition-transform duration-500 ease-out">
            {/* Header Lines */}
            <div className="w-full h-24 bg-warm-50 rounded border border-warm-100 mb-1 p-1.5 space-y-1.5 overflow-hidden">
               <div className="w-1/3 h-2 bg-warm-200 rounded-sm mb-3"></div>
               <div className="w-full h-1.5 bg-warm-100 rounded-sm"></div>
               <div className="w-full h-1.5 bg-warm-100 rounded-sm"></div>
               <div className="w-full h-1.5 bg-warm-100 rounded-sm"></div>
               <div className="w-2/3 h-1.5 bg-warm-100 rounded-sm"></div>
               <div className="w-full h-1.5 bg-warm-100 rounded-sm"></div>
            </div>
            {/* Body Lines */}
            <div className="flex-1 space-y-1.5">
               <div className="w-full h-1.5 bg-warm-50 rounded-sm"></div>
               <div className="w-full h-1.5 bg-warm-50 rounded-sm"></div>
               <div className="w-5/6 h-1.5 bg-warm-50 rounded-sm"></div>
               <div className="w-full h-1.5 bg-warm-50 rounded-sm"></div>
               <div className="w-4/5 h-1.5 bg-warm-50 rounded-sm"></div>
            </div>
            {/* Corner fold simulation */}
            <div className="absolute top-0 right-0 w-8 h-8 bg-warm-100 rounded-bl-xl shadow-sm"></div>
            
            <div className="absolute -bottom-4 -right-4 bg-accent text-white p-2 rounded-full shadow-lg border-4 border-white">
              <Icons.Check className="w-6 h-6" />
            </div>
          </div>

          <div className="flex-1 text-center md:text-left space-y-6">
             <div>
                <div className="inline-block px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-bold uppercase tracking-wide mb-3">System Ready</div>
                <h3 className="text-3xl font-display font-semibold text-ink mb-2">Ingestion Complete</h3>
                <p className="text-ink-light text-lg">{result.filename}</p>
             </div>

             <div className="grid grid-cols-2 gap-4">
               <div className="bg-warm-50 p-4 rounded-2xl border border-warm-100">
                 <p className="text-xs text-ink-light uppercase tracking-wide font-semibold mb-1">Total Pages</p>
                 <p className="text-2xl font-bold text-accent">{result.ingestion.total_pages}</p>
               </div>
               <div className="bg-warm-50 p-4 rounded-2xl border border-warm-100">
                 <p className="text-xs text-ink-light uppercase tracking-wide font-semibold mb-1">Vectors</p>
                 <p className="text-2xl font-bold text-accent">{result.ingestion.chunk_count}</p>
               </div>
             </div>

             <div className="pt-2">
               <button 
                  onClick={() => setResult(null)}
                  className="px-6 py-3 bg-white border border-warm-200 rounded-xl text-ink font-medium hover:bg-warm-50 hover:border-accent hover:text-accent transition-colors shadow-sm"
               >
                 Process Another Document
               </button>
             </div>
          </div>

        </div>
      )}
    </div>
  );
};

export default IngestModule;