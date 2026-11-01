import { useEffect, useRef, type ClipboardEvent, type KeyboardEvent } from 'react';

interface OtpInputProps {
  value: string;
  onChange: (value: string) => void;
  onComplete?: (code: string) => void;
  length?: number;
  disabled?: boolean;
  autoFocus?: boolean;
  error?: boolean;
}

export default function OtpInput({
  value,
  onChange,
  onComplete,
  length = 6,
  disabled = false,
  autoFocus = true,
  error = false,
}: OtpInputProps) {
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Split value into individual characters
  const digits = Array.from({ length }).map((_, i) => value[i] || '');

  // Auto-focus first input on mount
  useEffect(() => {
    if (autoFocus && inputRefs.current[0] && !disabled) {
      inputRefs.current[0].focus();
    }
  }, [autoFocus, disabled]);

  const updateValueAtIndex = (index: number, digit: string) => {
    const valChars = value.padEnd(length, ' ').split('');
    valChars[index] = digit;
    // Trim trailing empty spaces
    const nextVal = valChars.join('').replace(/\s+$/, '').slice(0, length);
    onChange(nextVal);

    if (nextVal.length === length && /^\d+$/.test(nextVal)) {
      onComplete?.(nextVal);
    }
  };

  const handleInputChange = (index: number, val: string) => {
    const cleanDigits = val.replace(/\D/g, '');
    if (!cleanDigits) {
      updateValueAtIndex(index, '');
      return;
    }

    if (cleanDigits.length === 1) {
      updateValueAtIndex(index, cleanDigits);
      if (index < length - 1) {
        inputRefs.current[index + 1]?.focus();
        inputRefs.current[index + 1]?.select();
      }
    } else {
      // Multiple digits pasted into a single input field
      handlePastedString(cleanDigits);
    }
  };

  const handlePastedString = (pasted: string) => {
    const clean = pasted.replace(/\D/g, '').slice(0, length);
    if (!clean) return;

    onChange(clean);
    const nextFocusIndex = Math.min(clean.length, length - 1);
    inputRefs.current[nextFocusIndex]?.focus();

    if (clean.length === length) {
      onComplete?.(clean);
    }
  };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text');
    handlePastedString(pastedData);
  };

  const handleKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      if (!digits[index] && index > 0) {
        // Move focus backward and clear previous box
        inputRefs.current[index - 1]?.focus();
        const prevChars = value.padEnd(length, ' ').split('');
        prevChars[index - 1] = '';
        onChange(prevChars.join('').replace(/\s+$/, ''));
      } else {
        // Clear current box
        updateValueAtIndex(index, '');
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      e.preventDefault();
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === 'ArrowRight' && index < length - 1) {
      e.preventDefault();
      inputRefs.current[index + 1]?.focus();
    }
  };

  return (
    <div
      role="group"
      aria-label="OTP verification code"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '6px',
        margin: '12px 0 16px',
      }}
    >
      {digits.map((digit, idx) => {
        const isMiddle = length === 6 && idx === 3;
        const isFilled = Boolean(digit);

        return (
          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {isMiddle && (
              <span
                style={{
                  color: 'var(--muted, #64748b)',
                  fontWeight: 700,
                  fontSize: 18,
                  userSelect: 'none',
                  opacity: 0.5,
                  padding: '0 2px',
                }}
              >
                —
              </span>
            )}
            <input
              ref={(el) => {
                inputRefs.current[idx] = el;
              }}
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete="one-time-code"
              maxLength={1}
              value={digit}
              disabled={disabled}
              onChange={(e) => handleInputChange(idx, e.target.value)}
              onKeyDown={(e) => handleKeyDown(idx, e)}
              onPaste={handlePaste}
              onFocus={(e) => e.target.select()}
              style={{
                width: '44px',
                height: '52px',
                textAlign: 'center',
                fontSize: '22px',
                fontWeight: 700,
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                borderRadius: '12px',
                border: error
                  ? '2px solid #ef4444'
                  : isFilled
                  ? '2px solid rgba(56, 189, 248, 0.7)'
                  : '1.5px solid rgba(148, 163, 184, 0.25)',
                background: error
                  ? 'rgba(239, 68, 68, 0.08)'
                  : isFilled
                  ? 'rgba(56, 189, 248, 0.08)'
                  : 'rgba(15, 23, 42, 0.35)',
                color: error ? '#ef4444' : isFilled ? '#38bdf8' : 'var(--ink, #f1f5f9)',
                outline: 'none',
                boxShadow: isFilled ? '0 0 12px rgba(56, 189, 248, 0.15)' : 'none',
                transition: 'all 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
                cursor: disabled ? 'not-allowed' : 'text',
                opacity: disabled ? 0.6 : 1,
              }}
              onFocusCapture={(e) => {
                if (!error) {
                  e.currentTarget.style.borderColor = '#38bdf8';
                  e.currentTarget.style.boxShadow = '0 0 14px rgba(56, 189, 248, 0.35)';
                  e.currentTarget.style.transform = 'scale(1.04)';
                }
              }}
              onBlurCapture={(e) => {
                e.currentTarget.style.transform = 'scale(1)';
                if (!error) {
                  e.currentTarget.style.borderColor = isFilled
                    ? 'rgba(56, 189, 248, 0.7)'
                    : 'rgba(148, 163, 184, 0.25)';
                  e.currentTarget.style.boxShadow = isFilled
                    ? '0 0 12px rgba(56, 189, 248, 0.15)'
                    : 'none';
                }
              }}
            />
          </div>
        );
      })}
    </div>
  );
}
