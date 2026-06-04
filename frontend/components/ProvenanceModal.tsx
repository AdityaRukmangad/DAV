import React from 'react';
import { ProvenanceData } from '../types';
import { Icons } from './ui/SystemIcons';

interface ProvenanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: ProvenanceData | null;
  loading: boolean;
  error: string | null;
}

const ProvenanceModal: React.FC<ProvenanceModalProps> = ({ isOpen, onClose, data, loading, error }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-accent to-orange-400 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Icons.Book className="w-6 h-6 text-white" />
            <h2 className="text-xl font-display font-bold text-white">Question Provenance</h2>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:bg-white/20 rounded-full p-2 transition-colors"
          >
            <Icons.X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Icons.Activity className="w-8 h-8 text-accent animate-spin" />
              <span className="ml-3 text-ink-light">Loading provenance data...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
              <Icons.AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0" />
              <div className="text-sm text-red-800">{error}</div>
            </div>
          )}

          {data && !loading && !error && (
            <>
              {/* Question Info */}
              <div className="bg-warm-50 rounded-xl p-5 border border-warm-200">
                <div className="flex items-center gap-2 mb-3">
                  <Icons.FileText className="w-4 h-4 text-accent" />
                  <h3 className="font-display font-semibold text-ink">Question Details</h3>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex gap-2">
                    <span className="text-ink-light font-medium w-24">Topic:</span>
                    <span className="text-ink">{data.topic}</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-ink-light font-medium w-24">Difficulty:</span>
                    <span className="text-ink">{data.difficulty}</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-ink-light font-medium w-24">Question ID:</span>
                    <span className="text-ink font-mono">#{data.question_id}</span>
                  </div>
                </div>
              </div>

              {/* Pedagogy Tags */}
              <div className="bg-blue-50 rounded-xl p-5 border border-blue-200">
                <div className="flex items-center gap-2 mb-3">
                  <Icons.Tag className="w-4 h-4 text-blue-600" />
                  <h3 className="font-display font-semibold text-ink">Educational Metadata</h3>
                </div>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-ink-light font-medium block mb-1">Bloom Level</span>
                    <span className="inline-block bg-blue-100 text-blue-800 px-3 py-1 rounded-full font-bold">
                      {data.bloom_level || 'N/A'}
                    </span>
                  </div>
                  <div>
                    <span className="text-ink-light font-medium block mb-1">Course Outcome</span>
                    <span className="inline-block bg-purple-100 text-purple-800 px-3 py-1 rounded-full font-bold">
                      {data.course_outcome || 'N/A'}
                    </span>
                  </div>
                  <div>
                    <span className="text-ink-light font-medium block mb-1">Program Outcome</span>
                    <span className="inline-block bg-green-100 text-green-800 px-3 py-1 rounded-full font-bold">
                      {data.program_outcome || 'N/A'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Source Documents */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icons.Database className="w-4 h-4 text-accent" />
                    <h3 className="font-display font-semibold text-ink">Source Documents</h3>
                  </div>
                  <span className="text-xs text-ink-light font-medium">
                    {data.total_chunks_used} chunks used
                  </span>
                </div>

                {data.source_documents.length === 0 ? (
                  <div className="text-center py-8 text-ink-light text-sm">
                    No source documents available
                  </div>
                ) : (
                  <div className="space-y-4">
                    {data.source_documents.map((doc, docIdx) => (
                      <div key={docIdx} className="border border-warm-200 rounded-xl overflow-hidden">
                        <div className="bg-warm-100 px-4 py-3 flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Icons.FileText className="w-4 h-4 text-red-500" />
                            <span className="font-medium text-sm text-ink">{doc.doc_id}</span>
                          </div>
                          <span className="text-xs text-ink-light">
                            {doc.chunk_count} {doc.chunk_count === 1 ? 'chunk' : 'chunks'}
                          </span>
                        </div>
                        <div className="p-4 space-y-3">
                          {doc.chunks.map((chunk, chunkIdx) => (
                            <div key={chunkIdx} className="bg-warm-50 rounded-lg p-4 border border-warm-100">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-mono text-ink-light">
                                  Chunk ID: {chunk.chunk_id.substring(0, 12)}...
                                </span>
                                <span className="text-xs bg-warm-200 text-ink px-2 py-0.5 rounded">
                                  Page {chunk.page}
                                </span>
                              </div>
                              <p className="text-sm text-ink leading-relaxed font-mono">
                                {chunk.content_preview}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-warm-200 px-6 py-4 bg-warm-50">
          <div className="flex items-center justify-between">
            <p className="text-xs text-ink-light">
              This is read-only provenance data. No regeneration is available.
            </p>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors text-sm font-medium"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProvenanceModal;
