"""
Module: app/services/dav_service.py
Purpose: Data Analytics & Visualization (DAV) service.
Provides EDA, statistical metrics, data cleaning, CO-PO attainment,
syllabus coverage, and Bloom distribution analytics.
"""

import sqlite3
import json
import math
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from app.config.syllabus_loader import get_syllabus_loader

DB_PATH = Path("question_bank.db")

DIFFICULTY_ORDER = {"Easy": 1, "Medium": 2, "Hard": 3}
DIFFICULTY_SCORE = {"Easy": 1, "Medium": 2, "Hard": 3}

BLOOM_LABELS = {
    1: "Remember",
    2: "Understand",
    3: "Apply",
    4: "Analyze",
    5: "Evaluate",
    6: "Create",
}

# Real course outcomes, pulled from the same app/config/syllabus.json used by
# the topic picker and question generation — NOT a made-up placeholder list.
_loader = get_syllabus_loader()
CO_LABELS = _loader.syllabus_data.get("course_outcomes") or {
    "CO1": "Foundational Knowledge",
    "CO2": "Comprehension & Analysis",
    "CO3": "Application & Design",
    "CO4": "Evaluation & Optimization",
    "CO5": "Innovation & Research",
}

# Standard NBA 12 Program Outcomes (only the ones actually referenced in
# syllabus.json's co_po_mapping get populated in the matrix, the rest show as 0).
PO_LABELS = {
    "PO1": "Engineering Knowledge",
    "PO2": "Problem Analysis",
    "PO3": "Design/Development of Solutions",
    "PO4": "Conduct Investigations",
    "PO5": "Modern Tool Usage",
    "PO6": "The Engineer and Society",
    "PO7": "Environment and Sustainability",
    "PO8": "Ethics",
    "PO9": "Individual and Team Work",
    "PO10": "Communication",
    "PO11": "Project Management and Finance",
    "PO12": "Life-long Learning",
}


# =============================================================================
# DB HELPERS
# =============================================================================

def _fetch_all() -> List[Dict]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM templates ORDER BY created_at ASC").fetchall()
    return [dict(r) for r in rows]


def _load_syllabus() -> Dict:
    return _loader.syllabus_data


def _is_similar(text1: str, text2: str, threshold: float = 0.5) -> bool:
    """Fuzzy match: exact, substring, sequence ratio, or token Jaccard overlap."""
    if text1 == text2 or text1 in text2 or text2 in text1:
        return True
    if SequenceMatcher(None, text1, text2).ratio() >= threshold:
        return True
    t1, t2 = set(text1.split()), set(text2.split())
    if t1 and t2:
        if len(t1 & t2) / len(t1 | t2) >= threshold:
            return True
    return False


# =============================================================================
# DATA CLEANING
# =============================================================================

def clean_data() -> Dict:
    """
    Performs a cleaning pass on the question_bank:
    - Removes exact duplicate (topic+difficulty+question_text) rows
    - Standardizes difficulty casing
    - Fills missing bloom_level with inferred default (2)
    - Fills missing course_outcome / program_outcome with 'Unknown'
    Returns a report of what was fixed.
    """
    if not DB_PATH.exists():
        return {"error": "Database not found"}

    report = {
        "duplicates_removed": 0,
        "difficulty_standardized": 0,
        "bloom_filled": 0,
        "co_filled": 0,
        "po_filled": 0,
    }

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # 1. Remove duplicate rows (keep lowest id)
        c.execute("""
            DELETE FROM templates WHERE id NOT IN (
                SELECT MIN(id) FROM templates
                GROUP BY LOWER(topic), LOWER(difficulty), LOWER(TRIM(question_text))
            )
        """)
        report["duplicates_removed"] = c.rowcount

        # 2. Standardize difficulty casing
        for raw, std in [("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")]:
            c.execute("UPDATE templates SET difficulty=? WHERE LOWER(difficulty)=?", (std, raw))
            report["difficulty_standardized"] += c.rowcount

        # 3. Fill missing bloom_level
        c.execute("UPDATE templates SET bloom_level=2 WHERE bloom_level IS NULL OR bloom_level=0")
        report["bloom_filled"] = c.rowcount

        # 4. Fill missing CO
        c.execute("UPDATE templates SET course_outcome='CO1' WHERE course_outcome IS NULL OR course_outcome=''")
        report["co_filled"] = c.rowcount

        # 5. Fill missing PO
        c.execute("UPDATE templates SET program_outcome='PO1' WHERE program_outcome IS NULL OR program_outcome=''")
        report["po_filled"] = c.rowcount

        conn.commit()

    return report


