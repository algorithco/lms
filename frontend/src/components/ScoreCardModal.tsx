import { useCallback, useEffect, useMemo, useState } from 'react';
import { X, Download, Share2, Send, FileText, Copy, Check } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { useTranslation } from '../i18n/useTranslation';

export interface ScoreCardModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  studentName: string;
  scorePercentage: number;
  gradeBadge?: string;
  correctCount: number;
  incorrectCount: number;
  totalQuestions: number;
  timeSpent?: string;
  date?: string;
  subject?: string;
  branchName?: string;
  resultId?: number | string;
  referralCode?: string;
  shareUrl?: string;
  telegramShareUrl?: string;
  pdfUrl?: string;
}

/**
 * Story Card export size (Instagram / Telegram story spec).
 *
 * The bitmap is ALWAYS exactly 1080x1920 CSS-independent pixels and is NOT
 * multiplied by `devicePixelRatio`: 1080*1920*dpr² would be 18.6M px at dpr=3,
 * which exceeds iOS Safari's ~16.7M px canvas limit (the canvas silently turns
 * blank) and costs ~75 MB of RAM. The on-screen preview is a plain <img> of the
 * encoded PNG, so the browser rescales it with its own high-quality filter and
 * it stays sharp on Retina screens.
 */
const CARD_WIDTH = 1080;
const CARD_HEIGHT = 1920;
const FONT_STACK = 'Inter, system-ui, -apple-system, "Segoe UI", sans-serif';

const SUBJECT_MAP: Record<string, { label: string; icon: string }> = {
  biology: { label: 'BIOLOGIYA (MILLIY SERTIFIKAT & DTM)', icon: '🧬' },
  chemistry: { label: 'KIMYO (MILLIY SERTIFIKAT & DTM)', icon: '🧪' },
  law: { label: 'HUQUQSHUNOSLIK (YURISPRUDENSIYA)', icon: '⚖️' },
  uzbek: { label: 'ONA TILI VA ADABIYOT', icon: '🇺🇿' },
  english: { label: 'INGLIZ TILI (CEFR / IELTS)', icon: '🇬🇧' },
};

interface StoryCardData {
  title: string;
  studentName: string;
  scorePercentage: number;
  gradeBadge: string;
  correctCount: number;
  incorrectCount: number;
  timeSpent: string;
  date: string;
  branch: string;
  subjectLabel: string;
  subjectIcon: string;
}

type LetterSpacingContext = CanvasRenderingContext2D & { letterSpacing?: string };

