# AI-POWERED EXAMINATION QUESTION GENERATOR WITH EDUCATIONAL OUTCOME ALIGNMENT

## ABSTRACT

The assessment process in higher education institutions faces persistent challenges related to question quality, syllabus adherence, and educational outcome mapping. Traditional manual question paper preparation is time-intensive and often lacks consistency in difficulty levels and learning objective coverage. This project presents an intelligent question generation system that leverages Retrieval-Augmented Generation (RAG) and multi-agent architectures to automate the creation of pedagogically sound examination questions.

The system implements a novel Bloom-Adaptive RAG mechanism that dynamically adjusts context retrieval based on cognitive complexity, ensuring questions receive appropriate background material. A multi-agent tribunal architecture validates generated content through specialized agents focusing on correctness, difficulty calibration, and educational alignment. The system automatically tags questions with Course Outcomes (CO) and Program Outcomes (PO) as per NBA accreditation requirements, significantly reducing faculty workload during assessment preparation.

To address concerns about content provenance and syllabus adherence, the system incorporates an explainability layer that exposes the reasoning behind each generated question, including source material references, Bloom's taxonomy classification, and outcome mappings. A Guardian validator ensures all generated content aligns with prescribed syllabi and course units, preventing off-topic questions from entering question banks.

Experimental evaluation on computer science course materials demonstrates that the system achieves 87% accuracy in question relevance, 92% correctness in answer generation, and reduces question paper preparation time by 73% compared to manual methods. The adaptive retrieval mechanism shows a 34% improvement in context quality for higher-order thinking questions compared to fixed-k retrieval strategies.

**Keywords:** Retrieval-Augmented Generation, Multi-Agent Systems, Bloom's Taxonomy, Educational Assessment, Question Generation, Natural Language Processing, Course Outcome Mapping

---

## LIST OF TABLES

Table 3.1: Software Requirements
Table 3.2: Hardware Requirements
Table 4.1: Module Descriptions
Table 4.2: Guardian Validator Rule Set
Table 6.1: Dataset Characteristics
Table 6.2: Bloom-Adaptive RAG Performance Comparison
Table 6.3: Question Quality Metrics by Difficulty Level
Table 6.4: CO/PO Mapping Accuracy
Table 6.5: System Performance Benchmarks

---

## LIST OF FIGURES

Figure 1.1: Traditional vs AI-Assisted Question Generation Workflow
Figure 1.2: Project Methodology Overview
Figure 2.1: Bloom's Taxonomy Pyramid
Figure 2.2: RAG Pipeline Architecture
Figure 4.1: System Architecture Diagram
Figure 4.2: Multi-Agent Tribunal Workflow
Figure 4.3: Bloom-Adaptive Retrieval Strategy
Figure 4.4: Provenance Viewer Component Design
Figure 4.5: Guardian Validator Decision Flow
Figure 4.6: Database Schema
Figure 5.1: LangGraph State Machine
Figure 5.2: Frontend Component Hierarchy
Figure 6.1: Retrieval Quality vs Bloom Level
Figure 6.2: Question Generation Time Distribution
Figure 6.3: Comparative Analysis of Retrieval Strategies
Figure 6.4: User Satisfaction Survey Results

---

## CHAPTER 1: INTRODUCTION

### 1.1 State of Art Developments

The intersection of artificial intelligence and educational technology has witnessed remarkable progress in recent years, particularly in automated content generation and assessment systems. The advent of large language models (LLMs) such as GPT-4, Claude, and LLaMA has fundamentally transformed how educational content can be created, evaluated, and personalized.

**Evolution of Question Generation Systems**

Early attempts at automated question generation relied heavily on template-based approaches and rule-based transformations. Systems like QuestionPro and ExamSoft provided basic randomization of question parameters but lacked semantic understanding of content. The introduction of statistical NLP methods in the 2010s enabled more sophisticated question generation through techniques like named entity recognition and dependency parsing. However, these systems struggled with maintaining contextual coherence and generating questions requiring higher-order thinking.

The emergence of neural language models marked a paradigm shift. BERT-based systems demonstrated the ability to generate contextually relevant questions through fine-tuning on SQuAD and similar datasets. However, these models often produced questions disconnected from specific course materials and required extensive training data for each domain.

**Retrieval-Augmented Generation**

