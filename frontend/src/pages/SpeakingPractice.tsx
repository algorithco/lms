import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Mic,
  Square,
  RotateCcw,
  Clock,
  Sparkles,
  ArrowLeft,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { SpeakingApi, type SpeakingTopicItem } from '../lib/api';

export default function SpeakingPractice() {
  const { topicId } = useParams<{ topicId: string }>();
  const navigate = useNavigate();

  const [topic, setTopic] = useState<SpeakingTopicItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Exam phase: 'prep' -> 'ready' -> 'recording' -> 'review' -> 'submitting'
  const [phase, setPhase] = useState<'prep' | 'ready' | 'recording' | 'review' | 'submitting'>('prep');

  // Timers
  const [prepSecondsLeft, setPrepSecondsLeft] = useState<number>(60);
  const [speakSecondsLeft, setSpeakSecondsLeft] = useState<number>(120);

  // Audio recording
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const prepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const speakTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load topic
  useEffect(() => {
    if (!topicId) return;
    setLoading(true);
    SpeakingApi.topic(topicId)
      .then((t) => {
        setTopic(t);
        setPrepSecondsLeft(t.prep_time_seconds || 60);
        setSpeakSecondsLeft(t.speak_time_seconds || 120);
        // If not part 2, skip prep phase directly to 'ready'
        if (t.part !== 'part2') {
          setPhase('ready');
        }
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Mavzuni yuklashda xatolik.");
      })
      .finally(() => setLoading(false));
  }, [topicId]);

  // Prep Countdown
  useEffect(() => {
    if (phase !== 'prep') return;
    prepTimerRef.current = setInterval(() => {
      setPrepSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(prepTimerRef.current!);
          setPhase('ready');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (prepTimerRef.current) clearInterval(prepTimerRef.current);
    };
  }, [phase]);

  // Speak Countdown
  useEffect(() => {
    if (phase !== 'recording') return;
    speakTimerRef.current = setInterval(() => {
      setSpeakSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(speakTimerRef.current!);
          stopRecording();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (speakTimerRef.current) clearInterval(speakTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        // Stop audio tracks
        stream.getTracks().forEach((track) => track.stop());
        setPhase('review');
      };

      mediaRecorder.start();
      setPhase('recording');
    } catch {
      setError(
        "Mikrofonga ruxsat berilmadi yoki mikrofon topilmadi. Iltimos, brauzer sozlamalarida mikrofonga ruxsat bering."
      );
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    if (speakTimerRef.current) clearInterval(speakTimerRef.current);
  };

  const handleRetake = () => {
    setAudioBlob(null);
    setAudioUrl(null);
    setSpeakSecondsLeft(topic?.speak_time_seconds || 120);
    setPhase('ready');
  };

  const handleSubmit = async () => {
    if (!audioBlob || !topic) return;

    setPhase('submitting');
    setError(null);

    const fd = new FormData();
    fd.append('audio', audioBlob, 'speaking_response.webm');
    fd.append('topic_id', String(topic.id));
    const duration = (topic.speak_time_seconds || 120) - speakSecondsLeft;
    fd.append('duration_seconds', String(Math.max(10, duration)));

    try {
      const res = await SpeakingApi.submit(fd);
      if (res.ok && res.submission) {
        navigate(`/speaking/result/${res.submission.id}`);
      } else {
        throw new Error("Baholash natijasini olishda xatolik yuz berdi.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Topshiriqni yuborishda xatolik yuz berdi.");
      setPhase('review');
    }
  };

  const formatTimer = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 20px', color: 'var(--ink-muted)' }}>
        <RefreshCw size={32} className="animate-spin" style={{ margin: '0 auto 12px' }} />
        <div>Speaking imtihon xonasi tayyorlanmoqda...</div>
      </div>
    );
  }

  if (error && !topic) {
    return (
      <div className="card error" style={{ maxWidth: 600, margin: '40px auto' }}>
        <h3>Xatolik yuz berdi</h3>
        <p>{error}</p>
        <Link to="/speaking" className="btn ghost sm">
          ← Ro'yxatga qaytish
        </Link>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 840, margin: '0 auto', paddingBottom: 60 }}>
      {/* Top back button */}
      <div style={{ marginBottom: 16 }}>
        <Link to="/speaking" className="btn ghost sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <ArrowLeft size={14} /> Barcha mavzularga qaytish
        </Link>
      </div>

      {/* Main Cue Card / Topic Box */}
      {topic && (
        <div
          className="card"
          style={{
            borderRadius: 20,
            border: '2px solid rgba(99, 102, 241, 0.3)',
            background: 'var(--card)',
            padding: 28,
            marginBottom: 24,
            boxShadow: 'var(--card-shadow, 0 10px 25px -5px rgba(0,0,0,0.1))',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
            <span
              className="badge"
              style={{
                background: 'rgba(99, 102, 241, 0.25)',
                color: '#C7D2FE',
                fontWeight: 800,
                fontSize: '0.82rem',
                padding: '6px 14px',
                borderRadius: 20,
              }}
            >
              🎙️ {topic.part_label}
            </span>

            {/* Phase Timer Indicator */}
            {phase === 'prep' && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 14px',
                  borderRadius: 20,
                  background: 'rgba(245, 158, 11, 0.2)',
                  border: '1px solid #F59E0B',
                  color: '#FBBF24',
                  fontWeight: 800,
                }}
              >
                <Clock size={16} />
                <span>Tayyorgarlik vaqti: {formatTimer(prepSecondsLeft)}</span>
              </div>
            )}

            {phase === 'recording' && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 14px',
                  borderRadius: 20,
                  background: 'rgba(244, 63, 94, 0.2)',
                  border: '1px solid #F43F5E',
                  color: '#FDA4AF',
                  fontWeight: 800,
                }}
              >
                <span className="pulsing-dot" style={{ width: 10, height: 10, borderRadius: '50%', background: '#F43F5E' }} />
                <span>Ovoz yozilmoqda: {formatTimer(speakSecondsLeft)}</span>
              </div>
            )}
          </div>

          <h2 style={{ fontSize: '1.45rem', fontWeight: 900, margin: '0 0 12px 0', color: 'var(--ink)' }}>
            {topic.title}
          </h2>

          <p style={{ fontSize: '1.02rem', lineHeight: 1.6, margin: '0 0 18px 0', color: 'var(--ink)' }}>
            {topic.prompt}
          </p>

          {/* Cue Card bullet points */}
          {topic.bullet_points && topic.bullet_points.length > 0 && (
            <div
              style={{
                padding: '16px 20px',
                borderRadius: 14,
                background: 'rgba(99, 102, 241, 0.06)',
                border: '1px solid rgba(99, 102, 241, 0.15)',
                marginBottom: 16,
              }}
            >
              <span style={{ fontSize: '0.84rem', fontWeight: 800, color: 'var(--accent, #6366f1)', textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>
                You should say:
              </span>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: '0.92rem', lineHeight: 1.7, color: 'var(--ink)' }}>
                {topic.bullet_points.map((pt, idx) => (
                  <li key={idx}>{pt}</li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 12,
                background: 'rgba(244, 63, 94, 0.15)',
                border: '1px solid #F43F5E',
                color: '#FDA4AF',
                fontSize: '0.88rem',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginTop: 16,
              }}
            >
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}
        </div>
      )}

      {/* Recording Control Hub */}
      <div
        className="card"
        style={{
          borderRadius: 20,
          padding: 32,
          textAlign: 'center',
          background: 'rgba(15, 23, 42, 0.7)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        }}
      >
        {/* PHASE 1: PREPARATION */}
        {phase === 'prep' && (
          <div>
            <div style={{ fontSize: '2.5rem', fontWeight: 900, color: '#FBBF24', marginBottom: 6 }}>
              {formatTimer(prepSecondsLeft)}
            </div>
            <p className="muted" style={{ maxWidth: 440, margin: '0 auto 20px' }}>
              Qog'ozga qisqa reja tuzib oling. Tayyorgarlik vaqti tugagach nutq so'zlash boshlanadi.
            </p>
            <button
              type="button"
              onClick={() => {
                if (prepTimerRef.current) clearInterval(prepTimerRef.current);
                setPhase('ready');
              }}
              className="btn sm ghost"
              style={{ fontWeight: 700 }}
            >
              Tayyorgarlikni o'tkazib yuborish (Tayyorman) →
            </button>
          </div>
        )}

        {/* PHASE 2: READY TO RECORD */}
        {phase === 'ready' && (
          <div>
            <div
              style={{
                width: 84,
                height: 84,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #6366F1 0%, #4F46E5 100%)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 18px',
                boxShadow: '0 10px 25px rgba(99, 102, 241, 0.5)',
                cursor: 'pointer',
              }}
              onClick={startRecording}
            >
              <Mic size={38} />
            </div>
            <h3 style={{ margin: '0 0 6px 0', fontSize: '1.25rem', fontWeight: 800 }}>
              Mikrofonni yoqish va javob berish
            </h3>
            <p className="muted small" style={{ maxWidth: 400, margin: '0 auto 20px' }}>
              Yuqoridagi binafsha tugmani bosing va baland, ravon ovozda gapirishni boshlang (maksimal {topic?.speak_time_seconds || 120} soniya).
            </p>
            <button
              type="button"
              onClick={startRecording}
              className="btn primary"
              style={{ padding: '12px 28px', fontWeight: 800, fontSize: '0.98rem' }}
            >
              🎙️ Gapirishni boshlash
            </button>
          </div>
        )}

        {/* PHASE 3: RECORDING IN PROGRESS */}
        {phase === 'recording' && (
          <div>
            <div
              style={{
                width: 90,
                height: 90,
                borderRadius: '50%',
                background: 'rgba(244, 63, 94, 0.2)',
                border: '3px solid #F43F5E',
                color: '#F43F5E',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
                animation: 'pulse 1.5s infinite',
                cursor: 'pointer',
              }}
              onClick={stopRecording}
            >
              <Square size={34} fill="#F43F5E" />
            </div>

            <div style={{ fontSize: '2.2rem', fontWeight: 900, color: '#F43F5E', marginBottom: 4 }}>
              {formatTimer(speakSecondsLeft)}
            </div>
            <p className="muted small" style={{ marginBottom: 20 }}>
              Ovoz yozilmoqda... Tugatgach qizil to'xtatish tugmasini bosing.
            </p>

            <button
              type="button"
              onClick={stopRecording}
              className="btn danger"
              style={{ padding: '10px 24px', fontWeight: 800 }}
            >
              ⏹️ Yozishni to'xtatish
            </button>
          </div>
        )}

        {/* PHASE 4: REVIEW & PLAYBACK */}
        {phase === 'review' && audioUrl && (
          <div>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '1.15rem', fontWeight: 800 }}>
              ✅ Ovoz yozuvi tayyor
            </h3>
            <div style={{ maxWidth: 400, margin: '0 auto 20px' }}>
              <audio src={audioUrl} controls style={{ width: '100%', borderRadius: 10 }} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={handleRetake}
                className="btn ghost"
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <RotateCcw size={15} /> Qaytadan yozish
              </button>

              <button
                type="button"
                onClick={handleSubmit}
                className="btn primary"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 24px',
                  fontWeight: 800,
                }}
              >
                <Sparkles size={16} /> AI Examinerga baholatish
              </button>
            </div>
          </div>
        )}

        {/* PHASE 5: SUBMITTING / AI EVALUATING */}
        {phase === 'submitting' && (
          <div style={{ padding: '20px 0' }}>
            <RefreshCw size={42} className="animate-spin" style={{ margin: '0 auto 16px', color: '#6366F1' }} />
            <h3 style={{ margin: '0 0 8px 0', fontSize: '1.25rem', fontWeight: 800 }}>
              Gemini AI nutqingizni baholamoqda...
            </h3>
            <p className="muted small" style={{ maxWidth: 440, margin: '0 auto' }}>
              Nutq ravonligi (FC), so'z boyligi (LR), grammatika (GRA) va talaffuz (PR) mezonlari tahlil qilinmoqda. Bu bir necha soniya vaqt oladi.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
