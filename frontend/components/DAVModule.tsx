import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import { onDataChanged, notifyDataChanged } from '../services/events';

// Auto-refresh cadence while an Analytics tab is open, so a paper generating
// in the background (Papers tab stays mounted behind the scenes) is picked
// up without the user needing to manually hit refresh.
const AUTO_REFRESH_MS = 12000;

// =============================================================================
// TYPES
// =============================================================================

interface Overview {
  total_questions: number;
  unique_topics: number;
  difficulty_distribution: Record<string, number>;
  mean_difficulty_score: number;
  difficulty_variance: number;
  difficulty_std_dev: number;
  avg_bloom_level: number;
  source_distribution: Record<string, number>;
  questions_last_7_days: number;
  bloom_balance_score: number;
}

interface BloomData {
  overall: { bloom_level: number; label: string; count: number }[];
  heatmap: { difficulty: string; bloom_level: number; bloom_label: string; count: number }[];
}

interface CoverageData {
  overall_coverage_pct: number;
  total_syllabus_topics: number;
  covered_count: number;
  gap_count: number;
  units: {
    unit: number;
    unit_name: string;
    total_topics: number;
    covered_topics: number;
    coverage_pct: number;
    topics: { topic: string; question_count: number; covered: boolean }[];
  }[];
  gap_topics: { unit: string; topic: string }[];
}

interface TrendData {
  daily: { date: string; Easy: number; Medium: number; Hard: number; total: number; cumulative: number; avg_difficulty_score: number }[];
  weekly: { week: string; Easy: number; Medium: number; Hard: number; total: number }[];
}

interface MatrixEntry {
  co: string; po: string;
  co_label: string; po_label: string;
  count: number; attainment_pct: number; nba_level: number;
}

interface CoPoData {
  matrix: MatrixEntry[];
  co_summary: { co: string; label: string; count: number; pct: number }[];
  po_summary: { po: string; label: string; count: number; pct: number }[];
  untagged_count?: number;
}

interface EDAReport {
  total_questions: number;
  difficulty: { distribution: Record<string, number>; mean_score: number; variance: number; std_dev: number };
  bloom: { distribution: Record<string, number>; mean_level: number; balance_score: number };
  topics: { unique_count: number; top_10: { topic: string; count: number }[] };
  outcomes: { co_distribution: Record<string, number>; po_distribution: Record<string, number> };
  data_quality: { missing_bloom_pct: number; missing_co_pct: number; missing_po_pct: number; questions_with_code_pct: number };
  accuracy_proxy: { questions_with_answer: number; questions_with_explanation: number };
}

interface BloomLevel {
  bloom_level: number; label: string;
  actual_pct: number; ideal_pct: number; deviation: number;
  status: string; actual_count: number;
}
interface PaperBalance {
  balance_score: number;
  total_questions: number;
  bloom_classified_questions?: number;
  unclassified_questions?: number;
  bloom_levels: BloomLevel[];
  difficulty_distribution: Record<string, number>;
  ideal_difficulty: Record<string, number>;
  suggestions: string[];
  rating: string;
}

interface SimilarPair {
  question_a_id: number; question_b_id: number;
  question_a_preview: string; question_b_preview: string;
  topic_a: string; topic_b: string;
  similarity_score: number; label: string;
}
interface SimilarityReport {
  total_questions: number;
  flagged_count: number;
  threshold_used: number;
  label_summary: Record<string, number>;
  pairs: SimilarPair[];
}

interface TopicPerf {
  topic: string; avg_score: number; accuracy_pct: number; response_count: number;
}
interface DifficultQ {
  question_id: number; topic: string; bloom_level: number; bloom_label: string;
  accuracy_pct: number; avg_score: number; avg_time_sec: number;
  response_count: number; flagged: boolean;
}
interface FeedbackAnalysis {
  total_responses: number;
  overall_accuracy_pct: number;
  avg_score: number;
  score_distribution: Record<string, number>;
  weak_topics: TopicPerf[];
  topic_performance: TopicPerf[];
  difficult_questions: DifficultQ[];
  flagged_question_count: number;
  message?: string;
}

