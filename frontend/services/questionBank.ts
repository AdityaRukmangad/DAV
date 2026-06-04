import { saveQuestionToBank } from '../services/questionBank';

export interface SaveQuestionPayload {
  question_text: string;
  marks: number;
  difficulty: string;
  bloom_level: string;
  co: string;
  unit_number: number;
  unit_name: string;
  topic?: string;
  type?: string;
  answer?: string;
  explanation?: string;
  source_filename?: string;
  source_pages?: (number | string)[];
  question_id?: number;
  computed_answer?: string;
}

export const saveQuestionToBank = (question: SaveQuestionPayload) => {
  try {
    const stored = localStorage.getItem('question_bank');
    const bank = stored ? JSON.parse(stored) : {};

    if (!bank[question.unit_number]) {
      bank[question.unit_number] = {
        unit_name: question.unit_name,
        questions: [],
      };
    }

    const newQuestion = {
      ...question,
      id: `q-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      generated_at: new Date().toISOString(),
    };

    bank[question.unit_number].questions.push(newQuestion);
    localStorage.setItem('question_bank', JSON.stringify(bank));
    
    return newQuestion;
  } catch (error) {
    console.error('Failed to save question:', error);
    return null;
  }
};

export const saveQuestionsToBank = (questions: SaveQuestionPayload[]) => {
  questions.forEach(saveQuestionToBank);
};