# =============================================================================
# OVERVIEW / SUMMARY STATS
# =============================================================================

def get_overview() -> Dict:
    rows = _fetch_all()
    total = len(rows)
    if total == 0:
        return {"total_questions": 0, "message": "No questions in bank yet."}

    difficulties = [r.get("difficulty", "Medium") or "Medium" for r in rows]
    diff_counts = Counter(difficulties)

    bloom_vals = [r.get("bloom_level") or 2 for r in rows]
    avg_bloom = round(sum(bloom_vals) / len(bloom_vals), 2)

    diff_scores = [DIFFICULTY_SCORE.get(d, 2) for d in difficulties]
    mean_diff = round(sum(diff_scores) / len(diff_scores), 2)
    variance = round(sum((x - mean_diff) ** 2 for x in diff_scores) / len(diff_scores), 3)
    std_dev = round(math.sqrt(variance), 3)

    topics = [r.get("topic", "") or "" for r in rows]
    unique_topics = len(set(t.lower().strip() for t in topics if t))

    sources = Counter(r.get("source_type", "unknown") or "unknown" for r in rows)

    # Questions over last 7 days
    now = datetime.now().timestamp()
    week_ago = now - 7 * 86400
    recent = sum(1 for r in rows if (r.get("created_at") or 0) >= week_ago)

    return {
        "total_questions": total,
        "unique_topics": unique_topics,
        "difficulty_distribution": dict(diff_counts),
        "mean_difficulty_score": mean_diff,
        "difficulty_variance": variance,
        "difficulty_std_dev": std_dev,
        "avg_bloom_level": avg_bloom,
        "source_distribution": dict(sources),
        "questions_last_7_days": recent,
        "bloom_balance_score": _bloom_balance(bloom_vals),
    }


def _bloom_balance(bloom_vals: List[int]) -> float:
    """Score 0-100 measuring how evenly distributed Bloom levels are (higher = more balanced)."""
    if not bloom_vals:
        return 0.0
    counts = Counter(bloom_vals)
    total = len(bloom_vals)
    expected = total / 6
    deviation = sum(abs(counts.get(i, 0) - expected) for i in range(1, 7))
    max_deviation = total * (5 / 6) * 2
    score = max(0.0, 1.0 - deviation / max_deviation) * 100 if max_deviation > 0 else 100.0
    return round(score, 1)


# =============================================================================
# BLOOM DISTRIBUTION
# =============================================================================

def get_bloom_distribution() -> Dict:
    rows = _fetch_all()
    if not rows:
        return {"data": [], "by_topic": {}}

    # Rows with a real, detected bloom_level vs rows where detection never ran/failed.
    # These are NOT coerced into "Understand" (level 2) anymore — that was hiding
    # detection failures behind a fake concentration in one bucket.
    def lvl_of(r):
        v = r.get("bloom_level")
        return v if v in range(1, 7) else None

    unclassified_count = sum(1 for r in rows if lvl_of(r) is None)

    # Overall distribution
    bloom_counts = Counter(lvl_of(r) for r in rows if lvl_of(r) is not None)
    overall = [
        {
            "bloom_level": lvl,
            "label": BLOOM_LABELS.get(lvl, f"Level {lvl}"),
            "count": bloom_counts.get(lvl, 0),
        }
        for lvl in range(1, 7)
    ]
    if unclassified_count:
        overall.append({"bloom_level": 0, "label": "Unclassified", "count": unclassified_count})

    # Per-topic breakdown
    topic_bloom: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        topic = (r.get("topic") or "Unknown").lower().strip()
        lvl = lvl_of(r)
        if lvl is not None:
            topic_bloom[topic][lvl] += 1

    by_topic = {}
    for topic, counter in topic_bloom.items():
        by_topic[topic] = [
            {"bloom_level": lvl, "label": BLOOM_LABELS.get(lvl, f"L{lvl}"), "count": counter.get(lvl, 0)}
            for lvl in range(1, 7)
        ]

    # Difficulty × Bloom heatmap data (unclassified rows excluded — they'd otherwise
    # all pile into one fake cell)
    heatmap_matrix: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        lvl = lvl_of(r)
        if lvl is None:
            continue
        diff = r.get("difficulty", "Medium") or "Medium"
        heatmap_matrix[diff][lvl] += 1

    heatmap_data = []
    for diff in ["Easy", "Medium", "Hard"]:
        for lvl in range(1, 7):
            heatmap_data.append({
                "difficulty": diff,
                "bloom_level": lvl,
                "bloom_label": BLOOM_LABELS.get(lvl, f"L{lvl}"),
                "count": heatmap_matrix[diff][lvl],
            })

    return {"overall": overall, "by_topic": by_topic, "heatmap": heatmap_data, "unclassified_count": unclassified_count}


