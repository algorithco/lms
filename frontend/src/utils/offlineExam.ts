/**
 * Offline-First & PWA Exam Engine (frontend/src/utils/offlineExam.ts).
 *
 * Provides robust offline persistence using browser IndexedDB (with LocalStorage fallback)
 * to ensure that internet dropouts in rural/regional areas never disrupt test taking.
 */

const DB_NAME = 'grandec_exam_offline_db';
const DB_VERSION = 1;
const STORE_EXAMS = 'cached_exams';
const STORE_ANSWERS = 'offline_answers';

export interface OfflineAnswerRecord {
  id: string; // `${attemptId}_${questionId}`
  attemptId: number | string;
  questionId: number | string;
  choice_ids?: number[];
  text_answer?: string;
  gap_answers?: Record<string, string>;
  matching?: Record<string, number | null>;
  written_text?: string;
  updatedAt: number;
  synced: boolean;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      return reject(new Error('IndexedDB not supported'));
    }

    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_EXAMS)) {
        db.createObjectStore(STORE_EXAMS, { keyPath: 'attemptId' });
      }
      if (!db.objectStoreNames.contains(STORE_ANSWERS)) {
        const answerStore = db.createObjectStore(STORE_ANSWERS, { keyPath: 'id' });
        answerStore.createIndex('attemptId', 'attemptId', { unique: false });
        answerStore.createIndex('synced', 'synced', { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/** Cache full test payload for offline viewing. */
export async function cacheExamData(attemptId: number | string, examData: unknown): Promise<void> {
  const normId = String(attemptId);
  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_EXAMS, 'readwrite');
      const store = tx.objectStore(STORE_EXAMS);
      const putReq = store.put({ attemptId: normId, data: examData, savedAt: Date.now() });
      putReq.onsuccess = () => resolve();
      putReq.onerror = () => reject(putReq.error);
    });
  } catch {
    try {
      localStorage.setItem(`offline_exam_${normId}`, JSON.stringify(examData));
    } catch {
      /* quota */
    }
  }
}

/** Retrieve cached test payload if network is down. */
export async function getCachedExamData<T = unknown>(attemptId: number | string): Promise<T | null> {
  const normId = String(attemptId);
  try {
    const db = await openDatabase();
    return new Promise((resolve) => {
      const tx = db.transaction(STORE_EXAMS, 'readonly');
      const store = tx.objectStore(STORE_EXAMS);
      const getReq = store.get(normId);
      getReq.onsuccess = () => {
        if (getReq.result?.data) {
          resolve(getReq.result.data as T);
        } else {
          resolve(null);
        }
      };
      getReq.onerror = () => resolve(null);
    });
  } catch {
    try {
      const raw = localStorage.getItem(`offline_exam_${normId}`);
      return raw ? (JSON.parse(raw) as T) : null;
    } catch {
      return null;
    }
  }
}

/** Store student answer locally in IndexedDB. */
export async function saveAnswerOffline(
  attemptId: number | string,
  questionId: number | string,
  answerPayload: {
    choice_ids?: number[];
    text_answer?: string;
    gap_answers?: Record<string, string>;
    matching?: Record<string, number | null>;
    written_text?: string;
  },
): Promise<void> {
  const normAttempt = String(attemptId);
  const normQuestion = String(questionId);
  const record: OfflineAnswerRecord = {
    id: `${normAttempt}_${normQuestion}`,
    attemptId: normAttempt,
    questionId: normQuestion,
    ...answerPayload,
    updatedAt: Date.now(),
    synced: false,
  };

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_ANSWERS, 'readwrite');
      const store = tx.objectStore(STORE_ANSWERS);
      const putReq = store.put(record);
      putReq.onsuccess = () => resolve();
      putReq.onerror = () => reject(putReq.error);
    });
  } catch {
    try {
      const key = `offline_answers_${normAttempt}`;
      const existing = JSON.parse(localStorage.getItem(key) || '{}');
      existing[normQuestion] = record;
      localStorage.setItem(key, JSON.stringify(existing));
    } catch {
      /* localstorage quota */
    }
  }
}

