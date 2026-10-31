import { useEffect, useRef, useState } from 'react';
import { X, Download, Share2, Award } from 'lucide-react';
import { useToast } from '../context/ToastContext';

interface ScoreCardModalProps {
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
}

export default function ScoreCardModal({
  isOpen,
  onClose,
  title,
  studentName,
  scorePercentage,
  gradeBadge = 'A+ DARAJA',
  correctCount,
  incorrectCount,
  totalQuestions,
  timeSpent = '42 daqiqa',
  date = new Date().toLocaleDateString('uz-UZ'),
}: ScoreCardModalProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [dataUrl, setDataUrl] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (!isOpen) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = 1080;
    const height = 1920;
    canvas.width = width;
    canvas.height = height;

    // 1. Background deep gradient
    const bgGrad = ctx.createLinearGradient(0, 0, width, height);
    bgGrad.addColorStop(0, '#090D16');
    bgGrad.addColorStop(0.5, '#0F172A');
    bgGrad.addColorStop(1, '#05070C');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    // 2. Radial gold glow behind center
    const radial = ctx.createRadialGradient(width / 2, 850, 50, width / 2, 850, 500);
    radial.addColorStop(0, 'rgba(245, 158, 11, 0.15)');
    radial.addColorStop(0.5, 'rgba(217, 119, 6, 0.05)');
    radial.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = radial;
    ctx.fillRect(0, 0, width, height);

    // 3. Ornate Double Gold Borders
    ctx.lineWidth = 4;
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.4)';
    ctx.strokeRect(40, 40, width - 80, height - 80);

    ctx.lineWidth = 1.5;
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.2)';
    ctx.strokeRect(55, 55, width - 110, height - 110);

    // Corner decorative accents
    const corners = [
      [55, 55],
      [width - 55, 55],
      [55, height - 55],
      [width - 55, height - 55],
    ];
    corners.forEach(([x, y]) => {
      ctx.fillStyle = '#F59E0B';
      ctx.beginPath();
      ctx.arc(x, y, 6, 0, Math.PI * 2);
      ctx.fill();
    });

    // 4. Header: Brand Logo & Title
    ctx.textAlign = 'center';

    // Humo / Crown icon mock
    ctx.fillStyle = '#F59E0B';
    ctx.font = '54px sans-serif';
    ctx.fillText('🦅', width / 2, 190);

    ctx.font = '900 48px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#FFFFFF';
    ctx.fillText('GRAND EDUCATION', width / 2, 270);

    ctx.font = '700 22px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#FBBF24';
    ctx.letterSpacing = '6px';
    ctx.fillText('ACADEMIC EDTECH • RASMIY NATIJA', width / 2, 315);
    ctx.letterSpacing = '0px';

    // Divider line
    ctx.beginPath();
    ctx.moveTo(width / 2 - 200, 360);
    ctx.lineTo(width / 2 + 200, 360);
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.3)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // 5. Exam Title Badge
    ctx.font = '600 30px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#94A3B8';
    ctx.fillText(title.length > 40 ? title.slice(0, 38) + '...' : title, width / 2, 440);

    // 6. Student Name
    ctx.font = '900 58px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#FFFFFF';
    const sName = studentName || "O'quvchi";
    ctx.fillText(sName.length > 25 ? sName.slice(0, 24) + '...' : sName, width / 2, 540);

    // 7. Center Massive Score Ring
    const centerX = width / 2;
    const centerY = 820;
    const radius = 220;

    // Outer subtle ring
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius + 20, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.15)';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Gradient main ring
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    const ringGrad = ctx.createLinearGradient(centerX - radius, centerY - radius, centerX + radius, centerY + radius);
    ringGrad.addColorStop(0, '#F59E0B');
    ringGrad.addColorStop(0.5, '#FDE68A');
    ringGrad.addColorStop(1, '#D97706');
    ctx.strokeStyle = ringGrad;
    ctx.lineWidth = 14;
    ctx.stroke();

    // Inner background circle
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius - 8, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
    ctx.fill();

    // Score inside ring
    ctx.font = '900 136px Inter, system-ui, sans-serif';
    const textGrad = ctx.createLinearGradient(centerX, centerY - 60, centerX, centerY + 50);
    textGrad.addColorStop(0, '#FFFFFF');
    textGrad.addColorStop(1, '#FBBF24');
    ctx.fillStyle = textGrad;
    ctx.fillText(`${scorePercentage}%`, centerX, centerY + 45);

    ctx.font = '700 24px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#94A3B8';
    ctx.fillText('UMUMIY NATIJA', centerX, centerY + 105);

    // 8. Grade Badge Pill
    const pillY = 1130;
    const pillW = 460;
    const pillH = 76;
    const pillX = centerX - pillW / 2;

    const pillGrad = ctx.createLinearGradient(pillX, pillY, pillX + pillW, pillY);
    pillGrad.addColorStop(0, '#D97706');
    pillGrad.addColorStop(0.5, '#F59E0B');
    pillGrad.addColorStop(1, '#B45309');

    // Rounded rectangle helper
    ctx.fillStyle = pillGrad;
    ctx.beginPath();
    ctx.roundRect(pillX, pillY, pillW, pillH, 38);
    ctx.fill();

    ctx.font = '900 34px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#0F172A';
    ctx.fillText(gradeBadge, centerX, pillY + 50);

    // 9. Stats Grid
    const statY = 1270;
    const statW = 280;
    const statH = 150;
    const gap = 30;
    const totalW = statW * 3 + gap * 2;
    const startX = (width - totalW) / 2;

    const stats = [
      { label: "TO'G'RI", value: `${correctCount} ta`, color: '#10B981', border: 'rgba(16, 185, 129, 0.3)' },
      { label: "NOTO'G'RI", value: `${incorrectCount} ta`, color: '#F43F5E', border: 'rgba(244, 63, 94, 0.3)' },
      { label: 'SARFLANGAN VAQT', value: timeSpent, color: '#38BDF8', border: 'rgba(56, 189, 248, 0.3)' },
    ];

    stats.forEach((s, idx) => {
      const x = startX + idx * (statW + gap);
      ctx.fillStyle = 'rgba(15, 23, 42, 0.7)';
      ctx.strokeStyle = s.border;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(x, statY, statW, statH, 20);
      ctx.fill();
      ctx.stroke();

      ctx.font = '700 18px Inter, system-ui, sans-serif';
      ctx.fillStyle = '#94A3B8';
      ctx.fillText(s.label, x + statW / 2, statY + 45);

      ctx.font = '900 34px Inter, system-ui, sans-serif';
      ctx.fillStyle = s.color;
      ctx.fillText(s.value, x + statW / 2, statY + 105);
    });

    // 10. Bottom Footer: Verification & CTA
    ctx.beginPath();
    ctx.moveTo(120, 1500);
    ctx.lineTo(width - 120, 1500);
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.2)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Stylized QR code mockup
    const qrX = 140;
    const qrY = 1560;
    const qrSize = 180;
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.roundRect(qrX, qrY, qrSize, qrSize, 20);
    ctx.fill();

    // QR pattern simulation
    ctx.fillStyle = '#0F172A';
    // 3 Corner squares
    ctx.fillRect(qrX + 15, qrY + 15, 45, 45);
    ctx.fillRect(qrX + qrSize - 60, qrY + 15, 45, 45);
    ctx.fillRect(qrX + 15, qrY + qrSize - 60, 45, 45);

    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(qrX + 25, qrY + 25, 25, 25);
    ctx.fillRect(qrX + qrSize - 50, qrY + 25, 25, 25);
    ctx.fillRect(qrX + 25, qrY + qrSize - 50, 25, 25);

    ctx.fillStyle = '#0F172A';
    ctx.fillRect(qrX + 32, qrY + 32, 11, 11);
    ctx.fillRect(qrX + qrSize - 43, qrY + 32, 11, 11);
    ctx.fillRect(qrX + 32, qrY + qrSize - 43, 11, 11);

    // Random QR matrix dots in center
    for (let r = 0; r < 5; r++) {
      for (let c = 0; c < 5; c++) {
        if ((r + c) % 2 === 0) {
          ctx.fillRect(qrX + 75 + c * 15, qrY + 75 + r * 15, 10, 10);
        }
      }
    }

    // CTA Text alongside QR
    ctx.textAlign = 'left';
    ctx.font = '700 32px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#FFFFFF';
    ctx.fillText('Siz ham o\'z bilimingizni', qrX + qrSize + 40, qrY + 55);
    ctx.fillText('sinab ko\'ring!', qrX + qrSize + 40, qrY + 98);

    ctx.font = '900 36px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#F59E0B';
    ctx.fillText('👉 grandec.uz', qrX + qrSize + 40, qrY + 152);

    // Date
    ctx.textAlign = 'center';
    ctx.font = '500 20px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#64748B';
    ctx.fillText(`Sana: ${date} • Rasmiy autentifikatsiyalangan natija`, width / 2, 1830);

    setDataUrl(canvas.toDataURL('image/png'));
  }, [isOpen, title, studentName, scorePercentage, gradeBadge, correctCount, incorrectCount, totalQuestions, timeSpent, date]);

  if (!isOpen) return null;

  const handleDownload = () => {
    if (!dataUrl) return;
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `grandec-score-${scorePercentage}ball.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    toast.success('Natija rasmi muvaffaqiyatli yuklab olindi!');
  };

  const handleShare = async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    try {
      if (navigator.share && canvas.toBlob) {
        canvas.toBlob(async (blob) => {
          if (!blob) {
            handleDownload();
            return;
          }
          const file = new File([blob], `grandec-score-${scorePercentage}ball.png`, {
            type: 'image/png',
          });
          if (navigator.canShare && navigator.canShare({ files: [file] })) {
            await navigator.share({
              files: [file],
              title: `${studentName} — ${title} natijasi`,
              text: `Men GRAND EDUCATION platformasida ${scorePercentage}% natija ko'rsatdim! O'z bilimingizni sinab ko'ring: https://grandec.uz`,
            });
            toast.success('Natija ulashildi!');
            return;
          }
          handleDownload();
        });
      } else {
        handleDownload();
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        handleDownload();
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-md">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl p-5 flex flex-col items-center">
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2 mb-3 text-amber-400 font-bold text-sm">
          <Award className="w-4 h-4" />
          <span>Instagram & Telegram Stories (9:16)</span>
        </div>

        {/* 9:16 Canvas / Image Preview */}
        <div className="w-[270px] h-[480px] rounded-2xl overflow-hidden border-2 border-amber-500/30 shadow-2xl relative bg-slate-950">
          <canvas ref={canvasRef} className="w-full h-full object-contain" />
        </div>

        {/* Actions */}
        <div className="w-full mt-4 flex gap-2">
          <button
            type="button"
            onClick={handleDownload}
            className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-amber-500 to-amber-400 hover:from-amber-400 hover:to-amber-300 text-slate-950 font-black text-xs shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2 transition-all"
          >
            <Download className="w-4 h-4" />
            <span>📥 Rasmni saqlash (.png)</span>
          </button>

          <button
            type="button"
            onClick={handleShare}
            className="flex-1 py-3 px-4 rounded-xl bg-[#229ED9] hover:bg-[#1E8CC2] text-white font-bold text-xs shadow-lg shadow-[#229ED9]/20 flex items-center justify-center gap-2 transition-all"
          >
            <Share2 className="w-4 h-4" />
            <span>✈️ Stories'ga ulashish</span>
          </button>
        </div>
      </div>
    </div>
  );
}
