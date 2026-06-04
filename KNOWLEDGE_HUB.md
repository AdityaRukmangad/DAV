# Knowledge Hub Feature

## Overview
The Knowledge Hub provides complete transparency into the AI question generation system by displaying:
1. **Course Syllabus** - Complete curriculum structure with units, topics, and CO/PO mappings
2. **Previous Year Question Papers** - Historical papers with detailed statistics and pattern analysis

## Backend Implementation

### API Endpoints

#### 1. GET `/api/v1/knowledge-hub/syllabus`
Returns complete course syllabus structure:
```json
{
  "course_info": {
    "name": "Artificial Intelligence and Machine Learning",
    "code": "IS353IA",
    "semester": "V",
    "category": "Professional Core Course"
  },
  "units": [
    {
      "unit_number": 1,
      "unit_name": "Introduction to AI and Search Algorithms",
      "topics": [...],
      "co_mapping": ["CO1", "CO3"]
    }
  ],
  "course_outcomes": [...],
  "co_po_mapping": {...},
  "credits": {...}
}
```

#### 2. GET `/api/v1/knowledge-hub/pyq-papers`
Returns all PYQ papers with statistics:
```json
{
  "papers": [
    {
      "filename": "sample_2024_midterm.json",
      "exam_name": "Midterm Examination 2024",
      "academic_year": "2023-2024",
      "stats": {
        "total_questions": 10,
        "total_marks": 50,
        "unique_cos": 3,
        "type_distribution": {"short": 5, "long": 3, "mcq": 2},
        "difficulty_distribution": {"easy": 4, "medium": 4, "hard": 2},
        "co_distribution": {"CO1": 4, "CO2": 3, "CO3": 3}
      }
    }
  ],
  "patterns_summary": {
    "total_questions": 10,
    "unique_topics": 8
  }
}
```

### Data Sources
- **Syllabus**: `app/config/syllabus.json` - Complete course structure
- **PYQ Papers**: `data/previous_year_papers/*.json` - Historical question papers

## Frontend Implementation

### New Component: `KnowledgeHubModule.tsx`

#### Features
1. **Dual Tab Interface**
   - Syllabus Tab: Shows course structure
   - PYQ Papers Tab: Shows historical papers with statistics

2. **Syllabus Display**
   - Course information card with code, name, semester, credits
   - CO-PO mapping matrix with visual indicators
   - Expandable units (click to expand/collapse)
   - Topics with subtopics and Bloom level tags
   - Color-coded badges for different categories

3. **PYQ Papers Display**
   - Pattern summary card showing total questions, unique topics, papers analyzed
   - Individual paper cards with:
     - Exam name and academic year
     - Total questions, marks, COs covered
     - Question type distribution (short, long, mcq, numerical)
     - Difficulty distribution with visual progress bars
     - CO distribution with color-coded badges

4. **Visual Design**
   - Gradient backgrounds for emphasis
   - Animated transitions and hover effects
   - Responsive grid layouts
   - Color-coded difficulty levels (green=easy, yellow=medium, red=hard)
   - Beautiful card-based interface matching existing design system

### Navigation
- New "Knowledge Hub" tab in main navigation
- Separate from "Upload" tab for better organization
- Shows badge with number of units and papers when available

### Icons Added
- `Target` - For CO-PO mapping
- `Question` (HelpCircle) - For PYQ section
- `Document` (FileCheck) - For syllabus section

## How It Works

### Pattern Learning Flow
1. User uploads PDFs → System vectorizes and stores
2. PYQ papers are placed in `data/previous_year_papers/`
3. System analyzes patterns on startup:
   - Question type distributions
   - Difficulty patterns by marks
   - CO coverage patterns
   - Expected answer lengths
4. Patterns guide question generation (no ML training needed)

### Syllabus Integration Flow
1. Syllabus loaded from `app/config/syllabus.json`
2. PDFs matched to units using filename or content analysis
3. Topics extracted from matched unit
4. LLM suggests topics aligned with unit curriculum
5. Questions generated with proper CO mapping

## Benefits

### For Users
- **Transparency**: See exactly what drives question generation
- **Trust**: Understand the patterns system follows
- **Validation**: Verify syllabus coverage and CO alignment
- **Insights**: View historical paper trends and distributions

### For System
- **Quality Control**: Ensure questions match curriculum
- **Pattern Consistency**: Follow established examination patterns
- **CO Coverage**: Maintain proper outcome distribution
- **Difficulty Balance**: Match historical difficulty trends

## Usage

### Viewing Syllabus
1. Navigate to "Knowledge Hub" tab
2. Click "Syllabus" tab
3. View course info and CO-PO mapping
4. Click on any unit to expand and see topics
5. Topics show subtopics and Bloom levels

### Viewing PYQ Papers
1. Navigate to "Knowledge Hub" tab
2. Click "PYQ Papers" tab
3. View pattern summary at top
4. Scroll through individual paper cards
5. Each card shows complete statistics and distributions

### Adding New PYQ Papers
1. Create JSON file in `data/previous_year_papers/`
2. Follow format of `sample_2024_midterm.json`:
```json
{
  "exam_name": "Your Exam Name",
  "academic_year": "2024-2025",
  "semester": "V",
  "duration_minutes": 90,
  "total_marks": 50,
  "questions": [
    {
      "question_number": 1,
      "marks": 2,
      "question_type": "short",
      "topic": "Your Topic",
      "difficulty": "easy",
      "co_mapping": ["CO1"],
      "expected_answer_length": "2-3 sentences"
    }
  ]
}
```
3. Restart server to reload patterns
4. View in Knowledge Hub

## Statistics Displayed

### Per Paper
- Total questions
- Total marks
- Unique COs covered
- Question type distribution (pie chart style)
- Difficulty distribution (progress bars)
- CO distribution (badges)

### Overall (Pattern Summary)
- Total questions across all papers
- Unique topics identified
- Number of papers analyzed

## Design Consistency
- Uses existing color palette (accent, warm tones)
- Matches animation styles (slide-up, fade-in)
- Follows card-based layout system
- Maintains typography hierarchy
- Responsive grid layouts
- Consistent spacing and borders

## Future Enhancements
- Interactive CO-PO heatmap visualization
- Topic coverage analysis across PDFs
- Export syllabus/statistics as PDF
- Compare multiple PYQ papers side-by-side
- Filter questions by CO/difficulty/type
- Add custom PYQ papers through UI upload
