import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Billing, PaymentsApi, type PaymentReceiptItem } from '../lib/api';
import { CopyIcon, CreditCardIcon, CheckIcon } from '../components/icons';

// Strictly 3 commercial subscription plans: START / STARTER (15 000), PRO (49 000 - recommended), PREMIUM (60 000)
export const PLAN_PRICES = {
  starter: 5000,
  pro: 49000,
  premium: 89000,
} as const;

const plans: {
  id: 'starter' | 'pro' | 'premium';
  name: string;
  priceKey: 'starter_price' | 'pro_price' | 'premium_price';
  defaultPrice: number;
  emoji: string;
  badgeUz?: string | null;
  badgeRu?: string | null;
  badgeEn?: string | null;
  featuresUz: string[];
  featuresRu: string[];
  featuresEn: string[];
}[] = [
  {
    id: 'starter',
    name: 'START / STARTER',
    priceKey: 'starter_price',
    defaultPrice: 5000,
    emoji: '⚡',
    badgeUz: null,
    badgeRu: null,
    badgeEn: null,
    featuresUz: [
      'Kuniga 5 ta test',
      'Haftasiga 8 ta esse',
      '5 Rasmli esse/hafta',
      '3 Matnli esse/hafta',
      'Matnli esselar orasida 5 soat',
    ],
    featuresRu: [
      '5 тестов в день',
      '8 эссе в неделю',
      '5 фото эссе / неделю',
      '3 текстовых эссе / неделю',
      '5 часов между текстовыми эссе',
    ],
    featuresEn: [
      '5 tests per day',
      '8 essays per week',
      '5 photo essays / week',
      '3 text essays / week',
      '5 hours cooldown between text essays',
    ],
  },
  {
    id: 'pro',
    name: 'PRO',
    priceKey: 'pro_price',
    defaultPrice: 49000,
    emoji: '🚀',
    badgeUz: '⭐ Eng ommabop / Tavsiya etiladi',
    badgeRu: '⭐ Самый популярный / Рекомендуется',
    badgeEn: '⭐ Most Popular / Recommended',
    featuresUz: [
      'Kuniga 1 ta rasmiy Mock test',
      'Haftasiga 15 ta esse baholash',
      'Barcha CBT va Mock testlar',
      "Kunlik 50 ta AI repetitor so'rovi & Tahlil",
      'Qisqa kutish vaqti (cooldownsiz)',
    ],
    featuresRu: [
      '1 официальный Mock тест в день',
      '15 оценок эссе в неделю',
      'Все CBT и Mock тесты',
      '50 запросов к AI-репетитору в день & Аналитика',
      'Короткое время ожидания (без кулдауна)',
    ],
    featuresEn: [
      '1 official Mock test per day',
      '15 essay assessments per week',
      'All CBT and Mock tests',
      '50 AI tutor requests per day & Analytics',
      'Short waiting time (no cooldown)',
    ],
  },
  {
    id: 'premium',
    name: 'PREMIUM',
    priceKey: 'premium_price',
    defaultPrice: 89000,
    emoji: '👑',
    badgeUz: null,
    badgeRu: null,
    badgeEn: null,
    featuresUz: [
      'Cheksiz rasmli va matnli esse baholash (12 mezon)',
      'Cheksiz barcha CBT, Mock testlar va 1v1 Arena',
      '24/7 Cheksiz AI repetitor ("Nega bu xato?")',
      'Rasmiy PDF Sertifikat & Ustoz tekshiruvi',
      "Hech qanday cheklov va cooldown yo'q",
    ],
    featuresRu: [
      'Безлимитная оценка фото и текстовых эссе (12 критериев)',
      'Все CBT, Mock тесты и 1v1 Арена',
      '24/7 Безлимитный AI репетитор ("Почему эта ошибка?")',
      'Официальный PDF Сертификат & Проверка учителем',
      'Без каких-либо ограничений и кулдауна',
    ],
    featuresEn: [
      'Unlimited photo and text essay grading (12 criteria)',
      'All CBT, Mock tests and 1v1 Arena',
      '24/7 Unlimited AI tutor ("Why is this wrong?")',
      'Official PDF Certificate & Teacher review',
      'No restrictions and no cooldown',
    ],
  },
];

