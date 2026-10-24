import { useState, useRef, useEffect } from 'react';
import type { FormEvent, DragEvent } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { PaymentsApi } from '../lib/api';
import { CreditCardIcon, CheckIcon, CopyIcon } from '../components/icons';

export const PLAN_PRICES = {
  starter: 5000,
  pro: 49000,
  premium: 89000,
} as const;

export default function Pricing() {
  const { t } = useLang();
  const [selectedPlan, setSelectedPlan] = useState<'starter' | 'pro' | 'premium'>('pro');
  const [cardInfo, setCardInfo] = useState<{
    card_number: string;
    card_holder: string;
  }>({
    card_number: '9860 **** **** ****',
    card_holder: 'KOMILJON R',
  });
  const [copied, setCopied] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState<boolean | null>(null);
  const [isBanned, setIsBanned] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    PaymentsApi.cardInfo()
      .then((data) => {
        if (data) {
          setCardInfo({
            card_number: data.card_number || '9860 **** **** ****',
            card_holder: data.card_holder || 'KOMILJON R',
          });
        }
      })
      .catch(() => {});
  }, []);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text.replace(/\s+/g, ''));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFileChange = (file: File | null) => {
    if (!file) return;
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setResultMessage(null);
    setIsSuccess(null);
    setIsBanned(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleVerifySubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setResultMessage("Iltimos, to'lov cheki rasmini tanlang.");
      setIsSuccess(false);
      return;
    }

    setUploading(true);
    setResultMessage(null);
    setIsSuccess(null);
    setIsBanned(false);

    try {
      const res = await PaymentsApi.verifyReceipt(selectedPlan, selectedFile);
      if (res.success) {
        setIsSuccess(true);
        setResultMessage(res.message);
        setSelectedFile(null);
        setPreviewUrl(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
      } else {
        setIsSuccess(false);
        setIsBanned(Boolean(res.is_banned));
        setResultMessage(res.message);
      }
    } catch (err: unknown) {
      setIsSuccess(false);
      const errMsg = err instanceof Error ? err.message : "Chekni tekshirishda xatolik yuz berdi.";
      if (errMsg.includes('403') || errMsg.toLowerCase().includes('bloklandi')) {
        setIsBanned(true);
      }
      setResultMessage(errMsg);
    } finally {
      setUploading(false);
    }
  };

  const currentPrice = PLAN_PRICES[selectedPlan];

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '24px 16px 60px' }}>
      <p style={{ marginBottom: 16 }}>
        <Link to="/plans" className="muted" style={{ textDecoration: 'none' }}>
          ← {t('pay_back_to_plans')}
        </Link>
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 14,
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.15))',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fbbf24',
          }}
        >
          <CreditCardIcon size={24} className="ico" />
        </div>
        <div>
          <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800 }}>Tariflar & To'lov (Vision AI Skaner)</h1>
          <p className="muted small" style={{ margin: 0 }}>
            To'lov chekini yuboring — Vision AI 3 soniyada tekshirib tarifni avtomatik faollashtiradi
          </p>
        </div>
      </div>

      {/* Pricing Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 24 }}>
        {/* Starter */}
        <div
          onClick={() => setSelectedPlan('starter')}
          className={`card ${selectedPlan === 'starter' ? 'card-selected' : ''}`}
          style={{
            cursor: 'pointer',
            padding: 24,
            borderRadius: 16,
            border: selectedPlan === 'starter' ? '2px solid #38bdf8' : '1px solid var(--border)',
            background: selectedPlan === 'starter' ? 'rgba(56, 189, 248, 0.04)' : 'var(--card)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 32 }}>⚡</span>
            {selectedPlan === 'starter' && <span className="badge" style={{ background: '#38bdf8', color: '#000' }}>Tanlangan</span>}
          </div>
          <strong style={{ fontSize: 20 }}>STARTER</strong>
          <p style={{ fontSize: 24, fontWeight: 700, margin: '8px 0 16px', color: 'var(--ink)' }}>
            5 000 <span style={{ fontSize: 14, color: 'var(--muted)' }}>so'm / oy</span>
          </p>
          <ul className="muted small" style={{ paddingLeft: 18, lineHeight: 1.7, margin: '0 0 16px' }}>
            <li>Kuniga 5 ta test</li>
            <li>Haftasiga 3 ta esse tekshirish</li>
            <li>AI tahlil va xatolar hisoboti</li>
          </ul>
        </div>

        {/* PRO */}
        <div
          onClick={() => setSelectedPlan('pro')}
          className={`card ${selectedPlan === 'pro' ? 'card-selected' : ''}`}
          style={{
            cursor: 'pointer',
            padding: 24,
            borderRadius: 16,
            border: selectedPlan === 'pro' ? '2px solid #fbbf24' : '1px solid var(--border)',
            background: selectedPlan === 'pro' ? 'rgba(245, 158, 11, 0.05)' : 'var(--card)',
            position: 'relative',
          }}
        >
          <span style={{ position: 'absolute', top: -10, right: 16, background: '#f59e0b', color: '#000', fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10 }}>
            TAVSIYA ETILADI
          </span>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 32 }}>🚀</span>
            {selectedPlan === 'pro' && <span className="badge yellow">Tanlangan</span>}
          </div>
          <strong style={{ fontSize: 20 }}>PRO</strong>
          <p style={{ fontSize: 24, fontWeight: 700, margin: '8px 0 16px', color: 'var(--ink)' }}>
            49 000 <span style={{ fontSize: 14, color: 'var(--muted)' }}>so'm / oy</span>
          </p>
          <ul className="muted small" style={{ paddingLeft: 18, lineHeight: 1.7, margin: '0 0 16px' }}>
            <li>30 kun cheksiz testlar va Mock testlar</li>
            <li>Haftasiga 15 ta chuqur esse baholash</li>
            <li>Kunlik 50 ta AI repetitor so'rovi</li>
            <li>IELTS & CEFR simulyatsiyasi</li>
          </ul>
        </div>

        {/* PREMIUM */}
        <div
          onClick={() => setSelectedPlan('premium')}
          className={`card ${selectedPlan === 'premium' ? 'card-selected' : ''}`}
          style={{
            cursor: 'pointer',
            padding: 24,
            borderRadius: 16,
            border: selectedPlan === 'premium' ? '2px solid #10b981' : '1px solid var(--border)',
            background: selectedPlan === 'premium' ? 'rgba(16, 185, 129, 0.04)' : 'var(--card)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 32 }}>👑</span>
            {selectedPlan === 'premium' && <span className="badge green">Tanlangan</span>}
          </div>
          <strong style={{ fontSize: 20 }}>PREMIUM</strong>
          <p style={{ fontSize: 24, fontWeight: 700, margin: '8px 0 16px', color: 'var(--ink)' }}>
            89 000 <span style={{ fontSize: 14, color: 'var(--muted)' }}>so'm / oy</span>
          </p>
          <ul className="muted small" style={{ paddingLeft: 18, lineHeight: 1.7, margin: '0 0 16px' }}>
            <li>Cheksiz esse baholash (12 mezon)</li>
            <li>Barcha Mock testlar va Speaking simulyator</li>
            <li>24/7 Shaxsiy AI ustoz</li>
            <li>Rasmiy PDF sertifikatlar</li>
          </ul>
        </div>
      </div>

      {/* Card Info Box */}
      <div className="card" style={{ marginBottom: 24, padding: 24, background: 'linear-gradient(135deg, #1e293b, #0f172a)', color: '#fff', borderRadius: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <span style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 1.5, color: '#94a3b8' }}>
            Uzcard / Humo / Click / Payme
          </span>
          <span style={{ fontSize: 13, color: '#38bdf8', fontWeight: 600 }}>GRAND EDUCATION</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
          <span style={{ fontSize: 24, fontFamily: 'monospace', letterSpacing: 2, fontWeight: 700 }}>
            {cardInfo.card_number}
          </span>
          <button
            type="button"
            className="btn sm"
            onClick={() => handleCopy(cardInfo.card_number)}
            style={{
              background: copied ? '#10b981' : 'rgba(255, 255, 255, 0.1)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              color: '#fff',
            }}
          >
            {copied ? <><CheckIcon size={14} className="ico" /> Nusxalandi</> : <><CopyIcon size={14} className="ico" /> Nusxa olish</>}
          </button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 12 }}>
          <div>
            <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Karta egasi:</span>
            <strong>{cardInfo.card_holder}</strong>
          </div>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>To'lov summasi:</span>
            <strong style={{ color: '#fbbf24', fontSize: 16 }}>{currentPrice.toLocaleString()} so'm</strong>
          </div>
        </div>
      </div>

      {/* Drag & Drop Receipt Verification Form */}
      <div className="card" style={{ padding: 24, borderRadius: 16 }}>
        <h2 style={{ fontSize: 18, marginBottom: 8 }}>📸 To'lov chekini yuklash (Vision AI OCR)</h2>
        <p className="muted small" style={{ marginBottom: 16 }}>
          Click, Payme yoki Uzum ilovasidan to'lov muvaffaqiyatli o'tgan kvitansiyani yuklang.
        </p>

        {isSuccess === true && resultMessage && (
          <div
            style={{
              padding: '14px 18px',
              borderRadius: 10,
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              color: '#34d399',
              marginBottom: 16,
              fontSize: 14,
            }}
            dangerouslySetInnerHTML={{ __html: resultMessage }}
          />
        )}

        {isSuccess === false && resultMessage && (
          <div
            style={{
              padding: '14px 18px',
              borderRadius: 10,
              background: isBanned ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.15)',
              border: isBanned ? '2px solid #ef4444' : '1px solid rgba(245, 158, 11, 0.4)',
              color: isBanned ? '#f87171' : '#fbbf24',
              marginBottom: 16,
              fontSize: 14,
            }}
            dangerouslySetInnerHTML={{ __html: resultMessage }}
          />
        )}

        <form onSubmit={handleVerifySubmit}>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: dragOver ? '2px dashed #fbbf24' : '2px dashed var(--border)',
              borderRadius: 14,
              padding: '36px 20px',
              textAlign: 'center',
              cursor: 'pointer',
              background: dragOver ? 'rgba(245, 158, 11, 0.05)' : 'var(--card-2)',
              transition: 'all 0.2s ease',
              marginBottom: 16,
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/jpg"
              style={{ display: 'none' }}
              onChange={(e) => handleFileChange(e.target.files ? e.target.files[0] : null)}
            />

            {previewUrl ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
                <img
                  src={previewUrl}
                  alt="Chek rasmi"
                  style={{ maxHeight: 200, maxWidth: '100%', borderRadius: 8, border: '1px solid var(--border)' }}
                />
                <span className="small muted">Boshqa rasm tanlash uchun bosing</span>
              </div>
            ) : (
              <div>
                <span style={{ fontSize: 36, display: 'block', marginBottom: 8 }}>📥</span>
                <strong style={{ display: 'block', marginBottom: 4 }}>Chek rasmini bu yerga tashlang yoki bosing</strong>
                <span className="small muted">PNG, JPG formatida (maksimal 5 MB)</span>
              </div>
            )}
          </div>

          <button
            type="submit"
            className="btn primary btn-glow"
            disabled={uploading || !selectedFile}
            style={{ width: '100%', justifyContent: 'center', fontWeight: 700, padding: '12px 20px' }}
          >
            {uploading ? "Vision AI chekni tekshirmoqda..." : "🚀 Chekni tasdiqlash va tarifni faollashtirish"}
          </button>
        </form>
      </div>
    </div>
  );
}