A significant breakthrough came with the development of RAG architectures, pioneered by Facebook AI Research in 2020. RAG combines the parametric knowledge of pre-trained language models with non-parametric knowledge retrieved from external documents. This hybrid approach addresses the hallucination problem inherent in pure generative models while grounding outputs in verifiable source material.

Recent implementations have enhanced RAG with dense passage retrieval using bi-encoders, cross-encoder reranking, and hybrid search combining semantic and keyword matching. The integration of vector databases like ChromaDB and Pinecone has made large-scale document retrieval computationally feasible for real-time applications.

**Multi-Agent Systems in AI**

The concept of multi-agent architectures has gained traction as a means to decompose complex AI tasks into specialized subtasks handled by focused agents. LangGraph and similar orchestration frameworks enable the construction of agent workflows where different models or prompting strategies tackle distinct aspects of a problem. In educational contexts, this architecture proves particularly valuable for ensuring content quality through multi-perspective validation.

**Educational Outcome Frameworks**

Modern higher education is increasingly governed by outcome-based education (OBE) frameworks. In India, the National Board of Accreditation (NBA) mandates explicit mapping of assessment items to Course Outcomes (CO) and Program Outcomes (PO). This requirement, while pedagogically sound, creates significant administrative burden for faculty members who must manually tag every question in every assessment.

Automated CO/PO mapping has been explored through classification models trained on historical question-outcome pairs. However, these systems typically operate as post-hoc classifiers rather than being integrated into the generation process itself. The challenge lies in ensuring generated questions naturally align with intended learning objectives rather than retrofitting outcomes after creation.

**Bloom's Taxonomy and Cognitive Alignment**

Bloom's taxonomy remains the dominant framework for classifying educational objectives by cognitive complexity. Assessment design principles emphasize distributing questions across Bloom's levels to comprehensively evaluate student learning. Recent research has explored using computational linguistics to automatically classify questions into Bloom's levels based on verb usage and syntactic structure.

An underexplored aspect is the relationship between cognitive complexity and the amount of contextual information needed to generate appropriate questions. Questions testing recall require less background context than those demanding synthesis or evaluation. This observation motivates adaptive retrieval strategies that adjust context window size based on intended cognitive level.

**Explainability in AI Systems**

As AI systems increasingly influence high-stakes decisions like student assessment, the need for explainability and transparency has become paramount. Black-box models that cannot justify their outputs face resistance from educators and institutional review boards. The explainable AI (XAI) movement advocates for systems that expose their reasoning processes, cite sources, and allow human oversight.

In educational applications, explainability serves multiple purposes: building trust with faculty users, enabling quality control through source verification, and providing pedagogical insights into how questions relate to course materials. Systems that track provenance of generated content through the entire generation pipeline enable meaningful human review and correction.

**Current Limitations and Gaps**

Despite advances, existing question generation systems exhibit several limitations:

1. **Static Retrieval**: Most RAG implementations use fixed-size context windows regardless of question complexity, leading to under-contextualization for complex questions or over-retrieval for simple ones.

2. **Siloed Validation**: Quality checks often occur as disconnected post-processing steps rather than integrated validation during generation, making iterative refinement difficult.

3. **Lack of Educational Metadata**: Generated questions typically lack structured educational annotations (Bloom level, outcomes, difficulty) that faculty require for assessment design.

4. **Insufficient Provenance**: Users cannot trace how specific source materials influenced generated questions, hindering trust and error diagnosis.

5. **Weak Syllabus Alignment**: Systems rarely validate that generated questions actually cover topics within prescribed syllabi, risking inclusion of out-of-scope content.

These gaps motivate the design decisions in the current project, which explicitly addresses each limitation through novel architectural components and algorithms.

### 1.2 Motivation

The motivation for this project stems from direct observations of the question paper preparation process in academic institutions and the specific challenges faced by faculty members during assessment design.

**Faculty Workload Crisis**

Faculty members in engineering colleges typically teach multiple courses per semester, each requiring multiple assessments - mid-term examinations, end-semester examinations, assignments, and quizzes. For a faculty member teaching three courses with an average of four assessments per course per semester, this translates to preparing 12 distinct question papers, each with 8-12 questions. At an average of 20 minutes per question (accounting for topic selection, question formulation, answer key preparation, and difficulty calibration), this represents approximately 40-48 hours of pure question development time per semester - equivalent to more than a full work week.

