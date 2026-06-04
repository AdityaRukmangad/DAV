from app.config.pyq_analyzer import get_pyq_analyzer

analyzer = get_pyq_analyzer()

print("=== Previous Year Question Pattern Analysis ===\n")
print(f"Total Papers Analyzed: {analyzer.patterns['total_papers']}")
print(f"Total Questions: {analyzer.patterns['total_questions']}\n")

# Test pattern retrieval for 2-mark short questions
print("=== Pattern for 2-mark Short Answer Question (CO1, Easy) ===")
hints = analyzer.get_generation_hints(marks=2, question_type='short', co='CO1', difficulty='Easy')
print(f"Expected Length: {hints['expected_length']}")
print(f"Typical Difficulty: {hints['typical_difficulty']}")
print(f"Has PYQ Data: {hints['has_pyq_data']}")
print("\nStyle Notes:")
for note in hints['style_notes']:
    print(f"  - {note}")

print("\n=== Pattern for 5-mark Long Answer Question (CO2, Medium) ===")
hints = analyzer.get_generation_hints(marks=5, question_type='long', co='CO2', difficulty='Medium')
print(f"Expected Length: {hints['expected_length']}")
print(f"Typical Difficulty: {hints['typical_difficulty']}")
print("\nStyle Notes:")
for note in hints['style_notes']:
    print(f"  - {note}")

print("\n=== Marks Distribution by CO ===")
for co, data in analyzer.patterns['by_co'].items():
    print(f"\n{co}:")
    print(f"  Question Types: {dict(data['question_types'])}")
    print(f"  Marks Distribution: {dict(data['marks_distribution'])}")
