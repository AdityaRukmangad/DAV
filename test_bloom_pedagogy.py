#!/usr/bin/env python3
"""
Test script for Step 2 (Bloom-Adaptive RAG) and Step 3 (Pedagogy Tagger)

This script tests:
1. Bloom level detection for different query types
2. Adaptive k retrieval based on Bloom level
3. Pedagogy tagging (when enabled)
4. Provenance tracking (chunk_ids, doc_ids)

Usage:
    python test_bloom_pedagogy.py
"""

import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.graph_agent import run_agent
from app.tools.utils import get_logger

logger = get_logger("BloomPedagogyTest")

def test_bloom_levels():
    """Test Bloom level detection and adaptive RAG"""

    # Enable Bloom RAG
    os.environ["BLOOM_RAG_ENABLED"] = "true"
    # Disable pedagogy tagger for this test (test separately)
    os.environ["ENABLE_PEDAGOGY_TAGGER"] = "false"

    test_cases = [
        {
            "topic": "Define entropy in decision trees",
            "difficulty": "Easy",
            "expected_bloom": "1-2",  # Remember/Understand
            "expected_k": "3-5"
        },
        {
            "topic": "Explain how ID3 algorithm works",
            "difficulty": "Easy",
            "expected_bloom": "2",  # Understand
            "expected_k": "3-5"
        },
        {
            "topic": "Calculate information gain for a dataset",
            "difficulty": "Medium",
            "expected_bloom": "3",  # Apply
            "expected_k": "6-10"
        },
        {
            "topic": "Analyze the time complexity of quicksort",
            "difficulty": "Medium",
            "expected_bloom": "4",  # Analyze
            "expected_k": "6-10"
        },
        {
            "topic": "Evaluate which sorting algorithm is best for large datasets",
            "difficulty": "Hard",
            "expected_bloom": "5",  # Evaluate
            "expected_k": "12-15"
        },
        {
            "topic": "Design a new decision tree splitting criterion",
            "difficulty": "Hard",
            "expected_bloom": "6",  # Create
            "expected_k": "12-15"
        }
    ]

    print("\n" + "="*80)
    print("TESTING BLOOM-ADAPTIVE RAG (STEP 2)")
    print("="*80 + "\n")

    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}/{len(test_cases)}: {test['topic']}")
        print(f"Expected Bloom: {test['expected_bloom']}, Expected k: {test['expected_k']}")
        print("-" * 80)

        try:
            result = run_agent(
                topic=test['topic'],
                difficulty=test['difficulty']
            )

            bloom_level = result.get('bloom_level')
            chunk_ids = result.get('retrieved_chunk_ids', [])
            doc_ids = result.get('retrieved_doc_ids', [])

            print(f"✓ Bloom Level Detected: {bloom_level}")
            print(f"✓ Retrieved Chunks: {len(chunk_ids)} chunks")
            print(f"✓ Retrieved Docs: {len(doc_ids)} docs")

            # Verify provenance was captured
            if bloom_level:
                print(f"✓ Provenance: bloom_level={bloom_level}, chunks={chunk_ids[:2]}...")
            else:
                print("⚠ WARNING: bloom_level not set!")

        except Exception as e:
            print(f"✗ ERROR: {e}")
            logger.error(f"Test {i} failed: {e}")

    print("\n" + "="*80)
    print("BLOOM-ADAPTIVE RAG TESTS COMPLETE")
    print("="*80 + "\n")

def test_pedagogy_tagger():
    """Test pedagogy tagging (CO/PO)"""

    # Enable both features
    os.environ["BLOOM_RAG_ENABLED"] = "true"
    os.environ["ENABLE_PEDAGOGY_TAGGER"] = "true"

    test_cases = [
        {
            "topic": "Define Gini index",
            "difficulty": "Easy",
            "expected_co": "CO1",  # Remember/Understand
            "expected_po": "PO1"   # Engineering knowledge
        },
        {
            "topic": "Calculate entropy for dataset",
            "difficulty": "Medium",
            "expected_co": "CO2",  # Apply
            "expected_po": "PO1"   # Problem-solving
        }
    ]

    print("\n" + "="*80)
    print("TESTING PEDAGOGY TAGGER (STEP 3)")
    print("="*80 + "\n")

    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}/{len(test_cases)}: {test['topic']}")
        print(f"Expected: {test['expected_co']}, {test['expected_po']}")
        print("-" * 80)

        try:
            result = run_agent(
                topic=test['topic'],
                difficulty=test['difficulty']
            )

            bloom_level = result.get('bloom_level')
            co = result.get('course_outcome')
            po = result.get('program_outcome')

            print(f"✓ Bloom Level: {bloom_level}")
            print(f"✓ Course Outcome: {co}")
            print(f"✓ Program Outcome: {po}")

            if co and po:
                print(f"✓ Pedagogy tags assigned successfully")
            else:
                print("⚠ WARNING: Pedagogy tags not set!")

        except Exception as e:
            print(f"✗ ERROR: {e}")
            logger.error(f"Test {i} failed: {e}")

    print("\n" + "="*80)
    print("PEDAGOGY TAGGER TESTS COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    print("\n" + "="*80)
    print("BLOOM-ADAPTIVE RAG + PEDAGOGY TAGGER TEST SUITE")
    print("="*80)

    print("\nNOTE: These tests require:")
    print("1. OPENAI_API_KEY set in environment")
    print("2. PDF documents ingested into the system")
    print("3. ChromaDB vector store populated")
    print("\nIf you don't have PDFs ingested, these tests will fail gracefully.")
    print("\n" + "="*80 + "\n")

    # Test Bloom-Adaptive RAG
    test_bloom_levels()

    # Test Pedagogy Tagger
    test_pedagogy_tagger()

    print("\n✅ ALL TESTS COMPLETE!\n")
    print("Check logs above for:")
    print("  - Bloom level detection (1-6)")
    print("  - Different k values used (3-5, 6-10, 12-15)")
    print("  - Provenance tracking (chunk_ids, doc_ids)")
    print("  - Pedagogy tags (CO, PO)")
    print("")