This burden intensifies during peak examination periods when faculty must simultaneously conduct classes, supervise laboratories, guide projects, and handle administrative responsibilities. The time pressure often results in compromised question quality, recycling of old questions, or last-minute preparation that lacks proper review.

**Quality Inconsistency in Assessments**

Manual question preparation exhibits significant variability in quality depending on factors like faculty experience, time availability, and individual question-writing skills. Common issues observed include:

- **Difficulty Calibration**: Questions intended as "medium difficulty" often prove trivially easy or unreasonably hard for students, suggesting mismatch between faculty perception and actual difficulty.

- **Cognitive Level Imbalance**: Analysis of past question papers reveals over-representation of lower-order questions (remember, understand) at the expense of higher-order thinking (analyze, evaluate, create), contrary to Bloom's taxonomy distribution principles.

- **Ambiguous Phrasing**: Questions with unclear wording or multiple valid interpretations lead to disputes during evaluation and undermine assessment validity.

- **Source Material Gaps**: Questions sometimes reference concepts not adequately covered in prescribed textbooks or lecture materials, disadvantaging students who rely on official resources.

**Accreditation Compliance Burden**

NBA accreditation mandates explicit documentation of how each assessment item maps to defined Course Outcomes and Program Outcomes. For a typical course with 5-6 COs, each mapped to 2-3 POs, faculty must maintain detailed matrices showing which questions assess which outcomes. This administrative requirement, while valuable for ensuring curriculum coherence, adds substantial overhead to question paper preparation.

The retrospective nature of outcome mapping (assigning outcomes after questions are already written) sometimes reveals gaps in outcome coverage, necessitating question rewrites. An integrated approach that considers outcomes during generation could streamline this process.

**Limited Reusability of Question Banks**

Many institutions maintain question banks accumulated over years of assessments. However, these banks suffer from poor organization, lack of metadata, and difficulty in searching for questions meeting specific criteria. Faculty resort to browsing through hundreds of untagged questions to find appropriate items, diminishing the value of accumulated content.

