import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { apiFetch } from '../lib/api';

interface ExerciseQuiz {
  id: number;
  word: string;
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
}

interface ExerciseSpelling {
  id: number;
  word: string;
  prompt: string;
  hint_pattern: string;
  scrambled_letters: string[];
  correct_word: string;
}

interface ExerciseTranslation {
  id: number;
  word?: string;
  uzbek_word?: string;
  options: string[];
  correct_answer: string;
}

interface GeneratedExercises {
  format_1_quiz: ExerciseQuiz[];
  format_2_spelling: ExerciseSpelling[];
  format_3_eng_uzb: ExerciseTranslation[];
  format_4_uzb_eng: ExerciseTranslation[];
}

export default function TeacherVocabGenerator() {
  const [title, setTitle] = useState('Unit 1: Advanced Vocabulary Practice');
  const [rawText, setRawText] = useState(
    'resilient\npersistent\nubiquitous\nscrutinize\nelaborate\npragmatic\nendeavor\nmeticulous\ninnovative\nversatile'
  );
  const [groups, setGroups] = useState<{ id: number; name: string }[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);

  const [loading, setLoading] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [activeTab, setActiveTab] = useState<'quiz' | 'spelling' | 'eng_uzb' | 'uzb_eng'>('quiz');
  const [exercises, setExercises] = useState<GeneratedExercises | null>(null);
  const [packId, setPackId] = useState<number | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Load Teacher Groups
  useEffect(() => {
    async function fetchGroups() {
      try {
        const res = await apiFetch<any>('/api/v1/school/overview/');
        const groupsList = (res?.groups || []).map((g: any) => ({
          id: g.id,
          name: g.name,
        }));
        setGroups(groupsList);
        if (groupsList.length > 0) {
          setSelectedGroupId(groupsList[0].id);
        }
      } catch (err) {
        console.error('Error fetching groups:', err);
      }
    }
    fetchGroups();
  }, []);

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  // Generate 4 Exercise Formats with AI
  const handleGenerate = async () => {
    if (!rawText.trim()) {
      showToast("Iltimos, kamida bitta inglizcha so'z kiriting.", 'error');
      return;
    }
    setLoading(true);
    setExercises(null);
    try {
      const res = await apiFetch<any>('/api/v1/vocabulary/generate/', {
        method: 'POST',
        body: JSON.stringify({
          raw_text: rawText,
          title: title.trim() || 'Ingliz tili Lug\'at To\'plami',
          group_id: selectedGroupId,
          save: true,
        }),
      });

      if (res.exercises_data) {
        setExercises(res.exercises_data);
        setPackId(res.id);
        showToast(`✨ ${res.word_count} ta so'zdan 4 ta mashq formati tayyorlandi!`, 'success');
      }
    } catch (err: any) {
      showToast(err.message || 'Mashqlarni generatsiya qilishda xatolik yuz berdi.', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Assign generated pack as Homework
  const handleAssignHomework = async () => {
    if (!packId || !selectedGroupId) return;
    setAssigning(true);
    try {
      const res = await apiFetch<any>('/api/v1/vocabulary/assign-homework/', {
        method: 'POST',
        body: JSON.stringify({
          pack_id: packId,
          group_id: selectedGroupId,
          due_days: 3,
        }),
      });
      showToast(res.message || 'Lug\'at guruhga vazifa qilib biriktirildi!', 'success');
    } catch (err: any) {
      showToast(err.message || 'Vazifani biriktirib bo\'lmadi.', 'error');
    } finally {
      setAssigning(false);
    }
  };

  const wordCount = rawText
    .split(/[\n,]+/)
    .map((w) => w.trim())
    .filter((w) => w.length > 1).length;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        {/* Toast */}
        {toast && (
          <div
            className={`p-4 rounded-xl shadow-lg border flex items-center justify-between transition-all ${
              toast.type === 'success'
                ? 'bg-emerald-950/80 border-emerald-500/50 text-emerald-200'
                : 'bg-rose-950/80 border-rose-500/50 text-rose-200'
            }`}
          >
            <span>{toast.message}</span>
            <button
              onClick={() => setToast(null)}
              className="text-xs uppercase px-2 py-1 bg-white/10 rounded hover:bg-white/20"
            >
              Yopish
            </button>
          </div>
        )}

        {/* Top Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/60 p-6 rounded-2xl border border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-2xl">✨</span>
              <h1 className="text-2xl font-bold text-white">
                Ingliz Tili AI Lug'at Generatori (50–60 So'z)
              </h1>
            </div>
            <p className="text-slate-400 text-sm">
              Xom so'zlar ro'yxatidan bir zumda 4 xil interaktiv mashq tuzing va guruhga dars vazifasi qilib biriktiring.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/teacher/finance"
              className="px-4 py-2.5 rounded-xl bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 font-medium text-sm transition-all"
            >
              💰 Moliya CRM
            </Link>
          </div>
        </div>

        {/* Word Input & Controls */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Input Parameters */}
          <div className="lg:col-span-1 bg-slate-900/80 p-5 rounded-2xl border border-slate-800 space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">
                To'plam Nomi
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Mavzu yoki Unit nomi"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">
                Biriktiriladigan Guruh
              </label>
              <select
                value={selectedGroupId || ''}
                onChange={(e) => setSelectedGroupId(Number(e.target.value))}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white focus:ring-2 focus:ring-purple-500"
              >
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    👥 {g.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-slate-400 uppercase">
                  So'zlar Ro'yxati ({wordCount} ta)
                </label>
                <span className="text-xs text-purple-400 font-medium">Tavsiya: 50–60 ta</span>
              </div>
              <textarea
                rows={12}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder="Har bir so'zni yangi qatordan yozing...&#10;resilient&#10;persistent&#10;ubiquitous"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl p-3 text-sm text-white font-mono leading-relaxed focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <button
              onClick={handleGenerate}
              disabled={loading || wordCount === 0}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-sm shadow-lg transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  AI generatsiya qilmoqda...
                </>
              ) : (
                <>✨ 4 Formatli Mashq Yaratish</>
              )}
            </button>
          </div>

          {/* Right: Live Interactive Preview */}
          <div className="lg:col-span-2 bg-slate-900/80 p-5 rounded-2xl border border-slate-800 flex flex-col justify-between">
            <div>
              {/* Tab Navigation */}
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-4 mb-4">
                <div className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800">
                  <button
                    onClick={() => setActiveTab('quiz')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      activeTab === 'quiz'
                        ? 'bg-purple-600 text-white shadow'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    1. Test (4 variantli)
                  </button>
                  <button
                    onClick={() => setActiveTab('spelling')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      activeTab === 'spelling'
                        ? 'bg-purple-600 text-white shadow'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    2. Spelling (Imlo)
                  </button>
                  <button
                    onClick={() => setActiveTab('eng_uzb')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      activeTab === 'eng_uzb'
                        ? 'bg-purple-600 text-white shadow'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    3. Eng ➔ Uzb
                  </button>
                  <button
                    onClick={() => setActiveTab('uzb_eng')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      activeTab === 'uzb_eng'
                        ? 'bg-purple-600 text-white shadow'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    4. Uzb ➔ Eng
                  </button>
                </div>

                {packId && (
                  <button
                    onClick={handleAssignHomework}
                    disabled={assigning}
                    className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-all shadow"
                  >
                    {assigning ? 'Yuklanmoqda...' : '📥 Guruhga Vazifa Qilib Berish'}
                  </button>
                )}
              </div>

              {/* Preview Content */}
              {!exercises ? (
                <div className="py-24 text-center text-slate-500">
                  <div className="text-4xl mb-3">📚</div>
                  <p className="text-sm">
                    Chap tomondan so'zlar ro'yxatini kiritib, <b>"4 Formatli Mashq Yaratish"</b> tugmasini bosing.
                  </p>
                </div>
              ) : (
                <div className="space-y-4 max-h-[550px] overflow-y-auto pr-2">
                  {/* Format 1: Quiz */}
                  {activeTab === 'quiz' &&
                    exercises.format_1_quiz.map((q, idx) => (
                      <div key={idx} className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
                        <div className="font-semibold text-white text-sm mb-2">
                          {idx + 1}. {q.question}
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {q.options.map((opt, oIdx) => (
                            <div
                              key={oIdx}
                              className={`p-2 rounded-lg border ${
                                opt === q.correct_answer
                                  ? 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300 font-medium'
                                  : 'bg-slate-900/60 border-slate-700/60 text-slate-300'
                              }`}
                            >
                              {opt} {opt === q.correct_answer && '✓'}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}

                  {/* Format 2: Spelling */}
                  {activeTab === 'spelling' &&
                    exercises.format_2_spelling.map((s, idx) => (
                      <div key={idx} className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
                        <div className="text-xs text-slate-400 mb-1">{s.prompt}</div>
                        <div className="font-mono text-lg font-bold text-amber-400 mb-2">
                          {s.hint_pattern}
                        </div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {s.scrambled_letters.map((lettr, lIdx) => (
                            <span
                              key={lIdx}
                              className="w-7 h-7 rounded bg-slate-900 border border-slate-700 flex items-center justify-center font-mono text-xs text-white uppercase font-bold"
                            >
                              {lettr}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}

                  {/* Format 3: Eng -> Uzb */}
                  {activeTab === 'eng_uzb' &&
                    exercises.format_3_eng_uzb.map((item, idx) => (
                      <div key={idx} className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
                        <div className="font-bold text-white text-base mb-2">
                          {idx + 1}. <span className="text-purple-400">{item.word}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {item.options.map((opt, oIdx) => (
                            <div
                              key={oIdx}
                              className={`p-2 rounded-lg border ${
                                opt === item.correct_answer
                                  ? 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300 font-medium'
                                  : 'bg-slate-900/60 border-slate-700/60 text-slate-300'
                              }`}
                            >
                              {opt}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}

                  {/* Format 4: Uzb -> Eng */}
                  {activeTab === 'uzb_eng' &&
                    exercises.format_4_uzb_eng.map((item, idx) => (
                      <div key={idx} className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
                        <div className="font-bold text-white text-base mb-2">
                          {idx + 1}. <span className="text-amber-400">{item.uzbek_word}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {item.options.map((opt, oIdx) => (
                            <div
                              key={oIdx}
                              className={`p-2 rounded-lg border ${
                                opt === item.correct_answer
                                  ? 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300 font-medium'
                                  : 'bg-slate-900/60 border-slate-700/60 text-slate-300'
                              }`}
                            >
                              {opt}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>

            {exercises && (
              <div className="pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span>Formatlar: Multiple Choice, Spelling, Eng➔Uzb, Uzb➔Eng</span>
                <span>Spaced Repetition bot viktorinasiga integratsiya qilingan</span>
              </div>
            )}
          </div>
        </div>
      </div>
  );
}
