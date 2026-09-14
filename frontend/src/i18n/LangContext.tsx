import { createContext, useCallback, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import { api, getTokens } from '../lib/api';
import data from './translations.json';

export type AppLang = 'uz' | 'ru' | 'en';
export const APP_LANGS: AppLang[] = ['uz', 'ru', 'en'];
const LANG_KEY = 'lms_lang';

// Uzbek is the only shipped dictionary — ru/en fall back to uz strings until
// their dictionaries land. The lang state itself is fully wired: persisted
// locally, synced to the profile (PATCH /api/auth/me/), and therefore honored
// by backend emails and locale-aware views.
const dict = (data as { uz: Record<string, string> }).uz;

// Frontend-only supplement for keys the backend dictionary lacks.
// Professional Uzbek copy in the same tone as the backend strings.
const extraUz: Record<string, string> = {
  an_passed_count: "O'tganlar",
  an_platform_growth: "Platforma o'sishi",
  arena_quick_match: "Tezkor o'yin",
  arena_quick_hint:
    "Reytingingizga mos raqib topiladi. Raqib topilmasa AI bilan o'ynaysiz.",
  arena_find_match: 'Raqib topish',
  arena_find_match_button: "O'yinni boshlash",
  arena_create_room: 'Xona yaratish',
  arena_create: 'Yaratish',
  arena_enter_code: 'Xona kodi',
  arena_join: "Qo'shilish",
  arena_my_stats: 'Mening statistikam',
  arena_leaderboard: 'Reyting',
  arena_waiting: 'Raqib kutilmoqda',
  arena_wait_hint: 'Ulanmoqda...',
  arena_starting: 'Tayyorlaning',
  arena_session_needed: 'Arena uchun qayta kiring',
  arena_ws_error: 'Ulanishda xatolik yuz berdi',
  arena_login_needed: 'Davom etish uchun tizimga kiring',
  arena_game_over: "O'yin yakunlandi",
  import_file: 'CSV fayl',
  import_no_file: 'CSV faylni tanlang',
  import_only_csv: 'Faqat CSV fayllar qabul qilinadi',
  import_too_big: "Fayl hajmi 5 MB dan oshmasligi kerak",
  panel_choice: 'Variant',
  panel_description: 'Tavsif',
  panel_edit_test: 'Testni tahrirlash',
  panel_pass_pct: "O'tish foizi (%)",
  panel_test_list: "Testlar ro'yxati",
  // Dedicated Telegram Mini App copy (old tma/index.html parity, uz-only).
  tma_home: 'Bosh sahifa',
  tma_essays_tab: 'Esselar',
  tma_essays_title: 'Esse mavzulari',
  tma_no_tests: 'Hali testlar yo‘q',
  tma_no_results: 'Hali natijalar yo‘q',
  tma_no_topics: 'Hali esse mavzulari yo‘q',
  tma_stats_essays: 'Esselar',
  tma_stats_passed: 'O‘tilgan',
  tma_stats_certs: 'Sertifikatlar',
  tma_info_questions: 'Savollar',
  tma_info_minutes: 'Daqiqa',
  tma_info_pass: 'O‘tish',
  tma_remaining: 'Qolgan vaqt',
  tma_begin: 'Testni boshlash',
  tma_retry: 'Qayta topshirish',
  tma_back_home: 'Bosh sahifa',
  tma_back: 'Orqaga',
  tma_cancel: 'Bekor qilish',
  tma_grading: 'Baholanmoqda...',
  tma_empty_essay: 'Esse matni bo‘sh!',
  tma_criteria: '12 mezon bahosi',
  tma_enter_password: 'Parolni kiriting',
  tma_checking: 'Tekshirilmoqda...',
  tma_open_in_telegram: 'Telegram ichida oching.',
  tma_network_error: 'Tarmoq xatoligi',
  tma_loading_error: 'Yuklashda xatolik',
  tma_percent: 'Foiz',
  tma_correct: 'To‘g‘ri javob',
  tma_exit_test: 'Testdan chiqmoqchimisiz? Javoblar saqlanadi.',
  tma_exit_essay: 'Esse yozishni to‘xtatmoqchimisiz?',
  tma_words: 'so‘z',
  tma_new: 'Yangi',
  tma_write_hint: 'Essingizni yozing...',
};

export function translate(key: string): string {
  return extraUz[key] ?? dict[key] ?? key;
}

function readStoredLang(): AppLang {
  try {
    const v = localStorage.getItem(LANG_KEY);
    if (v === 'ru' || v === 'en' || v === 'uz') return v;
  } catch {
    /* ignore */
  }
  return 'uz';
}

/** Persist locally so the next visit (and logged-out pages) keep the choice. */
export function storeLang(lang: AppLang): void {
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch {
    /* ignore */
  }
}

interface LangState {
  t: (key: string) => string;
  lang: AppLang;
  setLang: (lang: AppLang) => void;
}

const Ctx = createContext<LangState | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<AppLang>(readStoredLang);
  const t = useCallback((key: string) => translate(key), []);

  const setLang = useCallback(
    (next: AppLang) => {
      setLangState(next);
      storeLang(next);
      // Sync to profile so backend emails / locale views honor the choice.
      if (!getTokens().access && !getTokens().refresh) return;
      void api('/api/auth/me/', {
        method: 'PATCH',
        body: JSON.stringify({ language: next }),
      }).catch(() => undefined);
    },
    [],
  );

  return <Ctx.Provider value={{ t, lang, setLang }}>{children}</Ctx.Provider>;
}

export function useLang(): LangState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useLang must be used inside <LangProvider>');
  return ctx;
}