/** Rounded-rect path with a fallback for browsers without ctx.roundRect (Safari < 16). */
function roundedRectPath(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  ctx.beginPath();
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(x, y, w, h, r);
    return;
  }
  const radius = Math.min(r, w / 2, h / 2);
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 2)}...` : value;
}

function drawStoryCard(ctx: CanvasRenderingContext2D, d: StoryCardData): void {
  const width = CARD_WIDTH;
  const height = CARD_HEIGHT;
  const spacingCtx = ctx as LetterSpacingContext;
  const supportsLetterSpacing = 'letterSpacing' in ctx;

  // 1. Background deep gradient
  const bgGrad = ctx.createLinearGradient(0, 0, width, height);
  bgGrad.addColorStop(0, '#090D16');
  bgGrad.addColorStop(0.5, '#0F172A');
  bgGrad.addColorStop(1, '#05070C');
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, width, height);

  // 2. Radial gold glow behind center
  const radial = ctx.createRadialGradient(width / 2, 850, 50, width / 2, 850, 500);
  radial.addColorStop(0, 'rgba(245, 158, 11, 0.18)');
  radial.addColorStop(0.5, 'rgba(217, 119, 6, 0.06)');
  radial.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = radial;
  ctx.fillRect(0, 0, width, height);

  // 3. Ornate double gold borders
  ctx.lineWidth = 4;
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.45)';
  ctx.strokeRect(40, 40, width - 80, height - 80);

  ctx.lineWidth = 1.5;
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.25)';
  ctx.strokeRect(55, 55, width - 110, height - 110);

  const corners: ReadonlyArray<readonly [number, number]> = [
    [55, 55],
    [width - 55, 55],
    [55, height - 55],
    [width - 55, height - 55],
  ];
  ctx.fillStyle = '#F59E0B';
  corners.forEach(([x, y]) => {
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, Math.PI * 2);
    ctx.fill();
  });

  // 4. Header: brand & title
  ctx.textAlign = 'center';
  ctx.font = `54px ${FONT_STACK}`;
  ctx.fillText('🦅', width / 2, 170);

  ctx.font = `900 46px ${FONT_STACK}`;
  ctx.fillStyle = '#FFFFFF';
  ctx.fillText('GRAND EDUCATION', width / 2, 240);

  ctx.font = `700 22px ${FONT_STACK}`;
  ctx.fillStyle = '#FBBF24';
  if (supportsLetterSpacing) spacingCtx.letterSpacing = '2px';
  ctx.fillText(d.branch.toUpperCase(), width / 2, 285);
  if (supportsLetterSpacing) spacingCtx.letterSpacing = '0px';

  // Subject pill
  const subjPillW = 600;
  const subjPillH = 48;
  const subjPillX = width / 2 - subjPillW / 2;
  const subjPillY = 320;
  ctx.fillStyle = 'rgba(245, 158, 11, 0.12)';
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.35)';
  ctx.lineWidth = 1.5;
  roundedRectPath(ctx, subjPillX, subjPillY, subjPillW, subjPillH, 24);
  ctx.fill();
  ctx.stroke();

  ctx.font = `800 20px ${FONT_STACK}`;
  ctx.fillStyle = '#FDE68A';
  ctx.fillText(`${d.subjectIcon}  ${d.subjectLabel}`, width / 2, subjPillY + 31);

  // Divider
  ctx.beginPath();
  ctx.moveTo(width / 2 - 220, 395);
  ctx.lineTo(width / 2 + 220, 395);
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.3)';
  ctx.lineWidth = 2;
  ctx.stroke();

  // 5. Exam title
  ctx.font = `600 28px ${FONT_STACK}`;
  ctx.fillStyle = '#94A3B8';
  ctx.fillText(truncate(d.title, 44), width / 2, 455);

  // 6. Student name
  ctx.font = `900 56px ${FONT_STACK}`;
  ctx.fillStyle = '#FFFFFF';
  ctx.fillText(truncate(d.studentName || "O'quvchi", 25), width / 2, 545);

  // 7. Score ring
  const centerX = width / 2;
  const centerY = 820;
  const radius = 210;

  ctx.beginPath();
  ctx.arc(centerX, centerY, radius + 20, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.18)';
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
  const ringGrad = ctx.createLinearGradient(centerX - radius, centerY - radius, centerX + radius, centerY + radius);
  ringGrad.addColorStop(0, '#F59E0B');
  ringGrad.addColorStop(0.5, '#FDE68A');
  ringGrad.addColorStop(1, '#D97706');
  ctx.strokeStyle = ringGrad;
  ctx.lineWidth = 14;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(centerX, centerY, radius - 8, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
  ctx.fill();

  ctx.font = `900 130px ${FONT_STACK}`;
  const textGrad = ctx.createLinearGradient(centerX, centerY - 60, centerX, centerY + 50);
  textGrad.addColorStop(0, '#FFFFFF');
  textGrad.addColorStop(1, '#FBBF24');
  ctx.fillStyle = textGrad;
  ctx.fillText(`${d.scorePercentage}%`, centerX, centerY + 45);

  ctx.font = `700 24px ${FONT_STACK}`;
  ctx.fillStyle = '#94A3B8';
  ctx.fillText('YAKUNIY NATIJA', centerX, centerY + 105);

  // 8. Grade badge
  if (d.gradeBadge) {
    const pillY = 1120;
    const pillW = 500;
    const pillH = 76;
    const pillX = centerX - pillW / 2;

    const pillGrad = ctx.createLinearGradient(pillX, pillY, pillX + pillW, pillY);
    pillGrad.addColorStop(0, '#D97706');
    pillGrad.addColorStop(0.5, '#F59E0B');
    pillGrad.addColorStop(1, '#B45309');
    ctx.fillStyle = pillGrad;
    roundedRectPath(ctx, pillX, pillY, pillW, pillH, 38);
    ctx.fill();

    ctx.font = `900 32px ${FONT_STACK}`;
    ctx.fillStyle = '#0F172A';
    ctx.fillText(d.gradeBadge.toUpperCase(), centerX, pillY + 48);
  }

  // 9. Stats grid
  const statY = 1260;
  const statW = 280;
  const statH = 150;
  const gap = 30;
  const startX = (width - (statW * 3 + gap * 2)) / 2;

  const stats = [
    { label: 'TO‘G‘RI', value: String(d.correctCount), color: '#10B981', border: 'rgba(16, 185, 129, 0.35)' },
    { label: 'NOTO‘G‘RI', value: String(d.incorrectCount), color: '#F43F5E', border: 'rgba(244, 63, 94, 0.35)' },
    { label: 'VAQT', value: d.timeSpent || '—', color: '#38BDF8', border: 'rgba(56, 189, 248, 0.35)' },
  ];

  stats.forEach((s, idx) => {
    const x = startX + idx * (statW + gap);
    ctx.fillStyle = 'rgba(15, 23, 42, 0.75)';
    ctx.strokeStyle = s.border;
    ctx.lineWidth = 2;
    roundedRectPath(ctx, x, statY, statW, statH, 20);
    ctx.fill();
    ctx.stroke();

    ctx.font = `700 18px ${FONT_STACK}`;
    ctx.fillStyle = '#94A3B8';
    ctx.fillText(s.label, x + statW / 2, statY + 45);

    ctx.font = `900 34px ${FONT_STACK}`;
    ctx.fillStyle = s.color;
    ctx.fillText(s.value, x + statW / 2, statY + 105);
  });

  // 10. Footer: verification & CTA
  ctx.beginPath();
  ctx.moveTo(120, 1490);
  ctx.lineTo(width - 120, 1490);
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.25)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  const qrX = 140;
  const qrY = 1540;

  ctx.textAlign = 'left';
  ctx.font = `700 32px ${FONT_STACK}`;
  ctx.fillStyle = '#FFFFFF';
  ctx.fillText("O'z bilimingizni sinab ko'ring", qrX + 40, qrY + 55);
  ctx.fillText('va milliy sertifikat darajangizni oling:', qrX + 40, qrY + 98);

  ctx.font = `900 38px ${FONT_STACK}`;
  ctx.fillStyle = '#F59E0B';
  ctx.fillText('grandec.uz', qrX + 40, qrY + 155);

  ctx.textAlign = 'center';
  ctx.font = `500 20px ${FONT_STACK}`;
  ctx.fillStyle = '#64748B';
  ctx.fillText(`Topshirilgan sana: ${d.date}`, width / 2, 1820);
}

/** Renders the card on a throw-away canvas and resolves with the PNG blob. */
async function renderStoryCardBlob(data: StoryCardData): Promise<Blob | null> {
  // Make sure web fonts are ready, otherwise the first paint uses a fallback font.
  try {
    if (document.fonts?.ready) await document.fonts.ready;
  } catch {
    /* font loading is best-effort */
  }

  const canvas = document.createElement('canvas');
  canvas.width = CARD_WIDTH;
  canvas.height = CARD_HEIGHT;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;

  try {
    drawStoryCard(ctx, data);
    return await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
  } finally {
    // iOS Safari keeps canvas backing stores alive until they are shrunk: release it now.
    canvas.width = 0;
    canvas.height = 0;
  }
}

export default function ScoreCardModal({
  isOpen,
  onClose,
  title,
  studentName,
  scorePercentage,
  gradeBadge = '',
  correctCount,
  incorrectCount,
  totalQuestions: _totalQuestions,
  timeSpent = '',
  date = new Date().toLocaleDateString(),
  subject = '',
  branchName = '',
  resultId,
  referralCode = '',
  shareUrl = '',
  telegramShareUrl = '',
  pdfUrl = '',
}: ScoreCardModalProps) {
  const [cardBlob, setCardBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const toast = useToast();
  const { t } = useTranslation();

  const refCode = referralCode || 'GRAND';
  const effectiveShareUrl = shareUrl || `https://grandec.uz/join?ref=${refCode}`;

  // Stable primitives only: an object created per render would re-run the canvas effect every render.
  const subjInfo = useMemo(
    () =>
      SUBJECT_MAP[subject.toLowerCase()] || {
        label: (subject || 'GRAND EDUCATION').toUpperCase(),
        icon: '🏆',
      },
    [subject],
  );
  const subjectLabel = subjInfo.label;
  const subjectIcon = subjInfo.icon;

  const effectiveBranch = branchName || 'Grand Education Markaziy Filiali';

  const defaultShareText = `Men Grand Education'da ${subjectIcon} ${subjectLabel} fanidan ${scorePercentage}% ball (${gradeBadge || 'Sertifikat'}) oldim! Sen ham bilimingni sinab ko'r:`;
  const effectiveTgUrl =
    telegramShareUrl ||
    `https://t.me/share/url?url=${encodeURIComponent(effectiveShareUrl)}&text=${encodeURIComponent(defaultShareText)}`;

  const effectivePdfUrl = pdfUrl || (resultId ? `/api/results/${resultId}/pdf/` : '');

  // Render the PNG once per distinct input; clean up the object URL on every change/unmount.
  useEffect(() => {
    if (!isOpen) return undefined;

    let cancelled = false;
    let objectUrl: string | null = null;

    void renderStoryCardBlob({
      title,
      studentName,
      scorePercentage,
      gradeBadge,
      correctCount,
      incorrectCount,
      timeSpent,
      date,
      branch: effectiveBranch,
      subjectLabel,
      subjectIcon,
    }).then((blob) => {
      if (cancelled || !blob) return;
      objectUrl = URL.createObjectURL(blob);
      setCardBlob(blob);
      setPreviewUrl(objectUrl);
    });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setCardBlob(null);
      setPreviewUrl(null);
    };
  }, [
    isOpen,
    title,
    studentName,
    scorePercentage,
    gradeBadge,
    correctCount,
    incorrectCount,
    timeSpent,
    date,
    effectiveBranch,
    subjectLabel,
    subjectIcon,
  ]);

  const fileName = `grandec-score-${scorePercentage}ball.png`;

  const handleDownload = useCallback(() => {
    if (!previewUrl) return;
    const a = document.createElement('a');
    a.href = previewUrl;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    toast.success('Natija rasmi muvaffaqiyatli yuklab olindi!');
  }, [previewUrl, fileName, toast]);

  if (!isOpen) return null;

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(effectiveShareUrl);
      setCopied(true);
      toast.success("Taklif havolasi nusxalandi! Do'stlaringizga yuborishingiz mumkin.");
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      toast.error("Havolani nusxalab bo'lmadi. Qo'lda nusxalang.");
    }
  };

  const handleShare = async () => {
    if (!cardBlob) return;
    try {
      const file = new File([cardBlob], fileName, { type: 'image/png' });
      if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: `${studentName} — ${title} natijasi`,
          text: defaultShareText,
          url: effectiveShareUrl,
        });
        toast.success('Natija muvaffaqiyatli ulashildi!');
        return;
      }
      handleDownload();
    } catch (err: unknown) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        handleDownload();
      }
    }
  };

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(2, 6, 23, 0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px',
        overflowY: 'auto',
      }}
    >
      <div
        className="modal-card scorecard"
        style={{
          background: 'linear-gradient(180deg, #0F172A 0%, #090D16 100%)',
          border: '1px solid rgba(245, 158, 11, 0.4)',
          borderRadius: 24,
          padding: 24,
          maxWidth: 480,
          width: '100%',
          position: 'relative',
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 40px rgba(245, 158, 11, 0.15)',
        }}
      >
        <button
          type="button"
          onClick={onClose}
          style={{
            position: 'absolute',
            top: 18,
            right: 18,
            background: 'rgba(255, 255, 255, 0.08)',
            border: 'none',
            color: '#94A3B8',
            borderRadius: '50%',
            width: 36,
            height: 36,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          aria-label={t('common_close')}
        >
          <X size={18} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.1))',
              border: '1px solid rgba(245, 158, 11, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
            }}
          >
            🏆
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: '#FFFFFF' }}>
              Natijani Ulashish & Story Card
            </h3>
            <p style={{ margin: 0, fontSize: 12, color: '#94A3B8' }}>
              {effectiveBranch} · {subjInfo.label}
            </p>
          </div>
        </div>

        {/* Canvas preview */}
        <div
          style={{
            borderRadius: 16,
            overflow: 'hidden',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            maxHeight: 340,
            display: 'flex',
            justifyContent: 'center',
            background: '#090D16',
            boxShadow: 'inset 0 0 30px rgba(0,0,0,0.6)',
            marginBottom: 20,
          }}
        >
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={`${studentName} — ${title}`}
              width={CARD_WIDTH}
              height={CARD_HEIGHT}
              decoding="async"
              style={{
                width: '100%',
                height: 'auto',
                maxHeight: 340,
                objectFit: 'contain',
              }}
            />
          ) : (
            <div style={{ height: 340, width: '100%' }} aria-busy="true" />
          )}
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* 1. Telegram Share (Primary Viral CTA) */}
          <a
            href={effectiveTgUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              padding: '13px 20px',
              borderRadius: 14,
              background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
              color: '#FFFFFF',
              fontWeight: 800,
              fontSize: 15,
              textDecoration: 'none',
              boxShadow: '0 8px 24px rgba(2, 132, 199, 0.35)',
            }}
          >
            <Send size={18} />
            <span>✈️ Telegramda Ulashish</span>
          </a>

          {/* 2. Download Story PNG & Download PDF Row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <button
              type="button"
              onClick={handleDownload}
              disabled={!previewUrl}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                padding: '11px 14px',
                borderRadius: 12,
                background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                color: '#0F172A',
                fontWeight: 800,
                fontSize: 13,
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 6px 20px rgba(245, 158, 11, 0.3)',
              }}
            >
              <Download size={16} />
              <span>🖼 Story Card (PNG)</span>
            </button>

            {effectivePdfUrl ? (
              <a
                href={effectivePdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  padding: '11px 14px',
                  borderRadius: 12,
                  background: 'rgba(255, 255, 255, 0.08)',
                  color: '#F8FAFC',
                  fontWeight: 700,
                  fontSize: 13,
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  textDecoration: 'none',
                  cursor: 'pointer',
                }}
              >
                <FileText size={16} color="#38BDF8" />
                <span>📄 PDF Vedomost</span>
              </a>
            ) : (
              <button
                type="button"
                onClick={handleShare}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  padding: '11px 14px',
                  borderRadius: 12,
                  background: 'rgba(255, 255, 255, 0.08)',
                  color: '#F8FAFC',
                  fontWeight: 700,
                  fontSize: 13,
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  cursor: 'pointer',
                }}
              >
                <Share2 size={16} />
                <span>Ulashish</span>
              </button>
            )}
          </div>

          {/* 3. Copy Link with Referral Code */}
          <button
            type="button"
            onClick={handleCopyLink}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              padding: '10px 16px',
              borderRadius: 12,
              background: 'rgba(15, 23, 42, 0.6)',
              border: '1px dashed rgba(245, 158, 11, 0.35)',
              color: '#E2E8F0',
              fontWeight: 600,
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            {copied ? <Check size={14} color="#10B981" /> : <Copy size={14} color="#FBBF24" />}
            <span>{copied ? 'Havola nusxalandi!' : `Referal havola: grandec.uz/join?ref=${refCode}`}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
