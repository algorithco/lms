import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react';
import { CheckIcon, CopyIcon, CreditCardIcon, XIcon, ZapIcon } from './icons';
import { BillingApi, type CardDetailsResponse, type PaymentReceiptItem } from '../lib/api';

export interface CardPaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialTariff?: 'STARTER' | 'PRO' | 'PREMIUM';
  onSuccess?: (receipt: PaymentReceiptItem) => void;
}

const TARIFF_DETAILS = {
  STARTER: {
    id: 'STARTER',
    name: 'Starter',
    price: 7000,
    label: "7 000 so'm",
    tag: 'Boshlang\'ich',
    color: '#38BDF8',
  },
  PRO: {
    id: 'PRO',
    name: 'Pro',
    price: 15000,
    label: "15 000 so'm",
    tag: '⭐ Tavsiya etiladi',
    color: '#F59E0B',
  },
  PREMIUM: {
    id: 'PREMIUM',
    name: 'Premium',
    price: 27000,
    label: "27 000 so'm",
    tag: 'Cheksiz imkoniyat',
    color: '#A855F7',
  },
} as const;

export default function CardPaymentModal({
  isOpen,
  onClose,
  initialTariff = 'PRO',
  onSuccess,
}: CardPaymentModalProps) {
  const [selectedTariff, setSelectedTariff] = useState<'STARTER' | 'PRO' | 'PREMIUM'>(initialTariff);
  const [cardInfo, setCardInfo] = useState<{
    card_number: string;
    card_holder: string;
    starter_price: number;
    pro_price: number;
    premium_price: number;
  }>({
    card_number: '4916 9903 6325 9166',
    card_holder: 'Ro\'ziyev K.',
    starter_price: 7000,
    pro_price: 15000,
    premium_price: 27000,
  });

  const [copied, setCopied] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [submittedReceipt, setSubmittedReceipt] = useState<PaymentReceiptItem | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialTariff) {
      setSelectedTariff(initialTariff);
    }
  }, [initialTariff]);

  useEffect(() => {
    if (!isOpen) return;
    setErrorMsg(null);
    setSubmittedReceipt(null);
    setSelectedFile(null);
    setPreviewUrl(null);

    BillingApi.cardDetails()
      .then((data: CardDetailsResponse) => {
        if (data) {
          setCardInfo({
            card_number: data.card_number || '4916 9903 6325 9166',
            card_holder: data.card_holder || 'Ro\'ziyev K.',
            starter_price: data.starter_price || 7000,
            pro_price: data.pro_price || 15000,
            premium_price: data.premium_price || 27000,
          });
        }
      })
      .catch(() => {
        // Fallback default info is already loaded
      });
  }, [isOpen]);

  if (!isOpen) return null;

  const currentPrice =
    selectedTariff === 'STARTER'
      ? cardInfo.starter_price
      : selectedTariff === 'PREMIUM'
      ? cardInfo.premium_price
      : cardInfo.pro_price;

  const handleCopyCard = async () => {
    try {
      await navigator.clipboard.writeText(cardInfo.card_number.replace(/\s+/g, ''));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = cardInfo.card_number.replace(/\s+/g, '');
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
      setErrorMsg('Faqat rasm fayllari (.jpg, .jpeg, .png) qabul qilinadi.');
      return;
    }
    setErrorMsg(null);
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMsg('Iltimos, to\'lov cheki (kvitansiya) rasmini yuklang.');
      return;
    }

    setUploading(true);
    setErrorMsg(null);

    try {
      const receipt = await BillingApi.uploadReceipt(selectedTariff, selectedFile, currentPrice);
      setSubmittedReceipt(receipt);
      if (onSuccess) {
        onSuccess(receipt);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Chekni yuborishda xatolik yuz berdi. Qayta urinib ko\'ring.';
      setErrorMsg(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 99999,
        background: 'rgba(15, 23, 42, 0.8)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        overflowY: 'auto',
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        style={{
          width: '100%',
          maxWidth: 540,
          background: 'var(--card-2, #FFFFFF)',
          color: 'var(--ink, #0F172A)',
          borderRadius: 28,
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.4)',
          border: '1.5px solid rgba(245, 158, 11, 0.4)',
          position: 'relative',
          padding: '28px 24px',
          animation: 'fadeInScale 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          style={{
            position: 'absolute',
            top: 18,
            right: 18,
            background: 'rgba(100, 116, 139, 0.1)',
            border: 'none',
            color: 'var(--muted, #64748B)',
            cursor: 'pointer',
            padding: 8,
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 0.2s',
          }}
          aria-label="Yopish"
        >
          <XIcon size={20} />
        </button>

        {submittedReceipt ? (
          /* SUCCESS SCREEN */
          <div style={{ textAlign: 'center', padding: '16px 8px' }}>
            <div
              style={{
                width: 76,
                height: 76,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
                color: '#FFFFFF',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 12px 28px -6px rgba(16, 185, 129, 0.45)',
                marginBottom: 18,
              }}
            >
              <CheckIcon size={42} />
            </div>

            <h3
              style={{
                margin: '0 0 10px',
                fontSize: 22,
                fontWeight: 900,
                color: 'var(--ink, #0F172A)',
              }}
            >
              🎉 Chekingiz qabul qilindi!
            </h3>

            <p
              style={{
                margin: '0 auto 20px',
                fontSize: 15,
                color: 'var(--muted, #64748B)',
                lineHeight: 1.6,
                maxWidth: 460,
              }}
            >
              Administrator tekshirguniga qadar sizga <strong>24 SOATLIK PRO TRIAL</strong> taqdim etildi. Hozirdanoq barcha test va AI esselardan cheklovlarsiz foydalanishingiz mumkin!
            </p>

            {/* Status Card */}
            <div
              style={{
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                borderRadius: 18,
                padding: '16px 20px',
                marginBottom: 24,
                textAlign: 'left',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 13 }}>
                <span style={{ color: 'var(--muted, #64748B)' }}>Tanlangan tarif:</span>
                <strong style={{ color: '#F59E0B', fontWeight: 800 }}>{selectedTariff} ({currentPrice.toLocaleString()} so&apos;m)</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 13 }}>
                <span style={{ color: 'var(--muted, #64748B)' }}>Chek raqami:</span>
                <strong>#{submittedReceipt.id}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ color: 'var(--muted, #64748B)' }}>Joriy holat:</span>
                <span
                  style={{
                    background: '#D1FAE5',
                    color: '#065F46',
                    fontWeight: 800,
                    padding: '2px 10px',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                >
                  ⚡️ 24 soatlik PRO Trial faollashdi (Tekshirilmoqda)
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              style={{
                width: '100%',
                padding: '14px 20px',
                borderRadius: 14,
                background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                color: '#FFFFFF',
                fontWeight: 800,
                fontSize: 15,
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 8px 20px -4px rgba(245, 158, 11, 0.4)',
              }}
            >
              Tushunarli, rahmat!
            </button>
          </div>
        ) : (
          /* PAYMENT FORM */
          <div>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 14,
                  background: 'linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%)',
                  border: '1.5px solid #F59E0B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#D97706',
                  boxShadow: '0 8px 18px -4px rgba(245, 158, 11, 0.3)',
                }}
              >
                <CreditCardIcon size={26} />
              </div>
              <div>
                <h3 style={{ margin: '0 0 4px', fontSize: 20, fontWeight: 900 }}>
                  Kartaga to&apos;lov va chek yuklash
                </h3>
                <p style={{ margin: 0, fontSize: 13, color: 'var(--muted, #64748B)' }}>
                  1-klikda nusxalang, to&apos;lang va kvitansiyani yuboring
                </p>
              </div>
            </div>

            {/* Tariff Selector Tabs */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 8,
                marginBottom: 18,
                background: 'rgba(100, 116, 139, 0.06)',
                padding: 6,
                borderRadius: 16,
              }}
            >
              {(['STARTER', 'PRO', 'PREMIUM'] as const).map((tId) => {
                const item = TARIFF_DETAILS[tId];
                const active = selectedTariff === tId;
                const price =
                  tId === 'STARTER'
                    ? cardInfo.starter_price
                    : tId === 'PREMIUM'
                    ? cardInfo.premium_price
                    : cardInfo.pro_price;

                return (
                  <button
                    key={tId}
                    type="button"
                    onClick={() => setSelectedTariff(tId)}
                    style={{
                      border: active ? '1.5px solid #F59E0B' : '1px solid transparent',
                      background: active ? '#FFFFFF' : 'transparent',
                      color: active ? '#0F172A' : 'var(--muted, #64748B)',
                      borderRadius: 12,
                      padding: '10px 8px',
                      cursor: 'pointer',
                      textAlign: 'center',
                      boxShadow: active ? '0 4px 12px rgba(0, 0, 0, 0.08)' : 'none',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 800 }}>{item.name}</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: active ? '#D97706' : 'inherit' }}>
                      {price.toLocaleString()} so&apos;m
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Bank Card Display Banner */}
            <div
              style={{
                background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)',
                color: '#FFFFFF',
                borderRadius: 20,
                padding: '20px 22px',
                boxShadow: '0 12px 28px -6px rgba(15, 23, 42, 0.35)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                marginBottom: 18,
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  top: -20,
                  right: -20,
                  width: 100,
                  height: 100,
                  borderRadius: '50%',
                  background: 'rgba(245, 158, 11, 0.12)',
                  filter: 'blur(20px)',
                }}
              />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span
                    style={{
                      background: '#1A1F71',
                      color: '#FFFFFF',
                      fontWeight: 900,
                      fontStyle: 'italic',
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: 12,
                      letterSpacing: '0.08em',
                      boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
                    }}
                  >
                    VISA
                  </span>
                  <span style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#94A3B8', fontWeight: 700 }}>
                    Xalqaro Visa / Humo / Uzcard
                  </span>
                </div>
                <span
                  style={{
                    background: 'rgba(245, 158, 11, 0.2)',
                    color: '#FBBF24',
                    border: '1px solid rgba(245, 158, 11, 0.4)',
                    padding: '2px 10px',
                    borderRadius: 20,
                    fontSize: 11,
                    fontWeight: 800,
                  }}
                >
                  {selectedTariff}: {currentPrice.toLocaleString()} so&apos;m
                </span>
              </div>

              {/* Card Number & Copy Button */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  background: 'rgba(255, 255, 255, 0.08)',
                  padding: '10px 14px',
                  borderRadius: 14,
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  marginBottom: 14,
                }}
              >
                <span
                  style={{
                    fontFamily: 'monospace, "Courier New", Courier',
                    fontSize: 18,
                    fontWeight: 700,
                    letterSpacing: '0.12em',
                    color: '#F8FAFC',
                  }}
                >
                  {cardInfo.card_number}
                </span>

                <button
                  type="button"
                  onClick={handleCopyCard}
                  style={{
                    background: copied ? '#10B981' : '#F59E0B',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: 10,
                    padding: '8px 14px',
                    fontSize: 12,
                    fontWeight: 800,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    transition: 'all 0.15s ease',
                    flexShrink: 0,
                  }}
                >
                  {copied ? (
                    <>
                      <CheckIcon size={14} />
                      Nusxalandi!
                    </>
                  ) : (
                    <>
                      <CopyIcon size={14} />
                      Nusxalash
                    </>
                  )}
                </button>
              </div>

              {/* Card Holder & Instructions */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', fontSize: 13 }}>
                <div>
                  <div style={{ fontSize: 10, textTransform: 'uppercase', color: '#94A3B8', fontWeight: 700 }}>
                    Karta egasi
                  </div>
                  <div style={{ fontWeight: 800, color: '#F1F5F9', marginTop: 2 }}>
                    {cardInfo.card_holder}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 10, textTransform: 'uppercase', color: '#94A3B8', fontWeight: 700 }}>
                    To&apos;lov summasi
                  </div>
                  <div style={{ fontWeight: 900, color: '#FBBF24', fontSize: 16, marginTop: 2 }}>
                    {currentPrice.toLocaleString()} so&apos;m
                  </div>
                </div>
              </div>
            </div>

            {/* Step Guide Notice */}
            <div
              style={{
                fontSize: 13,
                color: 'var(--muted, #64748B)',
                background: 'rgba(245, 158, 11, 0.05)',
                borderLeft: '3px solid #F59E0B',
                padding: '10px 14px',
                borderRadius: '0 12px 12px 0',
                marginBottom: 18,
                lineHeight: 1.5,
              }}
            >
              💡 Istalgan bank ilovasi (<strong>Click, Payme, Uzum</strong>) orqali ushbu kartaga pul o&apos;tkazing va to&apos;lov kvitansiyasi (chek) skrinshotini pastga yuklang.
            </div>

            {/* Receipt Upload Form */}
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
                  border: dragOver
                    ? '2px dashed #F59E0B'
                    : selectedFile
                    ? '2px solid #10B981'
                    : '2px dashed rgba(100, 116, 139, 0.3)',
                  background: dragOver
                    ? 'rgba(245, 158, 11, 0.05)'
                    : selectedFile
                    ? 'rgba(16, 185, 129, 0.04)'
                    : 'rgba(248, 250, 252, 0.6)',
                  borderRadius: 18,
                  padding: '20px 16px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  marginBottom: 18,
                  transition: 'all 0.2s ease',
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFileChange(e.target.files[0]);
                    }
                  }}
                />

                {previewUrl ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14 }}>
                    <img
                      src={previewUrl}
                      alt="To'lov cheki"
                      style={{
                        width: 56,
                        height: 56,
                        objectFit: 'cover',
                        borderRadius: 12,
                        border: '1px solid #10B981',
                      }}
                    />
                    <div style={{ textAlign: 'left' }}>
                      <div style={{ fontSize: 14, fontWeight: 800, color: '#0F172A' }}>
                        {selectedFile?.name}
                      </div>
                      <div style={{ fontSize: 12, color: '#10B981', fontWeight: 700 }}>
                        ✓ Chek tanlandi ({((selectedFile?.size || 0) / 1024).toFixed(1)} KB)
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--muted, #64748B)', marginTop: 2 }}>
                        Boshqa rasm tanlash uchun bosing
                      </div>
                    </div>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: 32, marginBottom: 6 }}>📸</div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--ink, #0F172A)' }}>
                      To&apos;lov cheki (skrinshot)ni bu yerga tashlang yoki bosing
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--muted, #64748B)', marginTop: 4 }}>
                      JPG, PNG, JPEG formatlar qo&apos;llab-quvvatlanadi
                    </div>
                  </div>
                )}
              </div>

              {errorMsg && (
                <div
                  style={{
                    background: '#FEE2E2',
                    color: '#991B1B',
                    border: '1px solid #F87171',
                    borderRadius: 12,
                    padding: '10px 14px',
                    fontSize: 13,
                    fontWeight: 700,
                    marginBottom: 16,
                  }}
                >
                  ⚠️ {errorMsg}
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={uploading}
                style={{
                  width: '100%',
                  padding: '14px 20px',
                  borderRadius: 14,
                  background: uploading
                    ? '#94A3B8'
                    : 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                  color: '#FFFFFF',
                  fontWeight: 900,
                  fontSize: 15,
                  border: 'none',
                  cursor: uploading ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  boxShadow: uploading ? 'none' : '0 8px 20px -4px rgba(245, 158, 11, 0.4)',
                  transition: 'all 0.15s ease',
                }}
              >
                {uploading ? (
                  <span>Chek yuborilmoqda...</span>
                ) : (
                  <>
                    <ZapIcon size={18} />
                    Chekni yuborish ({currentPrice.toLocaleString()} so&apos;m)
                  </>
                )}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
