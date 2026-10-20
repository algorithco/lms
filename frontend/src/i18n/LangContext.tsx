import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { api, getTokens } from '../lib/api';
import data from './translations.json';

export type AppLang = 'uz' | 'ru' | 'en';
export const APP_LANGS: AppLang[] = ['uz', 'ru', 'en'];
const LANG_KEY = 'lms_lang';

// All three dictionaries from translations.json
const dicts: Record<AppLang, Record<string, string>> = {
  uz: (data as { uz: Record<string, string> }).uz,
  ru: (data as { ru: Record<string, string> }).ru,
  en: (data as { en: Record<string, string> }).en,
};

// Frontend-only supplement for keys the backend dictionary lacks.
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
  panel_admin_hero_sub: 'Platforma boshqaruvi — statistika, kontent va foydalanuvchilar bir joyda.',
  panel_attempts_today: 'Bugungi urinishlar',
  panel_attempts_total: 'Jami urinishlar',
  panel_essays_pending: 'Tekshiruv kutilmoqda',
  panel_essays_pending_ai: 'AI baholamoqda',
  panel_essays_awaiting_review: 'Tekshiruv kutilmoqda',
  panel_essays_total: 'Jami esselar',
  panel_new_users: 'Yangi foydalanuvchilar',
  panel_payments_pending: "Kutilayotgan to'lovlar",
  panel_subscriptions: 'Faol obunalar',
  panel_platform: 'Platforma',
  panel_quick_actions: 'Tezkor amallar',
  panel_action_new_test: 'Yangi test',
  panel_action_new_test_hint: 'Test yaratish va savollar qo‘shish',
  panel_action_new_topic: 'Esse mavzusi',
  panel_action_new_topic_hint: 'Mavzu yaratish va parol qo‘yish',
  panel_action_review_essays: 'Esselarni tekshirish',
  panel_action_manage_users: 'Foydalanuvchilar',
  panel_topic_password_set: 'Parolli',
  panel_topic_password_set_hint: 'Bu mavzu parol bilan himoyalangan',
  panel_topic_password_remove: 'Parolni o‘chirish',
  panel_topic_password_remove_confirm: 'Bu mavzudagi parol o‘chirilsinmi?',
  panel_topic_password_keep_hint: "Bo'sh qoldirilsa — joriy parol saqlanadi. O'chirish uchun jadvaldagi tugmani bosing.",
  difficulty_easy: 'Oson',
  difficulty_medium: "O'rtacha",
  difficulty_hard: 'Qiyin',
  tr_edit_text: 'Matnni tahrirlash',
  tr_edit_text_hint: 'Faqat admin matnni o‘zgartira oladi. Ballar o‘zgarmaydi — kerak bo‘lsa qayta baholang.',
  tr_text_saved: 'Matn saqlandi',
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
  take_single_mode: "1 tadan ishlash",
  take_all_mode: "Barcha savollar",
  take_next_q: "Keyingi savol",
  take_prev_q: "Oldingi savol",
  take_hotkey_hint: "Klaviaturadan tezkor foydalanish",
  take_answered_stat: "ta belgilandi",
  take_left_stat: "ta qoldi",
};

const KNOWN_SAFE_FALLBACKS: Record<string, string> = {
  nav_comparison: 'Taqqoslash',
  nav_pricing: 'Tariflar',
  nav_faq: 'FAQ',
  nav_features: 'Imkoniyatlar',
  nav_how: 'Qanday ishlaydi',
  faq_eyebrow: 'SAVOLLAR VA JAVOBLAR',
  faq_title_1: "Ko'p beriladigan",
  faq_title_2: 'savollar',
  pricing_eyebrow: 'HAMYONBOP TARIFLAR',
  pricing_title_1: 'Hamyonbop va qulay',
  pricing_title_2: 'tariflar',
  cmp_eyebrow: 'TAQQOSLASH',
  cmp_title_1: 'Nega aynan',
  cmp_title_2: 'GRAND EDUCATION?',
};

function formatRawKeyFallback(key: string): string {
  if (KNOWN_SAFE_FALLBACKS[key]) return KNOWN_SAFE_FALLBACKS[key];
  const parts = key.split('_');
  if (parts.length > 1) {
    const stripped = ['nav', 'faq', 'cmp', 'pricing', 'plan', 'trust', 'feature', 'stats', 'foot', 'cta'].includes(parts[0])
      ? parts.slice(1).join(' ')
      : parts.join(' ');
    return stripped.charAt(0).toUpperCase() + stripped.slice(1);
  }
  return key;
}

export function translate(key: string, lang: AppLang, fallback?: string): string {
  const val = dicts[lang]?.[key] ?? extraUz[key] ?? dicts.uz[key];
  if (val && typeof val === 'string' && val.trim().length > 0) {
    return val;
  }
  if (fallback !== undefined && fallback !== null && fallback.trim().length > 0) {
    return fallback;
  }
  return formatRawKeyFallback(key);
}

function readStoredLang(): AppLang {
  try {
    const v = localStorage.getItem(LANG_KEY);
    if (v === 'ru' || v === 'en' || v === 'uz') return v;
    // Strictly default to 'uz' (Uzbek) on first visit and persist
    localStorage.setItem(LANG_KEY, 'uz');
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

export interface LangState {
  t: (key: string, fallback?: string) => string;
  lang: AppLang;
  setLang: (lang: AppLang) => void;
}

const Ctx = createContext<LangState | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<AppLang>(readStoredLang);
  const langRef = useRef(lang);
  langRef.current = lang;

  const t = useCallback(
    (key: string, fallback?: string) => translate(key, langRef.current, fallback),
    [],
  );

  // Update document.documentElement.lang when language changes
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

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