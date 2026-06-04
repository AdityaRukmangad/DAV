from app.config.syllabus_loader import get_syllabus_loader

syllabus = get_syllabus_loader()

# Test course info
info = syllabus.get_course_info()
print("Course:", info['name'])
print("Code:", info['code'])
print()

# Test unit matching
test_files = ["AIML_Unit-1.pdf", "AIML_Unit-2.pdf", "AIML_UNIT-3.pdf"]
for filename in test_files:
    unit_num = syllabus.match_unit_for_pdf(filename)
    if unit_num:
        unit = syllabus.get_unit_by_number(unit_num)
        print(f"✓ {filename} → Unit {unit_num}: {unit['unit_name']}")
        topics = syllabus.get_unit_topics(unit_num)
        print(f"  {len(topics)} topics, CO: {syllabus.get_co_mapping(unit_num)}")
    else:
        print(f"✗ {filename} → No match")
    print()
