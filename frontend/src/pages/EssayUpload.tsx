import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Camera, Image as ImageIcon, X } from 'lucide-react';
import AutoGrow from '../components/AutoGrow';
import LimitExceededModal from '../components/LimitExceededModal';
import { useLang } from '../i18n/LangContext';
import { Essays, type ApiError } from '../lib/api';
import { essayKind } from '../lib/essays';
import { useSubject } from '../lib/useSubject';

const MAX_PAGES = 10;

interface TopicLite {
  id: number;
  title: string;
  category?: string;
  rubric_type?: string;
  has_password?: boolean;
}

const countWords = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;

/**
 * Handwritten essay: pick pages (camera or gallery) → preview → recognise text →
 * the student checks and corrects it → graded as a photo essay. Recognition is
 * free; only the final submit counts against the plan's photo-essay allowance.
 */
/** Server error code of POST /essays/ocr/ -> message key (anything else: "no text recognised"). */
const OCR_ERRORS: Record<string, string> = {
  ocr_unavailable: 'eu_err_unavailable',
  invalid_image: 'eu_err_image',
  not_an_image: 'eu_err_image',
  file_too_large: 'eu_err_size',
  too_many_pages: 'eu_err_size',
  plan_required: 'eu_err_plan',
  ocr_daily_limit: 'eu_err_daily',
};

export default function EssayUpload() {
  const { t } = useLang();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const subjectFromProfile = useSubject();
  const subject = params.get('subject') === 'english' || params.get('subject') === 'uzbek' ? (params.get('subject') as 'uzbek' | 'english') : subjectFromProfile;

  const [pages, setPages] = useState<File[]>([]);
  const [topics, setTopics] = useState<TopicLite[]>([]);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [incomplete, setIncomplete] = useState(false);
  const [busy, setBusy] = useState<'ocr' | 'send' | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [limitOpen, setLimitOpen] = useState(false);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);

  const previews = useMemo(() => pages.map((p) => URL.createObjectURL(p)), [pages]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  useEffect(() => {
    Essays.topics({ subject })
      .then((r) => setTopics(((r.topics as TopicLite[]) || []).filter((tp) => !tp.has_password)))
      .catch(() => setTopics([]));
  }, [subject]);

  const add = (list: FileList | null) => {
    if (!list) return;
    setPages((prev) => [...prev, ...Array.from(list)].slice(0, MAX_PAGES));
    setText(null);
  };

  const recognise = async () => {
    setBusy('ocr');
    setErr(null);
    try {
      const res = await Essays.ocr(pages);
      setText(res.text);
      setIncomplete(res.incomplete);
    } catch (e) {
      const code = (e as ApiError).code;
      setErr(t(OCR_ERRORS[code ?? ''] ?? 'eu_err_failed'));
    } finally {
      setBusy(null);
    }
  };

  const send = async () => {
    if (text == null) return;
    setBusy('send');
    setErr(null);
    try {
      const res = await Essays.imageSubmit(text, topicId, subject);
      navigate(`/essays/result/${res.submission_id}`, { replace: true });
    } catch (e) {
      const ae = e as ApiError;
      if (ae.status === 403 && ae.code !== 'topic_locked') setLimitOpen(true);
      else setErr(ae.code === 'topic_required' ? t('eu_err_topic') : ae.code === 'too_short' ? t('eu_err_short') : ae.message || t('essay_js_error'));
      setBusy(null);
    }
  };

  const needTopic = subject === 'english';

  return (
    <div className="ew">
      <header className="ew-head">
        <h1>{t('es_upload')}</h1>
      </header>
      <p className="ew-note">{t(needTopic ? 'eu_hint_english' : 'eu_hint')}</p>
      {err && (
        <p className="ew-alert" role="alert">
          {err}
        </p>
      )}

      <label className="ew-label" htmlFor="eu-topic">
        {t('eu_topic')}
      </label>
      <select
        id="eu-topic"
        className="ew-field"
        value={topicId ?? ''}
        onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">{needTopic ? t('eu_topic_choose') : t('eu_topic_own')}</option>
        {topics.map((tp) => (
          <option key={tp.id} value={tp.id}>
            {t(`es_kind_${essayKind(tp)}`)} · {tp.title.length > 60 ? `${tp.title.slice(0, 58)}…` : tp.title}
          </option>
        ))}
      </select>

      <div className="eu-pick">
        <button type="button" className="ui-btn ui-btn--lg" onClick={() => cameraRef.current?.click()} disabled={pages.length >= MAX_PAGES}>
          <Camera size={18} aria-hidden="true" /> {t('eu_camera')}
        </button>
        <button type="button" className="ui-btn ui-btn--lg" onClick={() => galleryRef.current?.click()} disabled={pages.length >= MAX_PAGES}>
          <ImageIcon size={18} aria-hidden="true" /> {t('eu_gallery')}
        </button>
        <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={(e) => add(e.target.files)} />
        <input ref={galleryRef} type="file" accept="image/*" multiple onChange={(e) => add(e.target.files)} />
      </div>

      {pages.length > 0 && (
        <>
          <p className="ew-note">{t('eu_pages').replace('{n}', String(pages.length)).replace('{max}', String(MAX_PAGES))}</p>
          <div className="eu-thumbs">
            {previews.map((src, i) => (
              <div key={src} className="eu-thumb">
                <img src={src} alt={t('eu_page_n').replace('{n}', String(i + 1))} />
                <span>{i + 1}</span>
                <button
                  type="button"
                  aria-label={t('eu_remove')}
                  onClick={() => {
                    setPages((prev) => prev.filter((_, j) => j !== i));
                    setText(null);
                  }}
                >
                  <X size={18} aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
          {text == null && (
            <button type="button" className="ui-btn ui-btn--primary ui-btn--lg" disabled={busy !== null} onClick={() => void recognise()}>
              {busy === 'ocr' ? t('eu_recognising') : t('eu_recognise')}
            </button>
          )}
        </>
      )}

      {text != null && (
        <>
          <p className="ew-note">{t(incomplete ? 'eu_check_incomplete' : 'eu_check')}</p>
          <AutoGrow className="ew-text" value={text} onChange={(e) => setText(e.target.value)} aria-label={t('cd_writing_area')} rows={10} spellCheck />
          <div className="ew-bar">
            <div className="ew-bar__info">
              <span className="ew-count">
                {countWords(text)} {t('cd_words')}
              </span>
            </div>
            <button
              type="button"
              className="ui-btn ui-btn--primary"
              disabled={busy !== null || !text.trim() || (needTopic && topicId == null)}
              onClick={() => void send()}
            >
              {busy === 'send' ? t('loading') : t('ew_submit')}
            </button>
          </div>
        </>
      )}
      <LimitExceededModal isOpen={limitOpen} onClose={() => setLimitOpen(false)} message={t('paywall_reason_essay')} feature="essay" subject={subject} />
    </div>
  );
}
