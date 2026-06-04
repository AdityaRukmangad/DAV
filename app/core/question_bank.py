"""
Module: app/core/question_bank.py
Purpose: Single source of truth for the database.
Fixed: Auto-migrates old database schemas to prevent 'No item with that key' errors.
"""
import sqlite3
import json
import time
from typing import Optional, Dict, Any
from pathlib import Path

DB_PATH = Path("question_bank.db")

def init_db():
    """
    Initialize DB and perform auto-migration if columns are missing.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # 1. Create Table if it doesn't exist
        c.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                difficulty TEXT,
                question_text TEXT,
                answer_text TEXT,
                explanation_text TEXT,
                verification_code TEXT,
                source_type TEXT,
                source_urls TEXT,
                full_json TEXT,
                created_at REAL
            )
        ''')

        # 2. Auto-Migration: Check for missing columns in existing DBs
        c.execute("PRAGMA table_info(templates)")
        existing_columns = [col[1] for col in c.fetchall()]

        # Define required new columns
        required_columns = {
            'answer_text': 'TEXT',
            'explanation_text': 'TEXT',
            'source_urls': 'TEXT',
            'full_json': 'TEXT',
            # STEP 2: Bloom-Adaptive RAG columns
            'bloom_level': 'INTEGER',
            'retrieved_chunk_ids': 'TEXT',
            'retrieved_doc_ids': 'TEXT',
            # STEP 3: Pedagogy Tagger columns
            'course_outcome': 'TEXT',
            'program_outcome': 'TEXT'
        }

        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                print(f"🔧 Migrating Database: Adding missing column '{col_name}'...")
                try:
                    c.execute(f"ALTER TABLE templates ADD COLUMN {col_name} {col_type}")
                except Exception as e:
                    print(f"Migration warning: {e}")

        conn.commit()

def save_template(topic: str, difficulty: str, question_text: str, code: str, source: str, full_data: Dict = None, source_urls: list = None) -> Optional[int]:
    """
    Save a question template to the database.

    Returns:
        The ID of the inserted question, or None if save failed
    """
    init_db()

    answer = full_data.get('answer', '') if full_data else ''
    explanation = full_data.get('explanation', '') if full_data else ''
    json_str = json.dumps(full_data) if full_data else '{}'
    urls_str = json.dumps(source_urls) if source_urls else '[]'

    # STEP 2 & 3: Extract new fields from full_data
    bloom_level = full_data.get('bloom_level') if full_data else None
    chunk_ids_str = json.dumps(full_data.get('retrieved_chunk_ids', [])) if full_data else '[]'
    doc_ids_str = json.dumps(full_data.get('retrieved_doc_ids', [])) if full_data else '[]'
    course_outcome = full_data.get('course_outcome') if full_data else None
    program_outcome = full_data.get('program_outcome') if full_data else None

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO templates
               (topic, difficulty, question_text, answer_text, explanation_text, verification_code, source_type, source_urls, full_json, created_at,
                bloom_level, retrieved_chunk_ids, retrieved_doc_ids, course_outcome, program_outcome)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (topic.lower(), difficulty, question_text, answer, explanation, code, source, urls_str, json_str, time.time(),
             bloom_level, chunk_ids_str, doc_ids_str, course_outcome, program_outcome)
        )
        question_id = c.lastrowid
        conn.commit()
        return question_id

def get_existing_template(topic: str, difficulty: str) -> Optional[Dict[str, Any]]:
    init_db()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT * FROM templates WHERE topic = ? AND difficulty = ? ORDER BY RANDOM() LIMIT 1",
            (topic.lower(), difficulty)
        )
        row = c.fetchone()

    if row:
        # Helper to safely get column or return empty string if DB is weird
        def get_safe(key):
            try:
                return row[key]
            except (IndexError, KeyError):
                return ""

        base = {
            "id": row['id'],  # Include database ID for tracking
            "cache_id": str(row['id']),  # String version for set operations
            "question_text": get_safe('question_text'),
            "python_code": get_safe('verification_code'),
            "answer": get_safe('answer_text'),
            "explanation": get_safe('explanation_text')
        }

        # Try to restore full rich structure
        json_data = get_safe('full_json')
        if json_data:
            try:
                extra = json.loads(json_data)
                base.update(extra)
                # Ensure ID is preserved even if json has it
                base['id'] = row['id']
                base['cache_id'] = str(row['id'])
            except:
                pass
        return base

    return None


def find_similar_questions(topic: str, difficulty: str = None, limit: int = 5) -> list:
    """
    Find similar questions in the bank using fuzzy topic matching.
    Returns list of matching questions sorted by relevance.
    """
    init_db()

    topic_lower = topic.lower()
    topic_words = set(topic_lower.split())

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get all questions (we'll filter in Python for fuzzy matching)
        if difficulty:
            c.execute("SELECT * FROM templates WHERE difficulty = ?", (difficulty,))
        else:
            c.execute("SELECT * FROM templates")

        rows = c.fetchall()

    results = []
    for row in rows:
        try:
            row_topic = row['topic'].lower() if row['topic'] else ''
            row_words = set(row_topic.split())

            # Calculate similarity score
            # Exact match
            if row_topic == topic_lower:
                score = 1.0
            # Word overlap (Jaccard similarity)
            elif topic_words and row_words:
                intersection = len(topic_words & row_words)
                union = len(topic_words | row_words)
                score = intersection / union if union > 0 else 0
            else:
                score = 0

            # Partial substring match bonus
            if topic_lower in row_topic or row_topic in topic_lower:
                score = max(score, 0.7)

            if score > 0.3:  # Threshold for similarity
                base = {
                    "id": row['id'],  # Include database ID for tracking
                    "cache_id": str(row['id']),  # String version for set operations
                    "topic": row['topic'],
                    "difficulty": row['difficulty'],
                    "question_text": row['question_text'] or "",
                    "python_code": row['verification_code'] or "",
                    "answer": row['answer_text'] or "",
                    "explanation": row['explanation_text'] or "",
                    "similarity_score": score
                }

                # Try to restore full structure
                json_data = row['full_json']
                if json_data:
                    try:
                        extra = json.loads(json_data)
                        base.update(extra)
                        # Ensure ID and score are preserved
                        base['id'] = row['id']
                        base['cache_id'] = str(row['id'])
                        base['similarity_score'] = score
                    except:
                        pass

                results.append(base)
        except Exception:
            continue

    # Sort by similarity score descending
    results.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
    return results[:limit]


def check_duplicate(topic: str, difficulty: str, threshold: float = 0.8) -> Optional[Dict[str, Any]]:
    """
    Check if a highly similar question already exists.
    Returns the existing question if similarity >= threshold, else None.
    """
    similar = find_similar_questions(topic, difficulty, limit=1)
    if similar and similar[0].get('similarity_score', 0) >= threshold:
        return similar[0]
    return None


def get_question_count(topic: str = None) -> int:
    """Get count of questions in bank, optionally filtered by topic."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        if topic:
            c.execute("SELECT COUNT(*) FROM templates WHERE topic LIKE ?", (f"%{topic.lower()}%",))
        else:
            c.execute("SELECT COUNT(*) FROM templates")
        return c.fetchone()[0]


init_db()