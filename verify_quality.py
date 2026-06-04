#!/usr/bin/env python3
"""Quick verification of question and paper generation quality"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.graph_agent import run_agent
from app.services.paper_generator import PaperGeneratorService, PaperTemplate, PaperSection, QuestionSpec
from app.tools.utils import get_logger

logger = get_logger("QualityCheck")

def test_single_question():
    """Test single question generation"""
    print("\n" + "="*60)
    print("TEST 1: Single Question Generation")
    print("="*60)

    result = run_agent("Define entropy in decision trees", "Medium")

    if result and 'question' in result:
        print("\n✅ Question Generated Successfully!")
        print(f"\n📝 Question: {result['question'][:200]}...")
        print(f"\n✓ Answer: {result.get('answer', 'N/A')[:100]}...")
        print(f"\n✓ Type: {result.get('question_type', 'N/A')}")
        print(f"✓ Difficulty: Medium")
        print(f"✓ Source: {result.get('source', 'N/A')}")

        # Check Bloom fields
        if result.get('bloom_level'):
            print(f"✓ Bloom Level: {result['bloom_level']}")
        if result.get('course_outcome'):
            print(f"✓ Course Outcome: {result['course_outcome']}")
        if result.get('program_outcome'):
            print(f"✓ Program Outcome: {result['program_outcome']}")

        return True
    else:
        print("\n❌ Question generation FAILED")
        print(f"Error: {result.get('error', 'Unknown error')}")
        return False

def test_paper_generation():
    """Test paper generation"""
    print("\n" + "="*60)
    print("TEST 2: Paper Generation (2 questions)")
    print("="*60)

    service = PaperGeneratorService()

    # Create a minimal template
    template = PaperTemplate(
        name="Quality Test Paper",
        subject="Machine Learning",
        total_marks=20,
        duration_minutes=60,
        instructions=["Answer all questions"],
        sections=[
            PaperSection(
                name="Section A",
                title="Short Answer",
                instructions="Answer ALL questions",
                questions=[
                    QuestionSpec(
                        topic="Decision Trees",
                        question_type="short",
                        total_marks=10,
                        difficulty="Medium",
                        count=2  # Generate 2 questions
                    )
                ]
            )
        ]
    )

    # Save template
    template_id = service.save_template(template)
    print(f"\n✓ Template created: {template_id}")

    # Generate paper
    try:
        paper = service.generate_paper(template_id, parallel=False)

        print(f"\n✅ Paper Generated Successfully!")
        print(f"\n✓ Paper ID: {paper.id}")
        print(f"✓ Total Questions: {paper.generation_stats['total_questions']}")
        print(f"✓ Successful: {paper.generation_stats['successful']}")
        print(f"✓ Failed: {paper.generation_stats['failed']}")

        # Show first question
        if paper.sections and paper.sections[0]['questions']:
            q1 = paper.sections[0]['questions'][0]
            print(f"\n📝 Sample Question:")
            print(f"   {q1['question_text'][:150]}...")
            print(f"   Answer: {q1['answer'][:100]}...")

        return True
    except Exception as e:
        print(f"\n❌ Paper generation FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🔍 QUALITY VERIFICATION SUITE")
    print("=" * 60)

    # Check if we have prerequisites
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  WARNING: OPENAI_API_KEY not set!")
        print("Set it with: export OPENAI_API_KEY=your_key_here")
        sys.exit(1)

    # Check if we have PDFs ingested
    from pathlib import Path
    chroma_path = Path("chroma_db")
    if not chroma_path.exists():
        print("\n⚠️  WARNING: No PDF database found!")
        print("Please ingest a PDF first:")
        print("  python main.py --ingest /path/to/your/document.pdf")
        sys.exit(1)

    # Run tests
    test1_pass = test_single_question()
    test2_pass = test_paper_generation()

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Single Question: {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Paper Generation: {'✅ PASS' if test2_pass else '❌ FAIL'}")

    if test1_pass and test2_pass:
        print("\n🎉 All quality checks PASSED!")
        print("\nNext Steps:")
        print("  - Check question quality manually")
        print("  - Test with different topics and difficulties")
        print("  - Try web UI at http://localhost:5173")
    else:
        print("\n⚠️  Some tests FAILED - check logs above")

    print("")
