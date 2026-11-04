import { ArrowRight, Award, GraduationCap, Headphones, PenLine } from 'lucide-react';
import { useLang } from '../i18n/LangContext';

interface Props {
  onOpen: (path: string) => void;
}

const TRACKS = [
  { id: 'bmb', Icon: Award, to: '/tests', tag: 'landing.bmb_tag', title: 'landing.bmb_title', desc: 'landing.bmb_desc', cta: 'landing.start_test_btn' },
  { id: 'attestation', Icon: GraduationCap, to: '/tests', tag: 'landing.attestation_tag', title: 'landing.attestation_title', desc: 'landing.attestation_desc', cta: 'landing.start_test_btn' },
  { id: 'essay', Icon: PenLine, to: '/essays', tag: 'landing.ai_rubric_tag', title: 'landing.ai_essay_title', desc: 'landing.ai_essay_desc', cta: 'landing.write_essay_btn' },
  { id: 'english', Icon: Headphones, to: '/tests', tag: 'landing.cambridge_tag', title: 'landing.cefr_title', desc: 'landing.cefr_desc', cta: 'landing.english_cbt_btn' },
] as const;

/** "Which exam are you preparing for?" — four equal cards: icon chip, tag, title, text, one action row. */
export default function ExamTracks({ onOpen }: Props) {
  const { t } = useLang();
  return (
    <section className="lp-tracks" aria-labelledby="lp-tracks-title">
      <div className="lp-tracks__head">
        <h2 id="lp-tracks-title">{t('landing.which_exam_title')}</h2>
        <p>{t('landing.which_exam_desc')}</p>
      </div>
      <div className="lp-tracks__grid">
        {TRACKS.map(({ id, Icon, to, tag, title, desc, cta }) => (
          <button key={id} type="button" className="ui-card lp-track" onClick={() => onOpen(to)}>
            <span className="lp-track__top">
              <span className="ic-chip">
                <Icon size={20} aria-hidden="true" />
              </span>
              <span className="lp-track__tag">{t(tag)}</span>
            </span>
            <span className="lp-track__title">{t(title)}</span>
            <span className="lp-track__desc">{t(desc)}</span>
            <span className="lp-track__cta">
              {t(cta)} <ArrowRight size={16} aria-hidden="true" />
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