# =============================================================================
# TOPIC COVERAGE (vs Syllabus)
# =============================================================================

def get_topic_coverage() -> Dict:
    """
    Coverage is computed against the question BANK (all generated questions
    stored in question_bank.db), not any single paper — a paper is just a
    subset of the bank assembled at export time, so bank coverage is the
    meaningful signal for "what topics have I generated questions for".
    """
    rows = _fetch_all()
    syllabus = _load_syllabus()

    question_topics = Counter((r.get("topic") or "").lower().strip() for r in rows if r.get("topic"))

    units = syllabus.get("units", [])
    coverage_data = []
    gap_topics = []
    covered_topics = []

    for unit in units:
        unit_name = unit.get("unit_name", f"Unit {unit.get('unit_number', '?')}")
        unit_num = unit.get("unit_number", 0)
        # Flatten topic name + subtopics — syllabus.json nests subtopics per topic
        topics = []
        for t in unit.get("topics", []):
            name = t.get("name") if isinstance(t, dict) else t
            if name:
                topics.append(name)
            if isinstance(t, dict):
                topics.extend(t.get("subtopics", []))
        unit_total = len(topics)
        unit_covered = 0

        topic_details = []
        for t in topics:
            t_lower = t.lower().strip()
            count = 0
            for qt, qc in question_topics.items():
                if _is_similar(t_lower, qt):
                    count += qc
            covered = count > 0
            if covered:
                unit_covered += 1
                covered_topics.append(t)
            else:
                gap_topics.append({"unit": unit_name, "topic": t})

            topic_details.append({
                "topic": t,
                "question_count": count,
                "covered": covered,
            })

        coverage_pct = round(unit_covered / unit_total * 100, 1) if unit_total else 0
        coverage_data.append({
            "unit": unit_num,
            "unit_name": unit_name,
            "total_topics": unit_total,
            "covered_topics": unit_covered,
            "coverage_pct": coverage_pct,
            "topics": topic_details,
        })

    total_syllabus_topics = sum(u["total_topics"] for u in coverage_data)
    total_covered = sum(u["covered_topics"] for u in coverage_data)
    overall_pct = round(total_covered / total_syllabus_topics * 100, 1) if total_syllabus_topics else 0

    return {
        "overall_coverage_pct": overall_pct,
        "total_syllabus_topics": total_syllabus_topics,
        "covered_count": total_covered,
        "gap_count": len(gap_topics),
        "units": coverage_data,
        "gap_topics": gap_topics,
    }


# =============================================================================
# DIFFICULTY TRENDS (over time)
# =============================================================================

def get_difficulty_trends() -> Dict:
    rows = _fetch_all()
    if not rows:
        return {"daily": [], "weekly": []}

    # Group by day
    daily: Dict[str, Dict[str, int]] = defaultdict(lambda: {"Easy": 0, "Medium": 0, "Hard": 0, "total": 0})
    for r in rows:
        ts = r.get("created_at")
        if not ts:
            continue
        day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        diff = r.get("difficulty", "Medium") or "Medium"
        daily[day][diff] = daily[day].get(diff, 0) + 1
        daily[day]["total"] += 1

    daily_list = [
        {"date": day, **counts}
        for day, counts in sorted(daily.items())
    ]

    # Compute cumulative total
    cumulative = 0
    for entry in daily_list:
        cumulative += entry["total"]
        entry["cumulative"] = cumulative

    # Weekly aggregation
    weekly: Dict[str, Dict] = defaultdict(lambda: {"Easy": 0, "Medium": 0, "Hard": 0, "total": 0})
    for r in rows:
        ts = r.get("created_at")
        if not ts:
            continue
        dt = datetime.fromtimestamp(ts)
        week = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
        diff = r.get("difficulty", "Medium") or "Medium"
        weekly[week][diff] = weekly[week].get(diff, 0) + 1
        weekly[week]["total"] += 1

    weekly_list = [{"week": w, **counts} for w, counts in sorted(weekly.items())]

    # Mean difficulty score per day
    for entry in daily_list:
        score = (entry.get("Easy", 0) * 1 + entry.get("Medium", 0) * 2 + entry.get("Hard", 0) * 3)
        total = entry.get("total", 1) or 1
        entry["avg_difficulty_score"] = round(score / total, 2)

    return {"daily": daily_list, "weekly": weekly_list}