export default function Subscribe() {
  const { planId } = useParams();
  const [searchParams] = useSearchParams();
  const planQuery = searchParams.get('plan');
  const { t, lang } = useLang();

  // Selected plan slug: 'starter' | 'pro' | 'premium'
  const [selectedPlan, setSelectedPlan] = useState<'starter' | 'pro' | 'premium'>('pro');
  const [cardInfo, setCardInfo] = useState({
    card_number: '9860 **** **** ****',
    card_holder: 'KOMILJON R',
    starter_price: PLAN_PRICES.starter,
    pro_price: PLAN_PRICES.pro,
    premium_price: PLAN_PRICES.premium,
  });
  const [copied, setCopied] = useState(false);

  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // User receipts history
  const [receipts, setReceipts] = useState<PaymentReceiptItem[]>([]);
  const [loadingReceipts, setLoadingReceipts] = useState(false);

  // Fetch initial card info and user receipts
  useEffect(() => {
    PaymentsApi.cardInfo()
      .then((data) => {
        if (data.card_number) {
          setCardInfo({
            card_number: data.card_number,
            card_holder: data.card_holder,
            starter_price: PLAN_PRICES.starter,
            pro_price: PLAN_PRICES.pro,
            premium_price: PLAN_PRICES.premium,
          });
        }
      })
      .catch(() => {});

    loadReceipts();

    if (planQuery === 'pro' || planQuery === 'premium' || planQuery === 'starter') {
      setSelectedPlan(planQuery);
    } else if (planId) {
      Billing.plans()
        .then((res) => {
          const match = res.results.find(
            (p) => String(p.id) === String(planId) || p.plan_type === planId,
          );
          if (match && match.plan_type === 'premium') {
            setSelectedPlan('premium');
          } else if (match && match.plan_type === 'pro') {
            setSelectedPlan('pro');
          } else if (match && (match.plan_type === 'starter' || match.plan_type === 'start')) {
            setSelectedPlan('starter');
          }
        })
        .catch(() => {});
    }
  }, [planId, planQuery]);

  const loadReceipts = () => {
    setLoadingReceipts(true);
    PaymentsApi.myReceipts()
      .then((res) => setReceipts(res.results))
      .catch(() => {})
      .finally(() => setLoadingReceipts(false));
  };

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleFileChange = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setUploadError('Faqat rasm fayllari (.jpg, .jpeg, .png) qabul qilinadi.');
      return;
    }
    setUploadError(null);
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const currentPrice = PLAN_PRICES[selectedPlan] ?? 49000;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError("Iltimos, to'lov cheki rasmini tanlang.");
      return;
    }

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const price = currentPrice;

    try {
      await PaymentsApi.uploadReceipt(selectedPlan, selectedFile, price);
      setUploadSuccess(
        "To'lov chekingiz qabul qilindi! Admin tekshiruvidan so'ng (odatda 5-15 daqiqa) tarifingiz faollashadi."
      );
      setSelectedFile(null);
      setPreviewUrl(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      loadReceipts();
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Chekni yuklashda xatolik yuz berdi.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ maxWidth: 920, margin: '0 auto', paddingBottom: 60 }}>
      <p style={{ marginBottom: 16 }}>
        <Link to="/plans" className="muted" style={{ textDecoration: 'none' }}>
          ← {t('pay_back_to_plans')}
        </Link>
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(217, 119, 6, 0.1))',
            border: '1px solid rgba(245, 158, 11, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fbbf24',
          }}
        >
          <CreditCardIcon size={22} className="ico" />
        </div>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>{t('sub_page_title')}</h1>
          <p className="muted small" style={{ margin: 0 }}>
            {t('sub_page_subtitle')}
          </p>
        </div>
      </div>

      {/* Step 1: Select Plan */}
      <div className="card" style={{ marginBottom: 20, padding: 24 }}>
        <h2 style={{ fontSize: 18, marginBottom: 16 }}>{t('sub_step1_title')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6" style={{ display: 'grid', gap: 24 }}>
          {plans.map((p) => {
            const isSelected = selectedPlan === p.id;
            const isPro = p.id === 'pro';
            const priceVal = PLAN_PRICES[p.id] ?? p.defaultPrice;
            const features = lang === 'ru' ? p.featuresRu : lang === 'en' ? p.featuresEn : p.featuresUz;
            const badgeText = isPro
              ? (lang === 'ru' ? p.badgeRu : lang === 'en' ? p.badgeEn : p.badgeUz)
              : null;

            return (
              <div
                key={p.id}
                onClick={() => setSelectedPlan(p.id)}
                className={`card ${isPro ? 'border-amber-500/80 shadow-lg' : ''}`}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  padding: 24,
                  borderRadius: 16,
                  cursor: 'pointer',
                  position: 'relative',
                  border: isPro
                    ? (isSelected ? '2px solid #f59e0b' : '2px solid rgba(245, 158, 11, 0.8)')
                    : isSelected
                    ? (p.id === 'starter' ? '2px solid #38bdf8' : '2px solid #10b981')
                    : '1px solid var(--border)',
                  boxShadow: isPro
                    ? (isSelected ? '0 0 25px rgba(245, 158, 11, 0.45)' : '0 0 18px rgba(245, 158, 11, 0.25)')
                    : undefined,
                  background: isPro
                    ? (isSelected ? 'rgba(245, 158, 11, 0.12)' : 'rgba(245, 158, 11, 0.04)')
                    : isSelected
                    ? (p.id === 'starter' ? 'rgba(56, 189, 248, 0.08)' : 'rgba(16, 185, 129, 0.08)')
                    : 'var(--card-2)',
                  transition: 'all 0.2s ease',
                }}
              >
                {badgeText && (
                  <span
                    style={{
                      position: 'absolute',
                      top: -12,
                      right: 16,
                      background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                      color: '#fff',
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '3px 10px',
                      borderRadius: 20,
                      boxShadow: '0 2px 8px rgba(245, 158, 11, 0.4)',
                    }}
                  >
                    {badgeText}
                  </span>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontSize: 32 }}>{p.emoji}</span>
                  {isSelected && (
                    <span
                      className={`badge ${isPro ? 'yellow' : p.id === 'starter' ? '' : 'green'}`}
                      style={{
                        background: isPro
                          ? 'rgba(245, 158, 11, 0.2)'
                          : p.id === 'starter'
                          ? 'rgba(56, 189, 248, 0.2)'
                          : 'rgba(16, 185, 129, 0.2)',
                        color: isPro ? '#fbbf24' : p.id === 'starter' ? '#38bdf8' : '#10b981',
                      }}
                    >
                      {t('sub_plan_selected')}
                    </span>
                  )}
                </div>

                <strong style={{ fontSize: 20, display: 'block', marginBottom: 4 }}>{p.name}</strong>
                <p className="stat-value" style={{ margin: '8px 0 16px', fontSize: 24, color: 'var(--ink)' }}>
                  {priceVal.toLocaleString()}{' '}
                  <span style={{ fontSize: 14, color: 'var(--muted)', fontWeight: 500 }}>{t('sub_per_month')}</span>
                </p>

                <ul className="muted small" style={{ paddingLeft: 18, margin: '0 0 20px', lineHeight: 1.7, flex: 1 }}>
                  {features.map((feat, idx) => (
                    <li key={idx} style={{ marginBottom: 6 }}>
                      {feat}
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  className={`btn sm ${isPro ? 'primary btn-glow' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedPlan(p.id);
                    const step2 = document.getElementById('step-card-info');
                    if (step2) {
                      step2.scrollIntoView({ behavior: 'smooth' });
                    }
                  }}
                  style={{
                    width: '100%',
                    marginTop: 'auto',
                    fontWeight: 700,
                    justifyContent: 'center',
                    textDecoration: 'none',
                    background: isPro ? 'linear-gradient(135deg, #f59e0b, #d97706)' : undefined,
                    color: isPro ? '#fff' : undefined,
                  }}
                >
                  {lang === 'ru' ? 'Оплатить и загрузить чек →' : lang === 'en' ? 'Pay & Upload Receipt →' : "To'lov qilish & Chek yuklash →"}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Step 2: Bank Card Details with 1-click copy */}
      <div id="step-card-info" className="card" style={{ marginBottom: 20, padding: 24 }}>
        <h2 style={{ fontSize: 18, marginBottom: 8 }}>{t('sub_step2_title')}</h2>
        <p className="muted small" style={{ marginBottom: 16 }}>
          {t('sub_step2_hint')}{' '}
          <strong style={{ color: '#fbbf24' }}>{currentPrice.toLocaleString()} {t('sub_per_month').split('/')[0].trim()}</strong>
        </p>

        <div
          style={{
            background: 'linear-gradient(135deg, #1e293b, #0f172a)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: 16,
            padding: 24,
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <span style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: 1.5, color: '#94a3b8' }}>
              Uzcard / Humo
            </span>
            <span style={{ fontSize: 13, color: '#38bdf8', fontWeight: 600 }}>GRAND EDUCATION</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <span
              style={{
                fontSize: 24,
                fontFamily: 'monospace',
                letterSpacing: 2,
                fontWeight: 700,
                color: '#fff',
                userSelect: 'all',
              }}
            >
              {cardInfo.card_number}
            </span>
            <button
              type="button"
              className="btn sm"
              onClick={() => handleCopy(cardInfo.card_number)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                background: copied ? '#10b981' : 'rgba(255, 255, 255, 0.1)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                color: '#fff',
                transition: 'all 0.2s ease',
              }}
            >
              {copied ? (
                <>
                  <CheckIcon size={14} className="ico" /> {t('sub_card_copied')}
                </>
              ) : (
                <>
                  <CopyIcon size={14} className="ico" /> {t('sub_copy_card')}
                </>
              )}
            </button>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20, paddingTop: 16, borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <div>
              <span style={{ fontSize: 11, color: '#94a3b8', display: 'block', textTransform: 'uppercase' }}>{t('sub_card_holder')}</span>
              <strong style={{ fontSize: 14, color: '#f8fafc' }}>{cardInfo.card_holder}</strong>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: 11, color: '#94a3b8', display: 'block', textTransform: 'uppercase' }}>{t('sub_transfer_amount')}</span>
              <strong style={{ fontSize: 16, color: '#fbbf24' }}>{currentPrice.toLocaleString()} {t('sub_per_month').split('/')[0].trim()}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Step 3: Receipt Upload Form */}
      <div className="card" style={{ marginBottom: 24, padding: 24 }}>
        <h2 style={{ fontSize: 18, marginBottom: 8 }}>{t('sub_step3_title')}</h2>
        <p className="muted small" style={{ marginBottom: 16 }}>
          {t('sub_step3_hint')}
        </p>

        {uploadSuccess && (
          <div
            className="badge green"
            style={{
              display: 'block',
              padding: '12px 16px',
              fontSize: 14,
              borderRadius: 8,
              marginBottom: 16,
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#34d399',
            }}
          >
            ✅ {uploadSuccess}
          </div>
        )}

        {uploadError && (
          <div
            className="error"
            style={{
              padding: '10px 14px',
              fontSize: 13,
              borderRadius: 8,
              marginBottom: 16,
            }}
          >
            ❌ {uploadError}
          </div>
        )}

        <form onSubmit={handleSubmit}>
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
                  alt="Chek namunasi"
                  style={{
                    maxHeight: 180,
                    maxWidth: '100%',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                  }}
                />
                <span className="small muted">{t('sub_change_photo')}</span>
              </div>
            ) : (
              <div>
                <span style={{ fontSize: 36, display: 'block', marginBottom: 8 }}>📸</span>
                <strong style={{ fontSize: 16, display: 'block', marginBottom: 4 }}>
                  {t('sub_drop_receipt')}
                </strong>
                <span className="muted small">{t('sub_receipt_formats')}</span>
              </div>
            )}
          </div>

          <button
            type="submit"
            className="btn primary btn-glow"
            disabled={!selectedFile || uploading}
            style={{
              width: '100%',
              padding: '12px 20px',
              fontWeight: 700,
              fontSize: 15,
            }}
          >
            {uploading ? t('sub_uploading') : t('sub_submit_btn')}
          </button>
        </form>
      </div>

      {/* Step 4: User's Receipt History */}
      <div className="card" style={{ padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ fontSize: 18, margin: 0 }}>{t('sub_step4_title')}</h2>
          <button
            type="button"
            className="btn sm ghost"
            onClick={loadReceipts}
            disabled={loadingReceipts}
          >
            Yangilash 🔄
          </button>
        </div>

        {loadingReceipts && <p className="muted small">Yuklanmoqda...</p>}

        {!loadingReceipts && receipts.length === 0 && (
          <p className="muted small" style={{ margin: 0 }}>
            {t('sub_no_receipts')}
          </p>
        )}

        {!loadingReceipts && receipts.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {receipts.map((r) => {
              const statusColor =
                r.status === 'approved' ? '#10b981' : r.status === 'rejected' ? '#ef4444' : '#fbbf24';
              const statusBg =
                r.status === 'approved'
                  ? 'rgba(16, 185, 129, 0.15)'
                  : r.status === 'rejected'
                  ? 'rgba(239, 68, 68, 0.15)'
                  : 'rgba(245, 158, 11, 0.15)';
              const statusText =
                r.status === 'approved' ? t('sub_status_approved') : r.status === 'rejected' ? t('sub_status_rejected') : t('sub_status_pending');

              return (
                <div
                  key={r.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 14,
                    borderRadius: 10,
                    background: 'var(--card-2)',
                    border: '1px solid var(--border)',
                    flexWrap: 'wrap',
                    gap: 10,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    {r.receipt_image_url && (
                      <a href={r.receipt_image_url} target="_blank" rel="noopener noreferrer">
                        <img
                          src={r.receipt_image_url}
                          alt="Chek"
                          style={{
                            width: 44,
                            height: 44,
                            objectFit: 'cover',
                            borderRadius: 6,
                            border: '1px solid var(--border)',
                          }}
                        />
                      </a>
                    )}
                    <div>
                      <strong style={{ fontSize: 14, textTransform: 'capitalize' }}>
                        {r.plan} {t('sub_tariff_label')} — {Number(r.amount).toLocaleString()} {t('sub_per_month').split('/')[0].trim()}
                      </strong>
                      <span className="muted small" style={{ display: 'block' }}>
                        {new Date(r.created_at).toLocaleDateString(lang === 'ru' ? 'ru-RU' : lang === 'en' ? 'en-US' : 'uz-UZ', {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}{' '}
                        · {t('sub_source_label')} {r.source.toUpperCase()}
                      </span>
                      {r.admin_note && (
                        <span style={{ fontSize: 12, color: '#f87171', display: 'block', marginTop: 2 }}>
                          {t('sub_admin_note')} {r.admin_note}
                        </span>
                      )}
                    </div>
                  </div>

                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      padding: '4px 10px',
                      borderRadius: 20,
                      color: statusColor,
                      background: statusBg,
                      border: `1px solid ${statusColor}40`,
                    }}
                  >
                    {statusText}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