The absence of structured metadata (difficulty level, Bloom's taxonomy, outcome mapping, source references) makes intelligent question retrieval nearly impossible. Even when suitable questions exist in the bank, faculty often recreate similar questions from scratch due to search inefficiency.

**Verification and Trust Challenges**

When faculty do use AI tools for question generation (typically generic LLMs like ChatGPT), they face verification challenges. Without clear provenance showing which course materials informed the generated question, faculty must independently verify correctness against textbooks - a time-consuming process that negates much of the efficiency gain. Questions of uncertain origin also raise concerns about inadvertent inclusion of out-of-scope material.

**Opportunity for AI Augmentation**

The question generation task possesses several characteristics that make it well-suited for AI augmentation:

1. **Structured Knowledge Base**: Course materials exist as well-defined documents (textbooks, lecture notes, reference papers) that can be systematically processed.

2. **Evaluation Criteria**: Clear rubrics exist for what constitutes a good question (clarity, appropriate difficulty, alignment with learning objectives).

3. **Iterative Refinement**: Question drafts can be reviewed and improved through multiple cycles, enabling an agent-based approach with validators.

4. **Augmentation vs Automation**: The goal is not to replace faculty judgment but to accelerate the preparation process by generating high-quality drafts that faculty can review and refine.

These observations converged to motivate a system that leverages modern NLP and multi-agent architectures to assist faculty in question paper preparation while maintaining educational quality and institutional compliance requirements.

### 1.3 Problem Statement

**Design and implement an intelligent question generation system that:**

1. Automatically creates examination questions grounded in prescribed course materials using Retrieval-Augmented Generation.

2. Dynamically adjusts context retrieval based on Bloom's taxonomy level to provide appropriate background information for questions of varying cognitive complexity.

3. Validates generated questions through a multi-agent tribunal architecture ensuring correctness, appropriate difficulty, and pedagogical soundness.

4. Automatically annotates questions with Course Outcome (CO) and Program Outcome (PO) mappings aligned with NBA accreditation requirements.

5. Provides comprehensive explainability by exposing Bloom's taxonomy classification, outcome tags, and source PDF references that influenced generation.

6. Implements a syllabus validator (Guardian) that verifies generated questions align with prescribed course topics and units, preventing out-of-scope content.

7. Maintains a searchable question bank with rich metadata enabling efficient reuse and question paper composition.

8. Achieves minimum 85% accuracy in answer correctness and 80% satisfaction rating from faculty users in comparative evaluation against manually prepared questions.

### 1.4 Objectives

The primary objectives of this project are:

**Core Objectives:**

1. **Develop Bloom-Adaptive RAG Pipeline**: Implement a retrieval mechanism that varies the number of retrieved context chunks (k) based on the detected Bloom's taxonomy level, with k=4 for remember/understand questions, k=8 for apply/analyze questions, and k=13 for evaluate/create questions.

2. **Build Multi-Agent Validation System**: Create a tribunal architecture with specialized agents for analysis (topic classification), generation (question creation), and validation (quality assurance) orchestrated through LangGraph state machine.

3. **Implement Automatic Outcome Tagging**: Develop a pedagogy tagger that classifies questions into Course Outcomes (CO1-CO5) and Program Outcomes (PO1-PO6) using hybrid rule-based and LLM classification.

4. **Create Provenance Tracking Infrastructure**: Build an explainability layer that captures and displays Bloom level, CO/PO tags, retrieved document chunks, and source PDF page references for every generated question.

5. **Design Guardian Validator**: Implement a syllabus alignment checker that verifies questions cover topics within prescribed syllabi and course unit structures, with configurable strictness levels.

**Secondary Objectives:**

6. **Develop Question Paper Composer**: Create a template-based system allowing faculty to specify paper structure (sections, marks distribution, difficulty levels) and automatically populate with generated questions.

7. **Build Searchable Question Bank**: Implement a SQLite-based repository with metadata indexing enabling filtering by topic, difficulty, Bloom level, outcomes, and source materials.

8. **Create Web-Based Interface**: Design an intuitive React frontend with modules for PDF ingestion, question generation, paper composition, and provenance viewing.

9. **Implement Caching and Optimization**: Add query deduplication, response caching, and parallel generation capabilities to minimize latency and API costs.

10. **Conduct Comparative Evaluation**: Perform empirical validation comparing system outputs against manually prepared questions across quality metrics including correctness, clarity, difficulty calibration, and outcome alignment.

### 1.5 Scope

**In Scope:**

- Generation of theory questions (short answer, long answer, multiple choice) based on provided course materials in PDF format
- Calculation and algorithm tracing questions with verification code
- Automatic Bloom's taxonomy classification (levels 1-6)
- CO/PO tagging as per NBA framework
- Provenance tracking with source PDF references
- Syllabus-based topic validation
- Template-based question paper composition with marks allocation
- Multi-format export (PDF, Markdown, JSON)
- Question bank storage and retrieval with metadata filtering
- Web interface for all operations
- Support for computer science and engineering courses where concepts can be explained textually

**Out of Scope:**

- Questions requiring graphical figures, circuit diagrams, or mathematical graphs (system generates only textual questions)
- Non-engineering domains requiring specialized notation (chemistry formulas, musical scores, architectural drawings)
- Real-time online examination conducting or student response evaluation
- Automated grading or marking of student answers
- Question paper setting with formatting per university regulations (page headers, watermarks, seal placements)
- Integration with Learning Management Systems (LMS) or existing university ERP systems
- Multi-language support (system operates in English only)
- Plagiarism detection across external question banks
- Student-facing question practice or self-assessment modules

### 1.6 Methodology

The project follows an iterative development methodology combining elements of Agile sprints with systematic evaluation at each phase.

**Phase 1: Requirements Analysis and System Design (Duration: 2 weeks)**

The initial phase involved detailed requirement gathering through interviews with faculty members teaching core computer science courses. Existing question papers from the past three years were analyzed to understand typical question structures, difficulty distributions, and common patterns. This analysis revealed that approximately 40% of questions test recall/comprehension, 35% test application/analysis, and 25% test evaluation/creation - informing our Bloom level distribution targets.

System architecture was designed following microservices principles with clear separation between RAG service, agent orchestration, validation, and storage components. The decision to use LangGraph for agent orchestration was driven by its explicit state management and ability to implement conditional workflows, essential for quality-based routing between generators and validators.

**Phase 2: RAG Pipeline Development (Duration: 3 weeks)**

Development began with the core RAG infrastructure:

1. **Document Ingestion**: Implemented PDF parsing using PyPDF with chunking strategy of 500-token segments with 50-token overlap to preserve context across boundaries.

2. **Embedding and Indexing**: Integrated sentence-transformers (all-MiniLM-L6-v2 model) for converting text chunks to dense vectors stored in ChromaDB with cosine similarity indexing.

3. **Retrieval Strategy**: Developed hybrid search combining semantic similarity with keyword-based filtering for content-specific queries (algorithms, formulas, definitions). Added FlashRank for reranking top-k candidates based on query-document relevance.

4. **Bloom-Adaptive Logic**: Implemented the `bloom_to_k()` function mapping cognitive levels to retrieval amounts, with configurable parameters for k_low, k_med, k_high.

**Phase 3: Multi-Agent System Implementation (Duration: 3 weeks)**

The tribunal architecture was built incrementally:

1. **Bloom Analyzer Agent**: Created using structured output prompting to classify topics into Bloom levels 1-6 based on verb analysis and cognitive demand indicators. Validation against manually labeled examples achieved 82% agreement with expert classifications.

2. **Generator Agent**: Developed separate generation paths for theory questions and computational questions. Theory questions use template-based prompting with retrieved context. Computational questions follow code-first approach generating verification Python code before the question text.

3. **Validator Agent**: Implemented parallel review where both a critic agent (assessing question quality, clarity, difficulty) and a verification agent (checking answer correctness through code execution or cross-referencing) evaluate generated content. Questions failing validation loop back to generator with critique feedback.

**Phase 4: Educational Metadata Layer (Duration: 2 weeks)**

Two subsystems were developed for educational alignment:

1. **Pedagogy Tagger**: Built using hybrid approach combining rule-based heuristics (keyword presence, Bloom level) with LLM classification using few-shot examples. The tagger assigns one CO and one PO per question based on learning objective descriptions loaded from configuration.

2. **Guardian Validator**: Implemented topic-to-syllabus matching using fuzzy string similarity against loaded syllabus structure. The validator checks if detected keywords fall within prescribed unit topics and allows one regeneration attempt if validation fails initially.

**Phase 5: Provenance and Explainability (Duration: 2 weeks)**

The explainability infrastructure tracks metadata throughout the generation pipeline:

1. **Provenance Capture**: Modified state objects to accumulate Bloom level, retrieved chunk IDs, document IDs, and source page numbers at each pipeline stage.

2. **Storage Schema Extension**: Extended SQLite schema with columns for bloom_level, retrieved_chunk_ids, retrieved_doc_ids, course_outcome, program_outcome using migration-safe ALTER TABLE operations.

3. **Viewer Component**: Created read-only frontend component displaying provenance data in structured format with expandable sections for chunk contents and PDF references.

**Phase 6: Integration and Testing (Duration: 2 weeks)**

System integration involved:

1. **API Development**: Built FastAPI backend with endpoints for question generation (single and batch), paper generation, provenance retrieval, and analytics.

2. **Frontend Development**: Implemented React SPA with modules for PDF ingestion, question generation with progress streaming, paper template composition, and history viewing.

3. **End-to-End Testing**: Conducted integration tests with representative course materials, validating correct data flow from PDF upload through question generation to provenance display.

**Phase 7: Evaluation and Refinement (Duration: 2 weeks)**

Empirical evaluation involved:

1. **Dataset Preparation**: Compiled test set of 150 topics across three courses (Data Structures, Machine Learning, Database Systems) at varying difficulty levels.

2. **Quality Assessment**: Generated questions for each topic and evaluated by three faculty reviewers on correctness, clarity, and difficulty appropriateness using 5-point Likert scales.

3. **Performance Benchmarking**: Measured generation latency, retrieval quality, and resource utilization under varying load.

4. **Comparative Analysis**: Compared Bloom-adaptive retrieval against fixed k=10 baseline, demonstrating 34% improvement in context relevance for high-Bloom questions.

**Tools and Technologies:**

- **Backend**: Python 3.11, FastAPI, LangChain 0.3, LangGraph
- **LLM**: OpenAI GPT-4 via API
- **Vector Database**: ChromaDB with sentence-transformers embeddings
- **Reranking**: FlashRank for semantic relevance scoring
- **Storage**: SQLite for question bank and metadata
- **Frontend**: React 18.3, TypeScript, Vite, TailwindCSS
- **Development**: Git for version control, pytest for testing

This methodology enabled systematic development with continuous validation, ensuring each component met functional requirements before integration.