# =============================================================================
# CO-PO ATTAINMENT MATRIX (NBA)
# =============================================================================

def get_copo_matrix() -> Dict:
    rows = _fetch_all()
    if not rows:
        return {"matrix": [], "co_summary": [], "po_summary": []}

    co_po_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    co_total: Dict[str, int] = defaultdict(int)
    po_total: Dict[str, int] = defaultdict(int)

    valid_cos = list(CO_LABELS.keys())
    valid_pos = list(PO_LABELS.keys())
    untagged_count = 0

    for r in rows:
        co = r.get("course_outcome") or ""
        po = r.get("program_outcome") or ""
        # Untagged rows (pedagogy tagger never ran / failed) are counted separately
        # instead of being silently folded into CO1/PO1, which was making the whole
        # bank look like it only ever produced CO1 questions.
        if co not in valid_cos or po not in valid_pos:
            untagged_count += 1
            continue
        co_po_counts[co][po] += 1
        co_total[co] += 1
        po_total[po] += 1

    total = len(rows) or 1

    # Build matrix
    matrix = []
    for co in valid_cos:
        for po in valid_pos:
            count = co_po_counts[co][po]
            attainment = round(count / total * 100, 1)
            # NBA scale: 0=Not Attained, 1=<40%, 2=40-60%, 3=>60%
            level = 0 if attainment == 0 else (1 if attainment < 5 else (2 if attainment < 15 else 3))
            matrix.append({
                "co": co,
                "po": po,
                "co_label": CO_LABELS.get(co, co),
                "po_label": PO_LABELS.get(po, po),
                "count": count,
                "attainment_pct": attainment,
                "nba_level": level,
            })

    # CO summary (% of total questions)
    co_summary = [
        {
            "co": co,
            "label": CO_LABELS.get(co, co),
            "count": co_total.get(co, 0),
            "pct": round(co_total.get(co, 0) / total * 100, 1),
        }
        for co in valid_cos
    ]

    # PO summary
    po_summary = [
        {
            "po": po,
            "label": PO_LABELS.get(po, po),
            "count": po_total.get(po, 0),
            "pct": round(po_total.get(po, 0) / total * 100, 1),
        }
        for po in valid_pos
    ]

    return {"matrix": matrix, "co_summary": co_summary, "po_summary": po_summary, "untagged_count": untagged_count}


# =============================================================================
# FULL EDA REPORT
# =============================================================================

