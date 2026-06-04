#!/usr/bin/env python3
"""
Database Management Utility
Allows clearing the question bank database entirely or by topic.
"""

import os
import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "question_bank.db"

def clear_database():
    """Delete the question bank database."""
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"✅ Successfully deleted {DB_PATH}")
        print("The database will be recreated on next question generation.")
    else:
        print(f"⚠️  Database not found at {DB_PATH}")

def clear_specific_topic(topic: str):
    """Delete questions for a specific topic."""
    if not DB_PATH.exists():
        print(f"⚠️  Database not found at {DB_PATH}")
        return

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM templates WHERE topic = ?", (topic.lower(),))
        count = c.fetchone()[0]

        if count == 0:
            print(f"⚠️  No questions found for topic: {topic}")
            return

        c.execute("DELETE FROM templates WHERE topic = ?", (topic.lower(),))
        conn.commit()
        print(f"✅ Deleted {count} question(s) for topic: {topic}")

def list_topics():
    """List all topics in the database."""
    if not DB_PATH.exists():
        print(f"⚠️  Database not found at {DB_PATH}")
        return

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT topic, difficulty, COUNT(*) as count FROM templates GROUP BY topic, difficulty")
        results = c.fetchall()

        if not results:
            print("⚠️  Database is empty")
            return

        print("\n📊 Questions in database:")
        print("-" * 60)
        for topic, difficulty, count in results:
            print(f"  {topic} ({difficulty}): {count} question(s)")
        print("-" * 60)

if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        # No arguments - clear entire database
        print("⚠️  This will delete the entire question bank database.")
        response = input("Are you sure? (yes/no): ")
        if response.lower() == 'yes':
            clear_database()
        else:
            print("❌ Cancelled")
    elif sys.argv[1] == "list":
        list_topics()
    elif sys.argv[1] == "topic" and len(sys.argv) > 2:
        topic_name = " ".join(sys.argv[2:])
        clear_specific_topic(topic_name)
    else:
        print("Usage:")
        print("  python clear_database.py          # Clear entire database (with confirmation)")
        print("  python clear_database.py list     # List all topics")
        print("  python clear_database.py topic <topic_name>   # Clear specific topic")
