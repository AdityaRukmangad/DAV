import React, { useState } from 'react';
import IngestModule from './components/IngestModule';
import GenerationModule from './components/GenerationModule';
import PaperGeneratorModule from './components/PaperGeneratorModule';
import KnowledgeHubModule from './components/KnowledgeHubModule';
import QuestionBankModule from './components/QuestionBankModule';
import { GenerationResponse } from './types';

type Tab = 'generate' | 'papers' | 'ingest' | 'knowledge' | 'question-bank';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('generate');

  const handleIngestSuccess = (_topic: string) => {
    // After ingestion, optionally navigate back to generate tab
    // Documents list will auto-refresh when GenerationModule mounts
  };

  const handleGenerationComplete = (data: GenerationResponse) => {
    // Questions are now saved in QuestionBankModule automatically
  };

  return (
    <div className="min-h-screen flex flex-col font-sans selection:bg-accent-soft selection:text-accent-hover">
      
      {/* HEADER */}
      <header className="fixed top-0 inset-x-0 z-50 px-6 py-6 pointer-events-none">
        <div className="max-w-6xl mx-auto flex items-center justify-between pointer-events-auto">
          <div className="group relative flex items-center space-x-2 bg-white/50 backdrop-blur-md px-5 py-2.5 rounded-full border border-white/60 shadow-sm hover:shadow-xl hover:shadow-accent/20 hover:border-accent/40 hover:bg-white/80 transition-all duration-500 cursor-pointer overflow-hidden">
            {/* Animated background gradient on hover */}
            <div className="absolute inset-0 bg-gradient-to-r from-accent/0 via-accent/5 to-accent/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 animate-pulse"></div>

            <span className="relative font-display font-bold text-lg tracking-tight text-accent group-hover:scale-110 group-hover:text-accent-hover inline-block transition-all duration-500 group-hover:rotate-[-2deg] drop-shadow-sm group-hover:drop-shadow-lg">
              Tribunal
            </span>
            <span className="relative text-xl group-hover:text-accent transition-all duration-500 opacity-0 group-hover:opacity-100 transform translate-x-[-10px] group-hover:translate-x-0 group-hover:rotate-12 group-hover:scale-110">⚖️</span>
          </div>

          <nav className="flex space-x-1 bg-white/50 backdrop-blur-md p-1.5 rounded-full border border-white/60 shadow-sm">
            <TabButton
              active={activeTab === 'generate'}
              onClick={() => setActiveTab('generate')}
              label="Generator"
            />
            <TabButton
              active={activeTab === 'papers'}
              onClick={() => setActiveTab('papers')}
              label="Papers"
            />
            <TabButton
              active={activeTab === 'question-bank'}
              onClick={() => setActiveTab('question-bank')}
              label="Question Bank"
            />
            <TabButton
              active={activeTab === 'knowledge'}
              onClick={() => setActiveTab('knowledge')}
              label="Knowledge Hub"
            />
            <TabButton
              active={activeTab === 'ingest'}
              onClick={() => setActiveTab('ingest')}
              label="Upload"
            />
          </nav>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="flex-1 w-full max-w-5xl mx-auto px-6 pt-32 pb-12 flex flex-col justify-start">
        {activeTab === 'generate' && (
          <GenerationModule
            onGenerationComplete={handleGenerationComplete}
            onNavigateToIngest={() => setActiveTab('ingest')}
          />
        )}
        {/* Keep PaperGeneratorModule mounted to preserve state */}
        <div style={{ display: activeTab === 'papers' ? 'block' : 'none' }}>
          <PaperGeneratorModule
            onNavigateToIngest={() => setActiveTab('ingest')}
          />
        </div>
        {activeTab === 'ingest' && (
          <IngestModule onIngest={handleIngestSuccess} />
        )}
        {activeTab === 'knowledge' && (
          <KnowledgeHubModule />
        )}
        {activeTab === 'question-bank' && (
          <QuestionBankModule />
        )}
      </main>

      {/* FOOTER */}
      <footer className="py-8 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/30 border border-white/40 text-xs font-medium text-ink-light uppercase tracking-widest">
           <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
           System Operational
        </div>
      </footer>
      
    </div>
  );
};

const TabButton: React.FC<{ 
  active: boolean; 
  onClick: () => void; 
  label: string;
}> = ({ active, onClick, label }) => (
  <button
    onClick={onClick}
    className={`
      px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-300
      ${active 
        ? 'bg-accent text-white shadow-lg shadow-accent/25 scale-105' 
        : 'text-ink-light hover:text-accent hover:bg-accent-soft/50'}
    `}
  >
    {label}
  </button>
);

export default App;