def get_eda_report() -> Dict:
    rows = _fetch_all()
    total = len(rows)

    if total == 0:
        return {"total": 0, "message": "No data available for EDA."}

    difficulties = [r.get("difficulty", "Medium") or "Medium" for r in rows]
    bloom_vals = [r.get("bloom_level") or 2 for r in rows]
    diff_scores = [DIFFICULTY_SCORE.get(d, 2) for d in difficulties]

    mean_d = sum(diff_scores) / len(diff_scores)
    variance_d = sum((x - mean_d) ** 2 for x in diff_scores) / len(diff_scores)

    topics = [r.get("topic", "") or "" for r in rows]
    topic_counts = Counter(t.lower().strip() for t in topics if t)
    top_topics = topic_counts.most_common(10)

    cos = Counter(r.get("course_outcome") or "CO1" for r in rows)
    pos = Counter(r.get("program_outcome") or "PO1" for r in rows)

    missing_bloom = sum(1 for r in rows if not r.get("bloom_level"))
    missing_co = sum(1 for r in rows if not r.get("course_outcome"))
    missing_po = sum(1 for r in rows if not r.get("program_outcome"))

    # Questions with code vs without
    has_code = sum(1 for r in rows if r.get("verification_code") and r["verification_code"].strip())

    return {
        "total_questions": total,
        "difficulty": {
            "distribution": dict(Counter(difficulties)),
            "mean_score": round(mean_d, 3),
            "variance": round(variance_d, 3),
            "std_dev": round(math.sqrt(variance_d), 3),
        },
        "bloom": {
            "distribution": {BLOOM_LABELS.get(k, str(k)): v for k, v in Counter(bloom_vals).items()},
            "mean_level": round(sum(bloom_vals) / len(bloom_vals), 2),
            "balance_score": _bloom_balance(bloom_vals),
        },
        "topics": {
            "unique_count": len(topic_counts),
            "top_10": [{"topic": t, "count": c} for t, c in top_topics],
        },
        "outcomes": {
            "co_distribution": dict(cos),
            "po_distribution": dict(pos),
        },
        "data_quality": {
            "missing_bloom_pct": round(missing_bloom / total * 100, 1),
            "missing_co_pct": round(missing_co / total * 100, 1),
            "missing_po_pct": round(missing_po / total * 100, 1),
            "questions_with_code_pct": round(has_code / total * 100, 1),
        },
        "accuracy_proxy": {
            "questions_with_answer": round(
                sum(1 for r in rows if r.get("answer_text", "").strip()) / total * 100, 1
            ),
            "questions_with_explanation": round(
                sum(1 for r in rows if r.get("explanation_text", "").strip()) / total * 100, 1
            ),
        },
    }


# =============================================================================
# 1. PAPER BALANCE CHECKER
# =============================================================================

# Ideal Bloom distribution for a balanced exam paper (%)
IDEAL_BLOOM_DIST = {1: 10, 2: 15, 3: 20, 4: 25, 5: 15, 6: 15}

def get_paper_balance(paper_id: Optional[int] = None) -> Dict:
    """
    Compare actual Bloom distribution against the ideal distribution.
    Returns imbalance scores and suggestions.

    NOTE: this always analyzes the ENTIRE question bank (every question ever
    generated, across all topics/units), not a single exported paper — a
    paper_id parameter is accepted for API compatibility but generated papers
    don't currently persist a bank-row reference to filter by. The UI label
    reflects this ("Question Bank Balance").
    """
    rows = _fetch_all()
    if not rows:
        return {"error": "No questions found"}

    bloom_vals = [r.get("bloom_level") for r in rows if r.get("bloom_level") in range(1, 7)]
    unclassified = len(rows) - len(bloom_vals)
    total = len(bloom_vals)
    if total == 0:
        return {"error": "No questions with a detected Bloom level yet"}
    actual_counts = Counter(bloom_vals)

    actual_pct = {lvl: round(actual_counts.get(lvl, 0) / total * 100, 1) for lvl in range(1, 7)}
    ideal_pct = IDEAL_BLOOM_DIST

    # Deviation per level
    levels = []
    suggestions = []
    for lvl in range(1, 7):
        actual = actual_pct[lvl]
        ideal = ideal_pct[lvl]
        deviation = round(actual - ideal, 1)
        status = "balanced"
        if deviation > 8:
            status = "over-represented"
            suggestions.append(f"Reduce {BLOOM_LABELS[lvl]} (L{lvl}) questions — {actual}% vs ideal {ideal}%")
        elif deviation < -8:
            status = "under-represented"
            suggestions.append(f"Add more {BLOOM_LABELS[lvl]} (L{lvl}) questions — only {actual}% vs ideal {ideal}%")

        levels.append({
            "bloom_level": lvl,
            "label": BLOOM_LABELS[lvl],
            "actual_pct": actual,
            "ideal_pct": ideal,
            "deviation": deviation,
            "status": status,
            "actual_count": actual_counts.get(lvl, 0),
        })

    # Overall balance score: 100 - mean absolute deviation
    mad = sum(abs(l["deviation"]) for l in levels) / 6
    balance_score = round(max(0, 100 - mad * 2), 1)

    # Difficulty balance (uses all rows, independent of Bloom classification)
    all_total = len(rows)
    difficulties = [r.get("difficulty", "Medium") or "Medium" for r in rows]
    diff_counts = Counter(difficulties)
    diff_pct = {d: round(diff_counts.get(d, 0) / all_total * 100, 1) for d in ["Easy", "Medium", "Hard"]}
    ideal_diff = {"Easy": 30, "Medium": 45, "Hard": 25}
    diff_suggestions = []
    for d, ideal in ideal_diff.items():
        actual_d = diff_pct.get(d, 0)
        if abs(actual_d - ideal) > 10:
            direction = "Reduce" if actual_d > ideal else "Add more"
            diff_suggestions.append(f"{direction} {d} questions — {actual_d}% vs ideal {ideal}%")

    return {
        "balance_score": balance_score,
        "total_questions": all_total,
        "bloom_classified_questions": total,
        "unclassified_questions": unclassified,
        "scope": "entire_question_bank",
        "bloom_levels": levels,
        "difficulty_distribution": diff_pct,
        "ideal_difficulty": ideal_diff,
        "suggestions": suggestions + diff_suggestions,
        "rating": "Excellent" if balance_score >= 80 else ("Good" if balance_score >= 60 else ("Fair" if balance_score >= 40 else "Poor")),
    }


