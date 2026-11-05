import { useNavigate } from 'react-router-dom';
import { ArrowRight, Award, GraduationCap, Headphones, PenLine } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLang } from '../i18n/LangContext';

interface Props {
  onOpen?: (path: string) => void;
}

const TRACKS = [
  {
    id: 'bmb',
    Icon: Award,
    to: '/tests',
    subject: 'uzbek' as const,
    track: 'national_certificate',
    accent: '#C8922A',
    accentBg: 'rgba(200, 146, 42, 0.14)',
    tagKey: 'landing.bmb_tag',
    tagFallback: 'BMB Rasch + 45 savol',
    titleKey: 'landing.bmb_title',
    titleFallback: 'BMB Milliy Sertifikat',
    descKey: 'landing.bmb_desc',
    descFallback: "Ona tili va adabiyot bo'yicha rasmiy davlat formatidagi 45 talik diagnostik testlar va A+ daraja tahlili.",
    ctaKey: 'landing.start_test_btn',
    ctaFallback: 'Testni boshlash',
  },
  {
    id: 'attestation',
    Icon: GraduationCap,
    to: '/tests',
    subject: 'uzbek' as const,
    track: 'attestation',
    accent: '#10B981',
    accentBg: 'rgba(16, 185, 129, 0.14)',
    tagKey: 'landing.attestation_tag',
    tagFallback: '70% Ustama · 50 savol',
    titleKey: 'landing.attestation_title',
    titleFallback: 'Attestatsiya 2026',
    descKey: 'landing.attestation_desc',
    descFallback: "Pedagoglar uchun mutaxassislik fani (35), kasbiy standart (5) va pedagogik mahorat (10) sinov simulyatori.",
    ctaKey: 'landing.start_test_btn',
    ctaFallback: 'Sinovni boshlash',
  },
  {
    id: 'essay',
    Icon: PenLine,
    to: '/essays',
    subject: 'uzbek' as const,
    track: 'national_certificate',
    accent: '#F59E0B',
    accentBg: 'rgba(245, 158, 11, 0.14)',
    tagKey: 'landing.ai_rubric_tag',
    tagFallback: '12 Mezon · Band 9.0',
    titleKey: 'landing.ai_essay_title',
    titleFallback: 'AI Esse va Speaking Tahlili',
    descKey: 'landing.ai_essay_desc',
    descFallback: 'BMB 12 mezoni hamda IELTS Writing Task 1/2 va Speaking javoblarini 15 soniyada tekshiruvchi AI ustoz.',
    ctaKey: 'landing.write_essay_btn',
    ctaFallback: 'Esse yozish',
  },
  {
    id: 'english',
    Icon: Headphones,
    to: '/tests',
    subject: 'english' as const,
    track: 'ielts',
    accent: '#3B82F6',
    accentBg: 'rgba(59, 130, 246, 0.14)',
    tagKey: 'landing.cambridge_tag',
    tagFallback: 'CD-IELTS · CEFR · OMR',
    titleKey: 'landing.cefr_title',
    titleFallback: 'CEFR & IELTS Mock + Titul Skaner',
    descKey: 'landing.cefr_desc',
    descFallback: 'Listening, Reading CBT imtihon interfeysi hamda qogʻoz titul varaqalarini kamera orqali 1 soniyada tekshirish.',
    ctaKey: 'landing.english_cbt_btn',
    ctaFallback: 'Mock ishlash',
  },
] as const;

/** Unified, high-contrast 4-card exam showcase for both Dark and Light themes. */
export default function ExamTracks({ onOpen }: Props) {
  const { t } = useLang();
  const { user } = useAuth();
  const navigate = useNavigate();

  const handleTrackClick = (item: (typeof TRACKS)[number]) => {
    try {
      localStorage.setItem('grandec_selected_track', item.track);
      localStorage.setItem('landing_subject', item.subject);
      localStorage.setItem('lms_subject', item.subject);
      localStorage.setItem('active_subject', item.subject);
      window.dispatchEvent(new CustomEvent('subject-changed', { detail: item.subject }));
    } catch {
      /* ignore */
    }
    if (user) {
      navigate(item.to);
    } else if (onOpen) {
      onOpen(item.to);
    } else {
      navigate(item.to);
    }
  };

  return (
    <section
      className="lp-tracks"
      aria-labelledby="lp-tracks-title"
      style={{
        maxWidth: 1200,
        margin: '0 auto',
        padding: '32px 20px 48px',
      }}
    >
      <div
        className="lp-tracks__head"
        style={{
          textAlign: 'center',
          maxWidth: 680,
          margin: '0 auto 28px',
        }}
      >
        <h2
          id="lp-tracks-title"
          style={{
            margin: '0 0 8px',
            fontSize: 'clamp(1.6rem, 3.2vw, 2.25rem)',
            fontWeight: 900,
            color: 'var(--text-primary, var(--ink))',
            letterSpacing: '-0.02em',
          }}
        >
          {t('landing.which_exam_title', 'Qaysi imtihonga tayyorlanasiz?')}
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: 15,
            color: 'var(--text-secondary, var(--muted))',
            lineHeight: 1.6,
          }}
        >
          {t('landing.which_exam_desc', "Yo'nalishingizni tanlang va shaxsiy AI tahlili bilan bugunoq mashqni boshlang")}
        </p>
      </div>

      <div
        className="lp-tracks__grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 255px), 1fr))',
          gap: 18,
        }}
      >
        {TRACKS.map((item) => {
          const { id, Icon, accent, accentBg, tagKey, tagFallback, titleKey, titleFallback, descKey, descFallback, ctaKey, ctaFallback } = item;
          return (
            <button
              key={id}
              type="button"
              className="ui-card lp-track"
              onClick={() => handleTrackClick(item)}
              style={{
                background: 'var(--bg-card, var(--card))',
                border: '1.5px solid var(--border-default, var(--border))',
                borderRadius: 20,
                padding: '22px 20px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'stretch',
                gap: 12,
                textAlign: 'left',
                color: 'var(--text-primary, var(--ink))',
                cursor: 'pointer',
                boxShadow: 'var(--card-shadow)',
                transition: 'transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-3px)';
                e.currentTarget.style.borderColor = accent;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.borderColor = 'var(--border-default, var(--border))';
              }}
            >
              <span
                className="lp-track__top"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 10,
                }}
              >
                <span
                  className="ic-chip"
                  style={{
                    width: 42,
                    height: 42,
                    borderRadius: 12,
                    background: accentBg,
                    color: accent,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Icon size={22} aria-hidden="true" />
                </span>
                <span
                  className="lp-track__tag"
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    padding: '4px 10px',
                    borderRadius: 999,
                    background: accentBg,
                    color: accent,
                    border: `1px solid ${accent}40`,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {t(tagKey, tagFallback)}
                </span>
              </span>

              <span
                className="lp-track__title"
                style={{
                  fontSize: 18,
                  fontWeight: 900,
                  color: 'var(--text-primary, var(--ink))',
                  lineHeight: 1.3,
                }}
              >
                {t(titleKey, titleFallback)}
              </span>

              <span
                className="lp-track__desc"
                style={{
                  fontSize: 13.5,
                  lineHeight: 1.55,
                  color: 'var(--text-secondary, var(--muted))',
                  flex: 1,
                }}
              >
                {t(descKey, descFallback)}
              </span>

              <span
                className="lp-track__cta"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  fontSize: 13.5,
                  fontWeight: 800,
                  color: accent,
                  marginTop: 4,
                }}
              >
                {t(ctaKey, ctaFallback)} <ArrowRight size={16} aria-hidden="true" />
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