/** Retrieve all unsynced answers for a given attempt. */
export async function getUnsyncedAnswers(attemptId: number | string): Promise<OfflineAnswerRecord[]> {
  const normAttempt = String(attemptId);
  try {
    const db = await openDatabase();
    return new Promise((resolve) => {
      const tx = db.transaction(STORE_ANSWERS, 'readonly');
      const store = tx.objectStore(STORE_ANSWERS);
      const index = store.index('attemptId');
      const request = index.getAll(normAttempt);

      request.onsuccess = () => {
        const results = (request.result as OfflineAnswerRecord[]) || [];
        resolve(results.filter((r) => !r.synced));
      };
      request.onerror = () => resolve([]);
    });
  } catch {
    try {
      const key = `offline_answers_${normAttempt}`;
      const existing = JSON.parse(localStorage.getItem(key) || '{}');
      return Object.values(existing).filter((r: any) => !r.synced) as OfflineAnswerRecord[];
    } catch {
      return [];
    }
  }
}

/** Mark answers as synced after server batch acknowledgment. */
export async function markAnswersSynced(
  attemptId: number | string,
  questionIds: (number | string)[],
): Promise<void> {
  const normAttempt = String(attemptId);
  const idsToMark = new Set(questionIds.map((qid) => `${normAttempt}_${qid}`));
  try {
    const db = await openDatabase();
    return new Promise((resolve) => {
      const tx = db.transaction(STORE_ANSWERS, 'readwrite');
      const store = tx.objectStore(STORE_ANSWERS);
      const index = store.index('attemptId');
      const request = index.getAll(normAttempt);

      request.onsuccess = () => {
        const records = (request.result as OfflineAnswerRecord[]) || [];
        for (const rec of records) {
          if (idsToMark.has(rec.id)) {
            rec.synced = true;
            store.put(rec);
          }
        }
        resolve();
      };
      request.onerror = () => resolve();
    });
  } catch {
    try {
      const key = `offline_answers_${normAttempt}`;
      const existing = JSON.parse(localStorage.getItem(key) || '{}');
      for (const qid of questionIds) {
        if (existing[qid]) {
          existing[qid].synced = true;
        }
      }
      localStorage.setItem(key, JSON.stringify(existing));
    } catch {
      /* ignore */
    }
  }
}

/** Push all pending offline answers to /api/tests/save-batch/ */
export async function syncOfflineBatch(
  attemptId: number | string,
  jwtToken?: string,
): Promise<{ success: boolean; syncedCount: number }> {
  const normAttempt = String(attemptId);
  const pending = await getUnsyncedAnswers(normAttempt);
  if (!pending.length) {
    return { success: true, syncedCount: 0 };
  }

  const payload = {
    attempt_id: Number(normAttempt) || normAttempt,
    answers: pending.map((p) => ({
      question_id: Number(p.questionId) || p.questionId,
      choice_ids: p.choice_ids || [],
      text_answer: p.text_answer || '',
      gap_answers: p.gap_answers || {},
      matching: p.matching || {},
      written_text: p.written_text,
    })),
  };

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (jwtToken) {
    headers['Authorization'] = `Bearer ${jwtToken}`;
  }

  try {
    const res = await fetch(`/api/tests/attempts/${normAttempt}/save-batch/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      // Try global route fallback
      const fallbackRes = await fetch('/api/tests/save-batch/', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });
      if (!fallbackRes.ok) return { success: false, syncedCount: 0 };
    }

    const qIds = pending.map((p) => p.questionId);
    await markAnswersSynced(normAttempt, qIds);
    return { success: true, syncedCount: pending.length };
  } catch {
    return { success: false, syncedCount: 0 };
  }
}