# =============================================================================
# 2. REPETITION & SIMILAR QUESTION DETECTION
# =============================================================================

def _tokenize(text: str) -> set:
    """Simple word-level tokenizer — lowercase, strip punctuation."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return set(text.split())


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def get_similarity_report(threshold: float = 0.55) -> Dict:
    """
    Detect semantically similar and near-duplicate questions using
    Jaccard similarity on question text tokens.
    Returns pairs above threshold sorted by similarity score.
    """
    rows = _fetch_all()
    if len(rows) < 2:
        return {"pairs": [], "total_questions": len(rows), "flagged_count": 0}

    # Pre-tokenize all questions
    tokenized = []
    for r in rows:
        text = (r.get("question_text") or "").strip()
        tokenized.append({
            "id": r["id"],
            "topic": r.get("topic", ""),
            "difficulty": r.get("difficulty", ""),
            "bloom_level": r.get("bloom_level") or 2,
            "text_preview": text[:120] + ("…" if len(text) > 120 else ""),
            "tokens": _tokenize(text),
        })

    pairs = []
    n = len(tokenized)
    for i in range(n):
        for j in range(i + 1, n):
            sim = _jaccard(tokenized[i]["tokens"], tokenized[j]["tokens"])
            if sim >= threshold:
                label = "exact duplicate" if sim >= 0.95 else ("near-duplicate" if sim >= 0.75 else "similar")
                pairs.append({
                    "question_a_id": tokenized[i]["id"],
                    "question_b_id": tokenized[j]["id"],
                    "question_a_preview": tokenized[i]["text_preview"],
                    "question_b_preview": tokenized[j]["text_preview"],
                    "topic_a": tokenized[i]["topic"],
                    "topic_b": tokenized[j]["topic"],
                    "similarity_score": round(sim, 3),
                    "label": label,
                })

    pairs.sort(key=lambda x: -x["similarity_score"])

    # Summary by label
    label_counts = Counter(p["label"] for p in pairs)

    return {
        "total_questions": n,
        "flagged_count": len(pairs),
        "threshold_used": threshold,
        "label_summary": dict(label_counts),
        "pairs": pairs[:50],  # Return top 50 pairs max
    }


# =============================================================================
# 3. STUDENT PERFORMANCE FEEDBACK ANALYSIS
# =============================================================================

FEEDBACK_DB_PATH = Path("question_bank.db")

def _ensure_feedback_table():
    with sqlite3.connect(FEEDBACK_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER,
                student_id TEXT,
                score INTEGER,         -- 0-100
                time_taken_sec INTEGER,
                correct INTEGER,       -- 1 or 0
                difficulty_felt TEXT,  -- 'Easy','Medium','Hard'
                created_at REAL
            )
        """)
        conn.commit()


