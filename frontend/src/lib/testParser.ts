/**
 * Smart Paste Test Parser for GRANDEC LMS.
 * High-precision parsing of tests copied from Word, PDF, or Telegram.
 * Supports:
 *  - Question prefixes: 1., 1), 1 -, 1-savol, Savol 1:, №1, or digits
 *  - Choices: A), B), C), D) or A., B., C., D. or A - or (A) or [A]
 *  - Inline multiple choices on the same line: "A) Olma  B) Anor  C) Behi  D) Uzum"
 *  - Correct answer indicators: *A), +B), A) *matn, A) matn*, Javob: B, Ans: C, Answer: D, Kalitlar: 1.A 2.B, 1-A 2-B
 */

export interface ParsedChoice {
  code: string; // A, B, C, D, E
  text: string;
}

export interface ParsedQuestion {
  order: number;
  qNum: number;
  text: string;
  choices: ParsedChoice[];
  correctAnswer: string | null; // e.g. 'A', 'B'
  hasExplicitAnswer: boolean;
  explanation: string;
}

export interface SmartParseResult {
  title: string;
  readingPassage: string;
  questions: ParsedQuestion[];
  unansweredCount: number;
}

export type SupportedSubject = 'uzbek' | 'adabiyot' | 'milliy' | 'english';

