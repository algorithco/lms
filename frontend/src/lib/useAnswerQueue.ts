import { useCallback, useEffect, useRef, useState } from 'react';

export interface SavePayload {
  question_id: number;
  choice_ids?: number[];
  text_answer?: string;
  written_text?: string;
}

export type SaveState = 'saved' | 'saving' | 'offline' | 'error';

const readQueue = (key: string): Record<number, SavePayload> => {
  try {
    return JSON.parse(localStorage.getItem(key) || '{}') as Record<number, SavePayload>;
  } catch {
    return {};
  }
};

/**
 * Answers go to the server one at a time, latest value per question wins. A failed or offline
 * save stays in a queue that is kept in localStorage, retried when the connection returns and
 * every few seconds, so a dropped connection or a reload never loses an answer.
 */
export function useAnswerQueue(attemptId: string, send: (payload: SavePayload) => Promise<unknown>) {
  const key = `cd-queue:${attemptId}`;
  const queue = useRef<Record<number, SavePayload>>(readQueue(key));
  const [initial] = useState(() => ({ ...queue.current }));
  const [state, setState] = useState<SaveState>(Object.keys(queue.current).length ? 'saving' : 'saved');
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine);
  const [justRestored, setJustRestored] = useState(false);
  const flushing = useRef(false);

  const persist = useCallback(() => {
    try {
      if (Object.keys(queue.current).length) localStorage.setItem(key, JSON.stringify(queue.current));
      else localStorage.removeItem(key);
    } catch {
      /* storage can be unavailable; the queue still works in memory */
    }
  }, [key]);

  const flush = useCallback(async (): Promise<boolean> => {
    if (flushing.current) return Object.keys(queue.current).length === 0;
    flushing.current = true;
    try {
      for (;;) {
        const entry = Object.entries(queue.current)[0];
        if (!entry) break;
        const [qid, payload] = entry;
        try {
          await send(payload);
        } catch {
          setState(navigator.onLine ? 'error' : 'offline');
          return false;
        }
        // Only drop it if nothing newer was queued for the same question meanwhile.
        if (queue.current[Number(qid)] === payload) delete queue.current[Number(qid)];
        persist();
      }
      setState('saved');
      return true;
    } finally {
      flushing.current = false;
    }
  }, [send, persist]);

  const enqueue = useCallback(
    (payload: SavePayload) => {
      queue.current[payload.question_id] = payload;
      persist();
      setState(navigator.onLine ? 'saving' : 'offline');
      void flush();
    },
    [flush, persist],
  );

  useEffect(() => {
    const goOnline = () => {
      setOnline(true);
      setJustRestored(true);
      void flush().then((ok) => ok && window.setTimeout(() => setJustRestored(false), 3000));
    };
    const goOffline = () => {
      setOnline(false);
      setState('offline');
    };
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    const timer = window.setInterval(() => {
      if (Object.keys(queue.current).length) void flush();
    }, 8000);
    if (Object.keys(queue.current).length) void flush(); // answers left over from before a reload
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
      window.clearInterval(timer);
    };
  }, [flush]);

  return {
    enqueue,
    flush,
    state,
    online,
    justRestored,
    initial,
    pending: () => Object.keys(queue.current).length,
  };
}