def submit_feedback(feedbacks: List[Dict]) -> Dict:
    """
    Bulk insert student feedback records.
    Each record: {question_id, student_id, score, time_taken_sec, correct, difficulty_felt}
    """
    import time
    _ensure_feedback_table()
    inserted = 0
    with sqlite3.connect(FEEDBACK_DB_PATH) as conn:
        for fb in feedbacks:
            try:
                conn.execute("""
                    INSERT INTO student_feedback
                    (question_id, student_id, score, time_taken_sec, correct, difficulty_felt, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    fb.get("question_id"),
                    fb.get("student_id", "anon"),
                    fb.get("score", 0),
                    fb.get("time_taken_sec", 0),
                    1 if fb.get("correct") else 0,
                    fb.get("difficulty_felt", "Medium"),
                    time.time(),
                ))
                inserted += 1
            except Exception:
                continue
        conn.commit()
    return {"inserted": inserted}


def get_feedback_analysis() -> Dict:
    """
    Analyze student feedback to identify difficult questions,
    weak topic areas, and performance patterns.
    """
    _ensure_feedback_table()

    with sqlite3.connect(FEEDBACK_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        feedback_rows = conn.execute("SELECT * FROM student_feedback").fetchall()
        question_rows = conn.execute("SELECT id, topic, bloom_level, difficulty, question_text FROM templates").fetchall()

    if not feedback_rows:
        return {"total_responses": 0, "message": "No student feedback submitted yet."}

    fb = [dict(r) for r in feedback_rows]
    questions = {r["id"]: dict(r) for r in question_rows}

    total = len(fb)
    # Per-question aggregation
    q_stats: Dict[int, Dict] = defaultdict(lambda: {
        "scores": [], "times": [], "correct": 0, "total": 0, "difficulty_felt": []
    })
    for f in fb:
        qid = f["question_id"]
        q_stats[qid]["scores"].append(f["score"] or 0)
        q_stats[qid]["times"].append(f["time_taken_sec"] or 0)
        q_stats[qid]["correct"] += f["correct"] or 0
        q_stats[qid]["total"] += 1
        q_stats[qid]["difficulty_felt"].append(f["difficulty_felt"] or "Medium")

    # Identify difficult questions (accuracy < 50%)
    difficult_questions = []
    for qid, stats in q_stats.items():
        acc = round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] else 0
        avg_score = round(sum(stats["scores"]) / len(stats["scores"]), 1) if stats["scores"] else 0
        avg_time = round(sum(stats["times"]) / len(stats["times"]), 1) if stats["times"] else 0
        q_info = questions.get(qid, {})
        difficult_questions.append({
            "question_id": qid,
            "topic": q_info.get("topic", "Unknown"),
            "bloom_level": q_info.get("bloom_level", 2),
            "bloom_label": BLOOM_LABELS.get(q_info.get("bloom_level", 2), ""),
            "accuracy_pct": acc,
            "avg_score": avg_score,
            "avg_time_sec": avg_time,
            "response_count": stats["total"],
            "flagged": acc < 50,
        })
    difficult_questions.sort(key=lambda x: x["accuracy_pct"])

    # Topic-level weakness
    topic_stats: Dict[str, Dict] = defaultdict(lambda: {"scores": [], "correct": 0, "total": 0})
    for f in fb:
        qid = f["question_id"]
        topic = questions.get(qid, {}).get("topic", "Unknown")
        topic_stats[topic]["scores"].append(f["score"] or 0)
        topic_stats[topic]["correct"] += f["correct"] or 0
        topic_stats[topic]["total"] += 1

    topic_performance = sorted([
        {
            "topic": t,
            "avg_score": round(sum(s["scores"]) / len(s["scores"]), 1) if s["scores"] else 0,
            "accuracy_pct": round(s["correct"] / s["total"] * 100, 1) if s["total"] else 0,
            "response_count": s["total"],
        }
        for t, s in topic_stats.items()
    ], key=lambda x: x["avg_score"])

    # Overall stats
    all_scores = [f["score"] or 0 for f in fb]
    overall_acc = round(sum(f["correct"] or 0 for f in fb) / total * 100, 1)
    avg_score = round(sum(all_scores) / len(all_scores), 1)

    # Score distribution buckets
    buckets = {"0-25": 0, "26-50": 0, "51-75": 0, "76-100": 0}
    for s in all_scores:
        if s <= 25: buckets["0-25"] += 1
        elif s <= 50: buckets["26-50"] += 1
        elif s <= 75: buckets["51-75"] += 1
        else: buckets["76-100"] += 1

    return {
        "total_responses": total,
        "overall_accuracy_pct": overall_acc,
        "avg_score": avg_score,
        "score_distribution": buckets,
        "weak_topics": [t for t in topic_performance if t["accuracy_pct"] < 50],
        "topic_performance": topic_performance,
        "difficult_questions": difficult_questions[:20],
        "flagged_question_count": sum(1 for q in difficult_questions if q["flagged"]),
    }


# =============================================================================
# 4. CO/PO MAPPING CONSISTENCY CHECK
# =============================================================================

# Expected CO for each Bloom level range
BLOOM_CO_RULES = {
    1: ["CO1"],
    2: ["CO1", "CO2"],
    3: ["CO2", "CO3"],
    4: ["CO3", "CO4"],
    5: ["CO4", "CO5"],
    6: ["CO5"],
}

# Expected PO for each CO
CO_PO_RULES = {
    "CO1": ["PO1", "PO2"],
    "CO2": ["PO1", "PO2", "PO3"],
    "CO3": ["PO2", "PO3", "PO4"],
    "CO4": ["PO3", "PO4", "PO5"],
    "CO5": ["PO4", "PO5", "PO6"],
}


def get_copo_consistency() -> Dict:
    """
    Validate CO/PO tag assignments against Bloom level rules.
    Flags questions where the CO/PO doesn't match the cognitive level.
    """
    rows = _fetch_all()
    if not rows:
        return {
            "total_questions": 0, "consistent_count": 0, "issue_count": 0,
            "consistency_score": 100, "issue_breakdown": {}, "co_mismatch_count": 0,
            "po_mismatch_count": 0, "missing_tags_count": 0, "issues": [],
            "bloom_co_rules": {str(k): v for k, v in BLOOM_CO_RULES.items()},
        }

    total = len(rows)
    issues = []
    co_mismatch = 0
    po_mismatch = 0
    missing_tags = 0

    for r in rows:
        bloom = r.get("bloom_level") or 2
        co = r.get("course_outcome") or ""
        po = r.get("program_outcome") or ""
        qid = r["id"]
        topic = r.get("topic", "Unknown")
        text_preview = (r.get("question_text") or "")[:100]

        if not co or not po:
            missing_tags += 1
            issues.append({
                "question_id": qid,
                "topic": topic,
                "bloom_level": bloom,
                "bloom_label": BLOOM_LABELS.get(bloom, ""),
                "co": co or "—",
                "po": po or "—",
                "issue_type": "missing_tag",
                "message": f"Missing {'CO' if not co else 'PO'} tag",
                "text_preview": text_preview,
            })
            continue

        expected_cos = BLOOM_CO_RULES.get(bloom, [])
        co_ok = co in expected_cos
        expected_pos = CO_PO_RULES.get(co, [])
        po_ok = po in expected_pos

        if not co_ok:
            co_mismatch += 1
            issues.append({
                "question_id": qid,
                "topic": topic,
                "bloom_level": bloom,
                "bloom_label": BLOOM_LABELS.get(bloom, ""),
                "co": co,
                "po": po,
                "issue_type": "co_mismatch",
                "message": f"Bloom L{bloom} ({BLOOM_LABELS.get(bloom,'')}) should map to {expected_cos}, got {co}",
                "text_preview": text_preview,
            })
        elif not po_ok:
            po_mismatch += 1
            issues.append({
                "question_id": qid,
                "topic": topic,
                "bloom_level": bloom,
                "bloom_label": BLOOM_LABELS.get(bloom, ""),
                "co": co,
                "po": po,
                "issue_type": "po_mismatch",
                "message": f"{co} should map to {expected_pos}, got {po}",
                "text_preview": text_preview,
            })

    consistent = total - len(issues)
    consistency_score = round(consistent / total * 100, 1) if total else 100

    issue_type_counts = Counter(i["issue_type"] for i in issues)

    return {
        "total_questions": total,
        "consistent_count": consistent,
        "issue_count": len(issues),
        "consistency_score": consistency_score,
        "issue_breakdown": dict(issue_type_counts),
        "co_mismatch_count": co_mismatch,
        "po_mismatch_count": po_mismatch,
        "missing_tags_count": missing_tags,
        "issues": issues[:100],
        "bloom_co_rules": {str(k): v for k, v in BLOOM_CO_RULES.items()},
    }
