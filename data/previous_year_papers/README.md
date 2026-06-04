# Previous Year Question Papers

This directory stores previous year question papers for pattern analysis.

## Format

Create JSON files with this structure:

```json
{
  "exam_name": "Mid-Term Examination",
  "academic_year": "2024-2025",
  "semester": "V",
  "course_code": "IS353IA",
  "total_marks": 50,
  "questions": [
    {
      "question_number": 1,
      "section": "Section A",
      "question_type": "short",
      "marks": 2,
      "difficulty": "Easy",
      "topic": "Intelligent Agents",
      "co_mapping": ["CO1"],
      "bloom_level": "Understand",
      "question_text": "Define rational agent.",
      "expected_answer_length": "2-3 sentences"
    }
  ]
}
```

## Usage

The system will:
1. Analyze patterns across multiple years
2. Learn typical question complexity for each marks value
3. Match CO-PO patterns from previous papers
4. Generate questions following similar structure