export function parseSmartTestText(rawText: string, defaultSubject: SupportedSubject = 'uzbek'): SmartParseResult {
  const text = (rawText || '').trim();
  if (!text) {
    return {
      title: '',
      readingPassage: '',
      questions: [],
      unansweredCount: 0,
    };
  }

  const lines = text.split(/\r?\n/);
  const globalKeys: Record<number, string> = {};
  const bodyLines: string[] = [];

  // 1. Check for global answer table (e.g., "Javoblar: 1-A, 2-B, 3-C" or "Kalitlar: 1.A 2.B" or "1-A 2-B 3-C")
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (
      /(?:javoblar|kalitlar|keys|answers)\s*:/i.test(line) ||
      /^(\s*\d+\s*[:.\-)?\s]\s*[a-eA-E]\s*[,;]?\s*){2,}$/.test(line)
    ) {
      const pairRegex = /(\d+)\s*[:.\-)?\s]\s*([a-eA-E])\b/g;
      let m: RegExpExecArray | null;
      while ((m = pairRegex.exec(line)) !== null) {
        globalKeys[Number(m[1])] = m[2].toUpperCase();
      }
    } else {
      bodyLines.push(rawLine);
    }
  }

  // Regex patterns
  // Matches: 1. or 1) or 1 - or Savol 1: or 1-savol: or №1
  const qStartRe = /^(?:(?:savol\s*|№\s*)?(\d+)[\.\)\-:\s]+|(\d+)\s*[-–—]?\s*savol[\.\):]?\s*)(.*)$/i;

  // Matches choices: A), A., A -, (A), [A], *A), +A)
  const inlineChoiceRe = /(?:^|\s+)([\*\+]?)\s*(?:\(|\[)?\s*([A-Ea-e])\s*(?:\)|\.|\-|\])\s*(.*?)(?=(?:\s+[\*\+]?\s*(?:\(|\[)?\s*[A-Ea-e]\s*(?:\)|\.|\-|\]))|$)/g;

  // Matches inline answer: Javob: A, To'g'ri javob: B, Ans: C, Answer: D, Kalit: A
  const inlineAnsRe = /^(?:(?:to['ʼ`]?g['ʼ`]?ri\s+)?(?:javob|kalit|key)|ans(?:wer)?)\s*[:=\-]\s*([A-Ea-e])\b/i;

  const questions: ParsedQuestion[] = [];
  let currQ: ParsedQuestion | null = null;
  let readingPassage = '';

  for (const rawLine of bodyLines) {
    const line = rawLine.trim();
    if (!line) continue;

    // Check for inline answer statement
    const ansMatch = line.match(inlineAnsRe);
    if (ansMatch && currQ) {
      currQ.correctAnswer = ansMatch[1].toUpperCase();
      currQ.hasExplicitAnswer = true;
      continue;
    }

    // Check if line starts a choice (e.g. A) or (A) or *A))
    const isChoiceStart = /^[\*\+]?\s*(?:\(|\[)?\s*[A-Ea-e]\s*(?:\)|\.|\-|\])/.test(line);
    const qMatch = line.match(qStartRe);

    if (qMatch && !isChoiceStart) {
      const qNum = Number(qMatch[1] || qMatch[2]);
      let rest = (qMatch[3] || '').trim();
      rest = rest.replace(/^(?:savol|question)[\.\):\-]?\s*/i, '').trim();

      currQ = {
        order: questions.length + 1,
        qNum: qNum || questions.length + 1,
        text: rest || `${qNum || questions.length + 1}-savol`,
        choices: [],
        correctAnswer: null,
        hasExplicitAnswer: false,
        explanation: '',
      };
      questions.push(currQ);
      continue;
    }

    // Check for choice matches (single or multiple on same line)
    const choiceMatches: { star: string; code: string; text: string }[] = [];
    let cm: RegExpExecArray | null;
    inlineChoiceRe.lastIndex = 0;

    while ((cm = inlineChoiceRe.exec(line)) !== null) {
      choiceMatches.push({
        star: cm[1],
        code: cm[2].toUpperCase(),
        text: cm[3].trim(),
      });
    }

    if (choiceMatches.length > 0 && currQ) {
      for (const item of choiceMatches) {
        let cText = item.text;
        if (/[\*\+\(\)]+$/.test(cText)) {
          cText = cText.replace(/[\*\+\(\)]+$/, '').trim();
          currQ.correctAnswer = item.code;
          currQ.hasExplicitAnswer = true;
        } else if (/^[\*\+]/.test(cText)) {
          cText = cText.replace(/^[\*\+]+/, '').trim();
          currQ.correctAnswer = item.code;
          currQ.hasExplicitAnswer = true;
        } else if (item.star === '*' || item.star === '+') {
          currQ.correctAnswer = item.code;
          currQ.hasExplicitAnswer = true;
        }

        currQ.choices.push({
          code: item.code,
          text: cText,
        });
      }
      continue;
    }

    // Continuation of question text or reading passage
    if (currQ && currQ.choices.length === 0) {
      currQ.text += ' ' + line;
    } else if (!currQ && line.length > 35) {
      readingPassage += (readingPassage ? ' ' : '') + line;
    }
  }

  // Post-process global keys and ensure fallback choices
  let unanswered = 0;
  for (const q of questions) {
    if (!q.hasExplicitAnswer && globalKeys[q.qNum]) {
      q.correctAnswer = globalKeys[q.qNum];
      q.hasExplicitAnswer = true;
    }

    // Standardize choices if fewer than 2
    if (q.choices.length === 0) {
      q.choices = [
        { code: 'A', text: 'A varianti' },
        { code: 'B', text: 'B varianti' },
        { code: 'C', text: 'C varianti' },
        { code: 'D', text: 'D varianti' },
      ];
    } else {
      q.choices.sort((a, b) => a.code.localeCompare(b.code));
    }

    if (!q.correctAnswer) {
      unanswered++;
    }
  }

  let subjectLabel = 'Ona tili va adabiyot';
  if (defaultSubject === 'english') {
    subjectLabel = 'English CBT Mock';
  } else if (defaultSubject === 'adabiyot') {
    subjectLabel = 'Adabiyot oraliq nazorat';
  } else if (defaultSubject === 'milliy') {
    subjectLabel = 'Milliy Sertifikat Diagnostika';
  }

  const defaultTitle = `${subjectLabel} — ${questions.length} talik test`;

  return {
    title: defaultTitle,
    readingPassage: readingPassage.trim(),
    questions,
    unansweredCount: unanswered,
  };
}