interface ConsistencyIssue {
  question_id: number; topic: string; bloom_level: number; bloom_label: string;
  co: string; po: string; issue_type: string; message: string; text_preview: string;
}
interface CoPoConsistency {
  total_questions: number;
  consistent_count: number;
  issue_count: number;
  consistency_score: number;
  issue_breakdown: Record<string, number>;
  co_mismatch_count: number;
  po_mismatch_count: number;
  missing_tags_count: number;
  issues: ConsistencyIssue[];
  bloom_co_rules: Record<string, string[]>;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const API = 'http://localhost:8000/api/v1/dav';

const PALETTE = {
  bloom: ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe', '#ede9fe'],
  diff: { Easy: '#10b981', Medium: '#f59e0b', Hard: '#ef4444' },
  nba: ['#f3f4f6', '#fef3c7', '#bfdbfe', '#bbf7d0'],
  line: '#6366f1',
  accent: '#6366f1',
};

const DIFFICULTIES = ['Easy', 'Medium', 'Hard'];

// =============================================================================
// SMALL REUSABLE COMPONENTS
// =============================================================================

const Card: React.FC<{ title: string; subtitle?: string; children: React.ReactNode; className?: string }> = ({
  title, subtitle, children, className = ''
}) => (
  <div className={`bg-white/70 backdrop-blur-sm border border-white/60 rounded-2xl p-6 shadow-sm ${className}`}>
    <div className="mb-4">
      <h3 className="font-semibold text-ink text-base">{title}</h3>
      {subtitle && <p className="text-ink-light text-xs mt-0.5">{subtitle}</p>}
    </div>
    {children}
  </div>
);

const StatChip: React.FC<{ label: string; value: string | number; sub?: string; color?: string }> = ({
  label, value, sub, color = 'bg-accent-soft text-accent'
}) => (
  <div className={`flex flex-col items-center justify-center rounded-xl px-4 py-3 ${color} min-w-[100px]`}>
    <span className="text-2xl font-bold leading-none">{value}</span>
    <span className="text-xs font-medium mt-1 opacity-80">{label}</span>
    {sub && <span className="text-xs opacity-60">{sub}</span>}
  </div>
);

const SectionHeader: React.FC<{ icon: string; title: string; desc: string }> = ({ icon, title, desc }) => (
  <div className="flex items-center gap-3 mb-6">
    <span className="text-2xl">{icon}</span>
    <div>
      <h2 className="text-lg font-bold text-ink">{title}</h2>
      <p className="text-xs text-ink-light">{desc}</p>
    </div>
  </div>
);

const Spinner: React.FC = () => (
  <div className="flex items-center justify-center h-32">
    <div className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin" />
  </div>
);

const NbaCell: React.FC<{ level: number; pct: number }> = ({ level, pct }) => {
  const bg = PALETTE.nba[level] || PALETTE.nba[0];
  return (
    <div
      className="flex flex-col items-center justify-center w-full h-full rounded p-1 transition-all duration-200 hover:scale-110 cursor-default"
      style={{ backgroundColor: bg, minHeight: 44 }}
      title={`${pct}% attainment (Level ${level})`}
    >
      <span className="text-xs font-bold text-ink leading-none">{pct > 0 ? `${pct}%` : '–'}</span>
      {level > 0 && (
        <span className="text-[9px] text-ink-light mt-0.5">L{level}</span>
      )}
    </div>
  );
};

// =============================================================================
// SECTION COMPONENTS
// =============================================================================

const OverviewSection: React.FC<{ data: Overview; onClean: () => void; cleaning: boolean }> = ({ data, onClean, cleaning }) => {
  const diffData = DIFFICULTIES.map(d => ({ name: d, value: data.difficulty_distribution?.[d] || 0 }));
  const srcData = Object.entries(data.source_distribution || {}).map(([k, v]) => ({ name: k, value: v }));
  const srcColors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

  return (
    <div className="space-y-6">
      <SectionHeader icon="📊" title="Overview" desc="Summary statistics and data health" />

      {/* Stat chips */}
      <div className="flex flex-wrap gap-3">
        <StatChip label="Total Questions" value={data.total_questions} color="bg-indigo-50 text-indigo-700" />
        <StatChip label="Unique Topics" value={data.unique_topics} color="bg-purple-50 text-purple-700" />
        <StatChip label="Last 7 Days" value={data.questions_last_7_days} color="bg-emerald-50 text-emerald-700" />
        <StatChip label="Avg Bloom" value={data.avg_bloom_level} color="bg-amber-50 text-amber-700" />
        <StatChip label="Bloom Balance" value={`${data.bloom_balance_score}%`} sub="higher = better" color="bg-blue-50 text-blue-700" />
        <StatChip label="Mean Difficulty" value={data.mean_difficulty_score} color="bg-rose-50 text-rose-700" />
        <StatChip label="Std Dev" value={data.difficulty_std_dev} color="bg-slate-50 text-slate-700" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Difficulty pie */}
        <Card title="Difficulty Distribution" subtitle="Pie chart breakdown">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={diffData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {diffData.map((entry) => (
                  <Cell key={entry.name} fill={(PALETTE.diff as Record<string,string>)[entry.name] || '#ccc'} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        {/* Source pie */}
        <Card title="Source Distribution" subtitle="Where questions come from">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={srcData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {srcData.map((_, i) => (
                  <Cell key={i} fill={srcColors[i % srcColors.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Data cleaning */}
      <Card title="Data Cleaning" subtitle="Remove duplicates, fill missing values, standardize difficulty casing">
        <div className="flex items-center gap-4">
          <button
            onClick={onClean}
            disabled={cleaning}
            className="px-5 py-2 rounded-full text-sm font-medium bg-accent text-white shadow hover:bg-accent-hover transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {cleaning ? 'Cleaning…' : 'Run Data Cleaning'}
          </button>
          <p className="text-xs text-ink-light">
            Standardizes difficulty, fills missing Bloom/CO/PO, removes exact duplicates.
          </p>
        </div>
      </Card>
    </div>
  );
};


const BloomSection: React.FC<{ data: BloomData }> = ({ data }) => {
  const barData = data.overall || [];

  // Build heatmap grid: difficulty rows × bloom cols
  const heatGrid: Record<string, Record<number, number>> = { Easy: {}, Medium: {}, Hard: {} };
  (data.heatmap || []).forEach(h => {
    if (!heatGrid[h.difficulty]) heatGrid[h.difficulty] = {};
    heatGrid[h.difficulty][h.bloom_level] = h.count;
  });

  const maxVal = Math.max(...(data.heatmap || []).map(h => h.count), 1);

  return (
    <div className="space-y-6">
      <SectionHeader icon="🧠" title="Bloom's Taxonomy Distribution" desc="Cognitive level spread across every question in the question bank (auto-detected at generation time)" />

      <Card title="Bloom Level Count" subtitle="Questions per cognitive level">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={barData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
              {barData.map((_, i) => <Cell key={i} fill={PALETTE.bloom[i % 6]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Difficulty × Bloom Heatmap" subtitle="Intensity = number of questions in that cell">
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                <th className="p-2 text-left text-ink-light font-medium">Difficulty</th>
                {[1,2,3,4,5,6].map(l => (
                  <th key={l} className="p-2 text-center text-ink-light font-medium w-16">L{l}<br/><span className="font-normal opacity-60">{['Rem','Und','App','Ana','Eva','Cre'][l-1]}</span></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DIFFICULTIES.map(diff => (
                <tr key={diff}>
                  <td className="p-2 font-semibold" style={{ color: (PALETTE.diff as Record<string,string>)[diff] }}>{diff}</td>
                  {[1,2,3,4,5,6].map(lvl => {
                    const count = heatGrid[diff]?.[lvl] || 0;
                    const opacity = count === 0 ? 0.05 : 0.15 + (count / maxVal) * 0.85;
                    return (
                      <td key={lvl} className="p-1 text-center">
                        <div
                          className="rounded-lg py-2 px-1 font-bold text-indigo-900"
                          style={{ backgroundColor: `rgba(99,102,241,${opacity})` }}
                        >
                          {count || '–'}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};


const CoverageSection: React.FC<{ data: CoverageData }> = ({ data }) => {
  const [expandedUnit, setExpandedUnit] = useState<number | null>(null);
  const radarData = (data.units || []).map(u => ({
    subject: `U${u.unit}`,
    full_name: u.unit_name,
    coverage: u.coverage_pct,
    fullMark: 100,
  }));

  return (
    <div className="space-y-6">
      <SectionHeader icon="📚" title="Syllabus Coverage" desc="Which syllabus topics/subtopics have at least one generated question in the question bank — per-unit gaps for NBA compliance" />

      {/* Summary chips */}
      <div className="flex flex-wrap gap-3">
        <StatChip label="Overall Coverage" value={`${data.overall_coverage_pct}%`} color="bg-emerald-50 text-emerald-700" />
        <StatChip label="Topics Covered" value={data.covered_count} color="bg-indigo-50 text-indigo-700" />
        <StatChip label="Gap Topics" value={data.gap_count} color="bg-rose-50 text-rose-700" />
        <StatChip label="Total Syllabus Topics" value={data.total_syllabus_topics} color="bg-slate-50 text-slate-700" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Radar */}
        <Card title="Unit Coverage Radar" subtitle="How well each unit is covered">
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
              <Radar name="Coverage %" dataKey="coverage" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} />
              <Tooltip formatter={(v: number) => [`${v}%`, 'Coverage']} />
            </RadarChart>
          </ResponsiveContainer>
        </Card>

        {/* Bar chart per unit */}
        <Card title="Coverage by Unit" subtitle="Covered vs total topics">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.units || []} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="unit_name" tick={{ fontSize: 9 }} />
              <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v}%`, 'Coverage']} />
              <Bar dataKey="coverage_pct" fill="#6366f1" radius={[6, 6, 0, 0]} name="Coverage %" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Per-unit accordion */}
      <Card title="Unit Detail" subtitle="Click a unit to see topic-level coverage">
        <div className="space-y-2">
          {(data.units || []).map(unit => (
            <div key={unit.unit} className="border border-white/80 rounded-xl overflow-hidden">
              <button
                className="w-full flex items-center justify-between px-4 py-3 bg-white/50 hover:bg-white/80 transition-colors text-left"
                onClick={() => setExpandedUnit(expandedUnit === unit.unit ? null : unit.unit)}
              >
                <span className="font-medium text-sm text-ink">
                  Unit {unit.unit}: {unit.unit_name}
                </span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${unit.coverage_pct}%`,
                        backgroundColor: unit.coverage_pct >= 70 ? '#10b981' : unit.coverage_pct >= 40 ? '#f59e0b' : '#ef4444'
                      }}
                    />
                  </div>
                  <span className="text-xs font-semibold text-ink">{unit.coverage_pct}%</span>
                  <span className="text-xs text-ink-light">{expandedUnit === unit.unit ? '▲' : '▼'}</span>
                </div>
              </button>
              {expandedUnit === unit.unit && (
                <div className="px-4 py-3 bg-white/30 grid grid-cols-2 md:grid-cols-3 gap-2">
                  {unit.topics.map(t => (
                    <div
                      key={t.topic}
                      className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs ${
                        t.covered ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-400'
                      }`}
                    >
                      <span>{t.covered ? '✓' : '✗'}</span>
                      <span className="truncate">{t.topic}</span>
                      {t.question_count > 0 && (
                        <span className="ml-auto font-semibold">{t.question_count}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Gap topics list */}
      {(data.gap_topics || []).length > 0 && (
        <Card title="Gap Topics" subtitle="Syllabus topics with zero questions — priority generation targets">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {data.gap_topics.map((g, i) => (
              <div key={i} className="flex flex-col rounded-lg bg-rose-50 border border-rose-100 px-3 py-2 text-xs">
                <span className="text-rose-700 font-medium truncate">{g.topic}</span>
                <span className="text-rose-400 mt-0.5">{g.unit}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};


const TrendsSection: React.FC<{ data: TrendData }> = ({ data }) => {
  const [view, setView] = useState<'daily' | 'weekly'>('daily');
  type AnyRecord = Record<string, string | number>;
  const dataset: AnyRecord[] = view === 'daily'
    ? (data.daily as unknown as AnyRecord[])
    : (data.weekly as unknown as AnyRecord[]);
  const xKey = view === 'daily' ? 'date' : 'week';

  return (
    <div className="space-y-6">
      <SectionHeader icon="📈" title="Generation Trends" desc="Questions created over time with difficulty breakdown" />

      <div className="flex gap-2">
        {(['daily', 'weekly'] as const).map(v => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
              view === v ? 'bg-accent text-white shadow-sm' : 'text-ink-light hover:text-accent'
            }`}
          >
            {v.charAt(0).toUpperCase() + v.slice(1)}
          </button>
        ))}
      </div>

      <Card title={`${view === 'daily' ? 'Daily' : 'Weekly'} Question Volume`} subtitle="Stacked by difficulty">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={dataset} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="Easy" stackId="a" fill={PALETTE.diff.Easy} radius={[0,0,0,0]} />
            <Bar dataKey="Medium" stackId="a" fill={PALETTE.diff.Medium} />
            <Bar dataKey="Hard" stackId="a" fill={PALETTE.diff.Hard} radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {view === 'daily' && (data.daily || []).length > 0 && (
        <Card title="Cumulative Growth" subtitle="Total questions over time">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data.daily} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="cumulative" stroke={PALETTE.line} strokeWidth={2} dot={false} name="Total" />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {view === 'daily' && (data.daily || []).length > 0 && (
        <Card title="Average Difficulty Score" subtitle="1=Easy, 2=Medium, 3=Hard — daily mean">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data.daily} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis domain={[1, 3]} ticks={[1, 2, 3]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="avg_difficulty_score" stroke="#f59e0b" strokeWidth={2} dot={false} name="Avg Difficulty" />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
};


const CoPoSection: React.FC<{ data: CoPoData }> = ({ data }) => {
  const COS = Array.from(new Set((data.matrix || []).map(m => m.co))).sort();
  const POS = Array.from(new Set((data.matrix || []).map(m => m.po))).sort(
    (a, b) => parseInt(a.replace('PO', '')) - parseInt(b.replace('PO', ''))
  );

  const getCell = (co: string, po: string): MatrixEntry | undefined =>
    (data.matrix || []).find(m => m.co === co && m.po === po);

  return (
    <div className="space-y-6">
      <SectionHeader
        icon="🏛️"
        title="CO-PO Attainment Matrix"
        desc="NBA/NAAC compliance — Course Outcome × Program Outcome mapping, computed from every tagged question in the question bank"
      />
      {!!data.untagged_count && (
        <div className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
          {data.untagged_count} question(s) have no CO/PO tag yet and are excluded from this matrix — enable the pedagogy tagger (ENABLE_PEDAGOGY_TAGGER=true) and regenerate to tag them.
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-2 text-xs">
        {[
          { label: 'Not Covered', color: PALETTE.nba[0] },
          { label: 'Level 1 (<5%)', color: PALETTE.nba[1] },
          { label: 'Level 2 (5–15%)', color: PALETTE.nba[2] },
          { label: 'Level 3 (>15%)', color: PALETTE.nba[3] },
        ].map(l => (
          <div key={l.label} className="flex items-center gap-1.5 px-2 py-1 rounded-full border border-slate-200">
            <div className="w-3 h-3 rounded" style={{ backgroundColor: l.color }} />
            <span className="text-ink-light">{l.label}</span>
          </div>
        ))}
      </div>

      {/* Matrix */}
      <Card title="Attainment Matrix" subtitle="Hover cells for exact attainment %">
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                <th className="p-2 text-left text-ink-light font-medium w-24">CO \ PO</th>
                {POS.map(po => (
                  <th key={po} className="p-1 text-center text-ink-light font-medium w-16">
                    {po}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COS.map(co => (
                <tr key={co}>
                  <td className="p-2 font-semibold text-indigo-700">{co}</td>
                  {POS.map(po => {
                    const cell = getCell(co, po);
                    return (
                      <td key={po} className="p-1">
                        <NbaCell level={cell?.nba_level || 0} pct={cell?.attainment_pct || 0} />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* CO bar */}
        <Card title="Course Outcome Distribution" subtitle="Questions per CO">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.co_summary || []} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="co" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v}%`, 'Coverage']} />
              <Bar dataKey="pct" fill="#6366f1" radius={[6, 6, 0, 0]} name="%" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* PO bar */}
        <Card title="Program Outcome Distribution" subtitle="Questions per PO">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.po_summary || []} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="po" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v}%`, 'Coverage']} />
              <Bar dataKey="pct" fill="#8b5cf6" radius={[6, 6, 0, 0]} name="%" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
};


const EDASection: React.FC<{ data: EDAReport }> = ({ data }) => {
  if (!data || !data.total_questions) {
    return (
      <div className="text-center py-12 text-ink-light text-sm">No data available for EDA.</div>
    );
  }

  const bloomBarData = Object.entries(data.bloom?.distribution || {}).map(([k, v]) => ({ name: k, count: v }));
  const topTopics = data.topics?.top_10 || [];
  const coData = Object.entries(data.outcomes?.co_distribution || {}).map(([k, v]) => ({ name: k, value: v }));
  const qualityData = [
    { metric: 'Has Answer', value: data.accuracy_proxy?.questions_with_answer || 0 },
    { metric: 'Has Explanation', value: data.accuracy_proxy?.questions_with_explanation || 0 },
    { metric: 'Has Code', value: data.data_quality?.questions_with_code_pct || 0 },
  ];
  const missingData = [
    { metric: 'Missing Bloom', value: data.data_quality?.missing_bloom_pct || 0 },
    { metric: 'Missing CO', value: data.data_quality?.missing_co_pct || 0 },
    { metric: 'Missing PO', value: data.data_quality?.missing_po_pct || 0 },
  ];

  return (
    <div className="space-y-6">
      <SectionHeader icon="🔬" title="Exploratory Data Analysis" desc="Statistical patterns, data quality, and topic insights" />

      {/* Stats row */}
      <div className="flex flex-wrap gap-3">
        <StatChip label="Mean Difficulty" value={data.difficulty?.mean_score} color="bg-amber-50 text-amber-700" />
        <StatChip label="Variance" value={data.difficulty?.variance} color="bg-rose-50 text-rose-700" />
        <StatChip label="Std Dev" value={data.difficulty?.std_dev} color="bg-orange-50 text-orange-700" />
        <StatChip label="Unique Topics" value={data.topics?.unique_count} color="bg-indigo-50 text-indigo-700" />
        <StatChip label="Bloom Balance" value={`${data.bloom?.balance_score}%`} color="bg-purple-50 text-purple-700" />
        <StatChip label="Avg Bloom" value={data.bloom?.mean_level} color="bg-blue-50 text-blue-700" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Bloom distribution */}
        <Card title="Bloom Distribution" subtitle="Cognitive level spread">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={bloomBarData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {bloomBarData.map((_, i) => <Cell key={i} fill={PALETTE.bloom[i % 6]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Top topics */}
        <Card title="Top 10 Topics" subtitle="Most generated topics">
          <div className="space-y-1.5 mt-1">
            {topTopics.slice(0, 8).map((t, i) => {
              const max = topTopics[0]?.count || 1;
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-xs text-ink-light w-4">{i + 1}</span>
                  <span className="text-xs text-ink truncate flex-1">{t.topic}</span>
                  <div className="w-20 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full rounded-full bg-indigo-400" style={{ width: `${(t.count / max) * 100}%` }} />
                  </div>
                  <span className="text-xs font-semibold text-indigo-600 w-6 text-right">{t.count}</span>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Accuracy/quality */}
        <Card title="Content Quality" subtitle="% of questions with complete metadata">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={qualityData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis dataKey="metric" type="category" tick={{ fontSize: 11 }} width={110} />
              <Tooltip formatter={(v: number) => [`${v}%`]} />
              <Bar dataKey="value" fill="#10b981" radius={[0, 6, 6, 0]} name="%" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Missing data */}
        <Card title="Data Completeness Gaps" subtitle="% of records with missing fields">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={missingData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
              <YAxis dataKey="metric" type="category" tick={{ fontSize: 11 }} width={110} />
              <Tooltip formatter={(v: number) => [`${v}%`]} />
              <Bar dataKey="value" fill="#ef4444" radius={[0, 6, 6, 0]} name="%" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* CO distribution pie */}
      <Card title="CO Distribution" subtitle="Which Course Outcomes are most represented">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={coData} cx="50%" cy="50%" outerRadius={85} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
              {coData.map((_, i) => <Cell key={i} fill={PALETTE.bloom[i % 6]} />)}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
};


// =============================================================================
// PAPER BALANCE CHECKER SECTION
// =============================================================================

const RATING_COLOR: Record<string, string> = {
  Excellent: 'text-emerald-600 bg-emerald-50',
  Good: 'text-blue-600 bg-blue-50',
  Fair: 'text-amber-600 bg-amber-50',
  Poor: 'text-rose-600 bg-rose-50',
};

const PaperBalanceSection: React.FC<{ data: PaperBalance }> = ({ data }) => {
  const chartData = (data.bloom_levels || []).map(l => ({
    name: l.label,
    Actual: l.actual_pct,
    Ideal: l.ideal_pct,
  }));

  const diffData = Object.entries(data.difficulty_distribution || {}).map(([k, v]) => ({
    name: k, Actual: v, Ideal: (data.ideal_difficulty || {})[k] || 0,
  }));

  return (
    <div className="space-y-6">
      <SectionHeader icon="⚖️" title="Question Bank Balance Checker" desc="Compares the ENTIRE question bank's Bloom distribution against the ideal — flags cognitive imbalances across all generated questions" />

      <div className="flex flex-wrap gap-3 items-center">
        <div className={`px-5 py-3 rounded-2xl font-bold text-lg ${RATING_COLOR[data.rating] || 'text-ink bg-slate-50'}`}>
          {data.rating} — {data.balance_score}%
        </div>
        <StatChip label="Total Questions in Bank" value={data.total_questions} color="bg-indigo-50 text-indigo-700" />
        {!!data.unclassified_questions && (
          <StatChip label="Unclassified (no Bloom level)" value={data.unclassified_questions} color="bg-amber-50 text-amber-700" />
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Bloom Level: Actual vs Ideal" subtitle="% of questions per cognitive level">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v}%`]} />
              <Legend />
              <Bar dataKey="Actual" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Ideal" fill="#e0e7ff" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Difficulty: Actual vs Ideal" subtitle="% Easy / Medium / Hard">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={diffData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => [`${v}%`]} />
              <Legend />
              <Bar dataKey="Actual" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Ideal" fill="#fef3c7" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Level detail table */}
      <Card title="Level-by-Level Breakdown" subtitle="Deviation from ideal per Bloom level">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-ink-light border-b border-slate-100">
                <th className="p-2 text-left">Level</th>
                <th className="p-2 text-right">Count</th>
                <th className="p-2 text-right">Actual %</th>
                <th className="p-2 text-right">Ideal %</th>
                <th className="p-2 text-right">Deviation</th>
                <th className="p-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {(data.bloom_levels || []).map(l => (
                <tr key={l.bloom_level} className="border-b border-slate-50 hover:bg-slate-50/50">
                  <td className="p-2 font-medium">L{l.bloom_level} {l.label}</td>
                  <td className="p-2 text-right">{l.actual_count}</td>
                  <td className="p-2 text-right">{l.actual_pct}%</td>
                  <td className="p-2 text-right text-ink-light">{l.ideal_pct}%</td>
                  <td className={`p-2 text-right font-semibold ${l.deviation > 0 ? 'text-amber-600' : l.deviation < 0 ? 'text-rose-500' : 'text-emerald-600'}`}>
                    {l.deviation > 0 ? `+${l.deviation}` : l.deviation}%
                  </td>
                  <td className="p-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      l.status === 'balanced' ? 'bg-emerald-50 text-emerald-700' :
                      l.status === 'over-represented' ? 'bg-amber-50 text-amber-700' :
                      'bg-rose-50 text-rose-600'
                    }`}>{l.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Suggestions */}
      {(data.suggestions || []).length > 0 && (
        <Card title="Improvement Suggestions" subtitle="Actions to improve paper balance">
          <ul className="space-y-2">
            {data.suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink">
                <span className="mt-0.5 text-amber-500">⚠</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
};


// =============================================================================
// REPETITION & SIMILARITY SECTION
// =============================================================================

const LABEL_COLOR: Record<string, string> = {
  'exact duplicate': 'bg-rose-100 text-rose-700',
  'near-duplicate': 'bg-orange-100 text-orange-700',
  'similar': 'bg-amber-100 text-amber-700',
};

const SimilaritySection: React.FC<{ data: SimilarityReport; onRefresh: (t: number) => void }> = ({ data, onRefresh }) => {
  const [threshold, setThreshold] = useState(0.55);
  const [removing, setRemoving] = useState(false);
  const [removeResult, setRemoveResult] = useState<string | null>(null);

  const summaryData = Object.entries(data.label_summary || {}).map(([k, v]) => ({ name: k, count: v }));

  const handleRemoveDuplicates = async () => {
    setRemoving(true);
    setRemoveResult(null);
    try {
      const res = await fetch(`${API}/similarity/remove-duplicates?threshold=${threshold}`, { method: 'POST' });
      const result = await res.json();
      setRemoveResult(`Removed ${result.removed_count ?? 0} duplicate question(s).`);
      onRefresh(threshold);
      notifyDataChanged(); // other tabs (overview counts, bloom, etc.) need to refresh too
    } catch {
      setRemoveResult('Failed to remove duplicates.');
    } finally {
      setRemoving(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader icon="🔁" title="Repetition & Similar Question Detection" desc="Semantic similarity analysis to prevent repeated questions across papers" />

      <div className="flex flex-wrap gap-3 items-center">
        <StatChip label="Questions Scanned" value={data.total_questions} color="bg-indigo-50 text-indigo-700" />
        <StatChip label="Flagged Pairs" value={data.flagged_count} color={data.flagged_count > 0 ? 'bg-rose-50 text-rose-700' : 'bg-emerald-50 text-emerald-700'} />
        <StatChip label="Threshold" value={`${Math.round(data.threshold_used * 100)}%`} color="bg-slate-50 text-slate-700" />
      </div>

      {/* Threshold slider */}
      <Card title="Similarity Threshold" subtitle="Higher = stricter — only flags very similar questions">
        <div className="flex items-center gap-4">
          <input
            type="range" min={0.3} max={0.95} step={0.05}
            value={threshold}
            onChange={e => setThreshold(Number(e.target.value))}
            className="flex-1 accent-indigo-500"
          />
          <span className="text-sm font-semibold text-ink w-12">{Math.round(threshold * 100)}%</span>
          <button
            onClick={() => onRefresh(threshold)}
            className="px-4 py-1.5 rounded-full bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-all"
          >
            Reanalyze
          </button>
          {data.flagged_count > 0 && (
            <button
              onClick={handleRemoveDuplicates}
              disabled={removing}
              className="px-4 py-1.5 rounded-full bg-rose-600 text-white text-sm font-medium hover:bg-rose-700 transition-all disabled:opacity-50"
              title="Deletes the newer question from every flagged pair at or above the current threshold"
            >
              {removing ? 'Removing…' : `Remove ${data.flagged_count} Flagged Duplicate${data.flagged_count === 1 ? '' : 's'}`}
            </button>
          )}
        </div>
        {removeResult && <p className="text-xs text-ink-light mt-2">{removeResult}</p>}
      </Card>

      {summaryData.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card title="Flagged Pairs by Type" subtitle="Breakdown of similarity categories">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={summaryData} cx="50%" cy="50%" outerRadius={75} dataKey="count"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                  {summaryData.map((_, i) => (
                    <Cell key={i} fill={['#ef4444', '#f97316', '#f59e0b'][i % 3]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>

          <Card title="How to Interpret" subtitle="Similarity label guide">
            <div className="space-y-3 mt-2">
              {[
                { label: 'exact duplicate', desc: '≥95% — identical or near-identical wording', color: 'bg-rose-100 text-rose-700' },
                { label: 'near-duplicate', desc: '75–94% — very similar, different phrasing', color: 'bg-orange-100 text-orange-700' },
                { label: 'similar', desc: `${Math.round(threshold*100)}–74% — overlapping concepts`, color: 'bg-amber-100 text-amber-700' },
              ].map(item => (
                <div key={item.label} className="flex items-start gap-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap ${item.color}`}>{item.label}</span>
                  <span className="text-xs text-ink-light">{item.desc}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {data.flagged_count === 0 ? (
        <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-xl px-5 py-4 text-emerald-700 text-sm font-medium">
          <span>✓</span> No similar question pairs detected at {Math.round(data.threshold_used * 100)}% threshold.
        </div>
      ) : (
        <Card title={`${data.flagged_count} Flagged Pairs`} subtitle="Review and remove duplicates to ensure diverse assessments">
          <div className="space-y-3">
            {(data.pairs || []).map((pair, i) => (
              <div key={i} className="border border-slate-100 rounded-xl p-4 bg-white/60 space-y-2">
                <div className="flex items-center justify-between">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${LABEL_COLOR[pair.label] || 'bg-slate-100 text-slate-600'}`}>
                    {pair.label}
                  </span>
                  <span className="text-xs font-bold text-indigo-600">{Math.round(pair.similarity_score * 100)}% similar</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  <div className="bg-slate-50 rounded-lg p-2 text-xs">
                    <div className="text-ink-light mb-1">Q#{pair.question_a_id} · {pair.topic_a}</div>
                    <div className="text-ink">{pair.question_a_preview}</div>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-2 text-xs">
                    <div className="text-ink-light mb-1">Q#{pair.question_b_id} · {pair.topic_b}</div>
                    <div className="text-ink">{pair.question_b_preview}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};


// =============================================================================
// STUDENT PERFORMANCE FEEDBACK SECTION
// =============================================================================

const FeedbackSection: React.FC<{ data: FeedbackAnalysis; onSubmitSample: () => void }> = ({ data, onSubmitSample }) => {
  if (!data.total_responses || data.message) {
    return (
      <div className="space-y-6">
        <SectionHeader icon="🎓" title="Student Performance Feedback" desc="Analyze student responses to identify difficult questions and weak topic areas" />
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 space-y-3">
          <p className="text-sm text-amber-700 font-medium">No student feedback submitted yet.</p>
          <p className="text-xs text-amber-600">Submit feedback via <code className="bg-amber-100 px-1 rounded">POST /api/v1/dav/feedback</code> or load sample data:</p>
          <button
            onClick={onSubmitSample}
            className="px-4 py-2 rounded-full bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-all"
          >
            Load Sample Feedback Data
          </button>
        </div>
      </div>
    );
  }

  const scoreDistData = Object.entries(data.score_distribution || {}).map(([k, v]) => ({ name: k, count: v }));
  const topicData = (data.topic_performance || []).slice(0, 10);

  return (
    <div className="space-y-6">
      <SectionHeader icon="🎓" title="Student Performance Feedback" desc="Difficult question detection, weak topic identification, and score distributions" />

      <div className="flex flex-wrap gap-3">
        <StatChip label="Total Responses" value={data.total_responses} color="bg-indigo-50 text-indigo-700" />
        <StatChip label="Overall Accuracy" value={`${data.overall_accuracy_pct}%`} color={data.overall_accuracy_pct >= 60 ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'} />
        <StatChip label="Avg Score" value={data.avg_score} color="bg-purple-50 text-purple-700" />
        <StatChip label="Flagged Questions" value={data.flagged_question_count} color="bg-rose-50 text-rose-700" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Score Distribution" subtitle="How students scored across all questions">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={scoreDistData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#6366f1" radius={[6, 6, 0, 0]} name="Students" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Topic Performance" subtitle="Average score per topic (lowest first)">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={topicData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
              <YAxis dataKey="topic" type="category" tick={{ fontSize: 9 }} width={90} />
              <Tooltip />
              <Bar dataKey="avg_score" radius={[0, 6, 6, 0]} name="Avg Score">
                {topicData.map((entry, i) => (
                  <Cell key={i} fill={entry.avg_score < 50 ? '#ef4444' : entry.avg_score < 70 ? '#f59e0b' : '#10b981'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {(data.weak_topics || []).length > 0 && (
        <Card title="Weak Topic Areas" subtitle="Topics where students scored below 50% accuracy">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {data.weak_topics.map((t, i) => (
              <div key={i} className="flex items-center justify-between bg-rose-50 border border-rose-100 rounded-xl px-4 py-2">
                <span className="text-sm font-medium text-rose-700 truncate">{t.topic}</span>
                <div className="flex items-center gap-2 ml-2 shrink-0">
                  <span className="text-xs text-rose-500">{t.accuracy_pct}% acc</span>
                  <span className="text-xs font-bold text-rose-700">{t.avg_score}/100</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card title="Difficult Questions" subtitle="Questions with <50% accuracy — consider revising or adding hints">
        <div className="space-y-2">
          {(data.difficult_questions || []).filter(q => q.flagged).slice(0, 10).map(q => (
            <div key={q.question_id} className="flex items-center gap-3 bg-white/60 border border-rose-100 rounded-xl px-4 py-2">
              <div className="flex-1 min-w-0">
                <div className="text-xs text-ink-light">Q#{q.question_id} · {q.topic} · L{q.bloom_level} {q.bloom_label}</div>
              </div>
              <div className="flex items-center gap-3 text-xs shrink-0">
                <span className="text-rose-600 font-semibold">{q.accuracy_pct}% acc</span>
                <span className="text-ink-light">{q.avg_score}/100</span>
                <span className="text-ink-light">{q.avg_time_sec}s avg</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};


// =============================================================================
// CO/PO CONSISTENCY CHECK SECTION
// =============================================================================

const ISSUE_COLOR: Record<string, string> = {
  co_mismatch: 'bg-rose-50 border-rose-200 text-rose-700',
  po_mismatch: 'bg-orange-50 border-orange-200 text-orange-700',
  missing_tag: 'bg-amber-50 border-amber-200 text-amber-700',
};

const ConsistencySection: React.FC<{ data: CoPoConsistency }> = ({ data }) => {
  const [filter, setFilter] = useState<string>('all');

  const filtered = (data.issues || []).filter(i => filter === 'all' || i.issue_type === filter);

  const summaryData = [
    { name: 'CO Mismatch', count: data.co_mismatch_count, color: '#ef4444' },
    { name: 'PO Mismatch', count: data.po_mismatch_count, color: '#f97316' },
    { name: 'Missing Tags', count: data.missing_tags_count, color: '#f59e0b' },
    { name: 'Consistent', count: data.consistent_count, color: '#10b981' },
  ];

  const scoreColor = data.consistency_score >= 80 ? 'text-emerald-600 bg-emerald-50'
    : data.consistency_score >= 60 ? 'text-amber-600 bg-amber-50' : 'text-rose-600 bg-rose-50';

  return (
    <div className="space-y-6">
      <SectionHeader icon="✅" title="CO/PO Mapping Consistency Check" desc="Validates that CO/PO tags align with Bloom level rules for accreditation compliance" />

      <div className="flex flex-wrap gap-3 items-center">
        <div className={`px-5 py-3 rounded-2xl font-bold text-lg ${scoreColor}`}>
          {data.consistency_score}% Consistent
        </div>
        <StatChip label="Total Questions" value={data.total_questions} color="bg-indigo-50 text-indigo-700" />
        <StatChip label="Issues Found" value={data.issue_count} color={data.issue_count > 0 ? 'bg-rose-50 text-rose-700' : 'bg-emerald-50 text-emerald-700'} />
        <StatChip label="Consistent" value={data.consistent_count} color="bg-emerald-50 text-emerald-700" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Issue Breakdown" subtitle="Types of CO/PO mapping errors">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={summaryData} cx="50%" cy="50%" outerRadius={80} dataKey="count"
                label={({ name, percent }) => percent > 0 ? `${name} ${(percent * 100).toFixed(0)}%` : ''}>
                {summaryData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Bloom → CO Rules" subtitle="Expected CO for each Bloom level">
          <div className="space-y-2 mt-1">
            {Object.entries(data.bloom_co_rules || {}).map(([lvl, cos]) => (
              <div key={lvl} className="flex items-center gap-2 text-xs">
                <span className="w-16 font-medium text-indigo-700">Bloom L{lvl}</span>
                <span className="text-ink-light">→</span>
                <div className="flex gap-1">
                  {(cos as string[]).map(co => (
                    <span key={co} className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-semibold">{co}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {data.issue_count > 0 && (
        <>
          {/* Filter */}
          <div className="flex gap-2">
            {['all', 'co_mismatch', 'po_mismatch', 'missing_tag'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                  filter === f ? 'bg-accent text-white' : 'text-ink-light hover:text-accent'
                }`}
              >
                {f === 'all' ? `All (${data.issue_count})` :
                  f === 'co_mismatch' ? `CO Mismatch (${data.co_mismatch_count})` :
                  f === 'po_mismatch' ? `PO Mismatch (${data.po_mismatch_count})` :
                  `Missing Tags (${data.missing_tags_count})`}
              </button>
            ))}
          </div>

          <Card title="Flagged Questions" subtitle="Questions with inconsistent CO/PO mapping">
            <div className="space-y-2">
              {filtered.slice(0, 20).map((issue, i) => (
                <div key={i} className={`border rounded-xl px-4 py-3 text-xs space-y-1 ${ISSUE_COLOR[issue.issue_type] || 'bg-slate-50 border-slate-200 text-slate-700'}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">Q#{issue.question_id} · {issue.topic}</span>
                    <div className="flex gap-2">
                      <span className="font-medium">L{issue.bloom_level} {issue.bloom_label}</span>
                      <span>CO: {issue.co}</span>
                      <span>PO: {issue.po}</span>
                    </div>
                  </div>
                  <div className="opacity-80">{issue.message}</div>
                  {issue.text_preview && (
                    <div className="italic opacity-60 truncate">{issue.text_preview}…</div>
                  )}
                </div>
              ))}
              {filtered.length > 20 && (
                <p className="text-xs text-ink-light text-center pt-2">
                  Showing 20 of {filtered.length} issues
                </p>
              )}
            </div>
          </Card>
        </>
      )}

      {data.issue_count === 0 && (
        <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-xl px-5 py-4 text-emerald-700 text-sm font-medium">
          <span>✓</span> All CO/PO mappings are consistent with Bloom level rules.
        </div>
      )}
    </div>
  );
};


// =============================================================================
// MAIN DAV MODULE
// =============================================================================

type DAVTab = 'overview' | 'bloom' | 'coverage' | 'trends' | 'copo' | 'eda' | 'balance' | 'similarity' | 'feedback' | 'consistency';

const TABS: { id: DAVTab; label: string; icon: string }[] = [
  { id: 'overview',     label: 'Overview',   icon: '📊' },
  { id: 'bloom',        label: "Bloom's",    icon: '🧠' },
  { id: 'coverage',     label: 'Coverage',   icon: '📚' },
  { id: 'trends',       label: 'Trends',     icon: '📈' },
  { id: 'copo',         label: 'CO-PO',      icon: '🏛️' },
  { id: 'eda',          label: 'EDA',        icon: '🔬' },
  { id: 'balance',      label: 'Balance',    icon: '⚖️' },
  { id: 'similarity',   label: 'Similarity', icon: '🔁' },
  { id: 'feedback',     label: 'Feedback',   icon: '🎓' },
  { id: 'consistency',  label: 'Consistency',icon: '✅' },
];

const DAVModule: React.FC = () => {
  const [activeTab, setActiveTab] = useState<DAVTab>('overview');
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [cleanResult, setCleanResult] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [overview, setOverview] = useState<Overview | null>(null);
  const [bloom, setBloom] = useState<BloomData | null>(null);
  const [coverage, setCoverage] = useState<CoverageData | null>(null);
  const [trends, setTrends] = useState<TrendData | null>(null);
  const [copo, setCopo] = useState<CoPoData | null>(null);
  const [eda, setEda] = useState<EDAReport | null>(null);
  const [balance, setBalance] = useState<PaperBalance | null>(null);
  const [similarity, setSimilarity] = useState<SimilarityReport | null>(null);
  const [feedback, setFeedback] = useState<FeedbackAnalysis | null>(null);
  const [consistency, setConsistency] = useState<CoPoConsistency | null>(null);
  const [simThreshold, setSimThreshold] = useState(0.55);

  const fetchTab = useCallback(async (tab: DAVTab, extra?: Record<string, unknown>, silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const endpointMap: Record<DAVTab, string> = {
        overview:     `${API}/overview`,
        bloom:        `${API}/bloom-distribution`,
        coverage:     `${API}/topic-coverage`,
        trends:       `${API}/difficulty-trends`,
        copo:         `${API}/copo-matrix`,
        eda:          `${API}/eda-report`,
        balance:      `${API}/paper-balance`,
        similarity:   `${API}/similarity?threshold=${extra?.threshold ?? simThreshold}`,
        feedback:     `${API}/feedback`,
        consistency:  `${API}/copo-consistency`,
      };
      const res = await fetch(endpointMap[tab], { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (tab === 'overview') setOverview(data);
      else if (tab === 'bloom') setBloom(data);
      else if (tab === 'coverage') setCoverage(data);
      else if (tab === 'trends') setTrends(data);
      else if (tab === 'copo') setCopo(data);
      else if (tab === 'eda') setEda(data);
      else if (tab === 'balance') setBalance(data);
      else if (tab === 'similarity') setSimilarity(data);
      else if (tab === 'feedback') setFeedback(data);
      else if (tab === 'consistency') setConsistency(data);
    } catch (e: unknown) {
      // Silent background refreshes shouldn't surface transient network blips as page errors
      if (!silent) setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [simThreshold]);

  useEffect(() => {
    fetchTab(activeTab);
  }, [activeTab, fetchTab]);

  // Keep the currently viewed tab reachable for effects below without
  // re-subscribing them every time the user switches tabs.
  const activeTabRef = useRef(activeTab);
  activeTabRef.current = activeTab;

  // 1. Instant refresh: fires the moment a question/paper is generated
  //    anywhere in the app (see services/events.ts), even if that happened
  //    on a different tab that stayed mounted in the background.
  useEffect(() => {
    return onDataChanged(() => fetchTab(activeTabRef.current, undefined, true));
  }, [fetchTab]);

  // 2. Fallback polling: catches anything the event above misses (e.g. a
  //    paper still streaming when this tab was opened) without needing a
  //    manual refresh click.
  useEffect(() => {
    const id = setInterval(() => fetchTab(activeTabRef.current, undefined, true), AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [fetchTab]);

  // 3. Refresh when the browser tab/window regains focus (e.g. user tabbed
  //    away to generate something, then tabbed back).
  useEffect(() => {
    const onFocus = () => fetchTab(activeTabRef.current, undefined, true);
    const onVisibility = () => {
      if (document.visibilityState === 'visible') onFocus();
    };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [fetchTab]);

  const handleSimilarityRefresh = (t: number) => {
    setSimThreshold(t);
    fetchTab('similarity', { threshold: t });
  };

  const handleSampleFeedback = async () => {
    // Fetch existing question IDs then POST mock feedback
    try {
      const overviewRes = await fetch(`${API}/overview`);
      const overviewData = await overviewRes.json();
      if (!overviewData.total_questions) {
        setError('Generate some questions first before loading sample feedback.');
        return;
      }
      // Post 20 mock feedback entries spread across first few question IDs
      const feedbacks = Array.from({ length: 20 }, (_, i) => ({
        question_id: (i % Math.max(overviewData.total_questions, 1)) + 1,
        student_id: `student_${i % 5 + 1}`,
        score: Math.floor(Math.random() * 100),
        time_taken_sec: Math.floor(Math.random() * 120) + 20,
        correct: Math.random() > 0.45,
        difficulty_felt: ['Easy', 'Medium', 'Hard'][Math.floor(Math.random() * 3)],
      }));
      await fetch(`${API}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedbacks }),
      });
      fetchTab('feedback');
    } catch {
      setError('Failed to submit sample feedback');
    }
  };

  const handleClean = async () => {
    setCleaning(true);
    setCleanResult(null);
    try {
      const res = await fetch(`${API}/clean`, { method: 'POST' });
      const data = await res.json();
      setCleanResult(data);
      // Refresh overview after cleaning
      fetchTab('overview');
    } catch {
      setError('Data cleaning failed');
    } finally {
      setCleaning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Section title */}
      <div>
        <h1 className="text-2xl font-bold text-ink">Data Analytics & Visualization</h1>
        <p className="text-sm text-ink-light mt-1">
          Exploratory analysis, Bloom taxonomy, syllabus coverage, paper balance, similarity detection, student feedback, and CO-PO consistency.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1.5 bg-white/50 backdrop-blur-sm p-1.5 rounded-2xl border border-white/60 shadow-sm w-fit">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
              activeTab === t.id
                ? 'bg-accent text-white shadow-md shadow-accent/20'
                : 'text-ink-light hover:text-accent hover:bg-accent-soft/40'
            }`}
          >
            <span>{t.icon}</span>
            <span>{t.label}</span>
          </button>
        ))}
        <button
          onClick={() => fetchTab(activeTab)}
          className="px-3 py-2 rounded-xl text-ink-light hover:text-accent hover:bg-accent-soft/40 transition-all text-sm"
          title="Refresh"
        >
          ↺
        </button>
        <span className="flex items-center gap-1 px-2 text-xs text-emerald-600" title="Auto-updates when new questions/papers are generated">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Live
        </span>
      </div>

      {/* Clean result banner */}
      {cleanResult && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-sm text-emerald-700 flex items-center gap-3">
          <span>✓</span>
          <span>
            Cleaned: {cleanResult.duplicates_removed} duplicates removed,{' '}
            {cleanResult.bloom_filled} Bloom fields filled,{' '}
            {cleanResult.difficulty_standardized} difficulty values standardized.
          </span>
          <button onClick={() => setCleanResult(null)} className="ml-auto text-emerald-400 hover:text-emerald-600">✕</button>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <Spinner />
      ) : error ? (
        <div className="bg-rose-50 border border-rose-200 rounded-xl px-4 py-3 text-sm text-rose-600">
          {error}. Make sure the backend is running.
        </div>
      ) : (
        <>
          {activeTab === 'overview' && overview && (
            <OverviewSection data={overview} onClean={handleClean} cleaning={cleaning} />
          )}
          {activeTab === 'bloom' && bloom && <BloomSection data={bloom} />}
          {activeTab === 'coverage' && coverage && <CoverageSection data={coverage} />}
          {activeTab === 'trends' && trends && <TrendsSection data={trends} />}
          {activeTab === 'copo' && copo && <CoPoSection data={copo} />}
          {activeTab === 'eda' && eda && <EDASection data={eda} />}
          {activeTab === 'balance' && balance && <PaperBalanceSection data={balance} />}
          {activeTab === 'similarity' && similarity && (
            <SimilaritySection data={similarity} onRefresh={handleSimilarityRefresh} />
          )}
          {activeTab === 'feedback' && (
            <FeedbackSection
              data={feedback || { total_responses: 0, message: 'No feedback yet.' } as FeedbackAnalysis}
              onSubmitSample={handleSampleFeedback}
            />
          )}
          {activeTab === 'consistency' && consistency && <ConsistencySection data={consistency} />}
        </>
      )}
    </div>
  );
};

export default DAVModule;
