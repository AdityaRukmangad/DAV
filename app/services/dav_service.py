"""
Module: app/services/dav_service.py
Purpose: Data Analytics & Visualization (DAV) service.
Provides EDA, statistical metrics, data cleaning, CO-PO attainment,
syllabus coverage, and Bloom distribution analytics.
"""

import sqlite3
import json
import math
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timedelta

import yaml

DB_PATH = Path("question_bank.db")
SYLLABUS_PATH = Path("config/syllabus.yaml")

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

CO_LABELS = {
    "CO1": "Foundational Knowledge",
    "CO2": "Comprehension & Analysis",
    "CO3": "Application & Design",
    "CO4": "Evaluation & Optimization",
    "CO5": "Innovation & Research",
}

PO_LABELS = {
    "PO1": "Engineering Knowledge",
    "PO2": "Problem Analysis",
    "PO3": "Design Solutions",
    "PO4": "Investigation",
    "PO5": "Modern Tool Usage",
    "PO6": "Ethics & Society",
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
    if not SYLLABUS_PATH.exists():
        return {}
    with open(SYLLABUS_PATH) as f:
        return yaml.safe_load(f) or {}


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

    # Overall distribution
    bloom_counts = Counter(r.get("bloom_level") or 2 for r in rows)
    overall = [
        {
            "bloom_level": lvl,
            "label": BLOOM_LABELS.get(lvl, f"Level {lvl}"),
            "count": bloom_counts.get(lvl, 0),
        }
        for lvl in range(1, 7)
    ]

    # Per-topic breakdown
    topic_bloom: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        topic = (r.get("topic") or "Unknown").lower().strip()
        lvl = r.get("bloom_level") or 2
        topic_bloom[topic][lvl] += 1

    by_topic = {}
    for topic, counter in topic_bloom.items():
        by_topic[topic] = [
            {"bloom_level": lvl, "label": BLOOM_LABELS.get(lvl, f"L{lvl}"), "count": counter.get(lvl, 0)}
            for lvl in range(1, 7)
        ]

    # Difficulty × Bloom heatmap data
    heatmap = []
    for r in rows:
        diff = r.get("difficulty", "Medium") or "Medium"
        lvl = r.get("bloom_level") or 2
        heatmap.append({"difficulty": diff, "bloom_level": lvl})

    heatmap_matrix: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for entry in heatmap:
        heatmap_matrix[entry["difficulty"]][entry["bloom_level"]] += 1

    heatmap_data = []
    for diff in ["Easy", "Medium", "Hard"]:
        for lvl in range(1, 7):
            heatmap_data.append({
                "difficulty": diff,
                "bloom_level": lvl,
                "bloom_label": BLOOM_LABELS.get(lvl, f"L{lvl}"),
                "count": heatmap_matrix[diff][lvl],
            })

    return {"overall": overall, "by_topic": by_topic, "heatmap": heatmap_data}


# =============================================================================
# TOPIC COVERAGE (vs Syllabus)
# =============================================================================

def get_topic_coverage() -> Dict:
    rows = _fetch_all()
    syllabus = _load_syllabus()

    question_topics = Counter((r.get("topic") or "").lower().strip() for r in rows if r.get("topic"))

    units = syllabus.get("units", [])
    coverage_data = []
    gap_topics = []
    covered_topics = []

    for unit in units:
        unit_name = unit.get("name", f"Unit {unit.get('unit', '?')}")
        unit_num = unit.get("unit", 0)
        topics = unit.get("topics", [])
        unit_total = len(topics)
        unit_covered = 0

        topic_details = []
        for t in topics:
            t_lower = t.lower().strip()
            count = question_topics.get(t_lower, 0)
            # Also check partial matches
            if count == 0:
                for qt, qc in question_topics.items():
                    if t_lower in qt or qt in t_lower:
                        count = qc
                        break
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

    for r in rows:
        co = r.get("course_outcome") or "CO1"
        po = r.get("program_outcome") or "PO1"
        if co not in valid_cos:
            co = "CO1"
        if po not in valid_pos:
            po = "PO1"
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

    return {"matrix": matrix, "co_summary": co_summary, "po_summary": po_summary}


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
