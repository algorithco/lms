import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { Certificates, apiBlob } from '../lib/api';
import type { ApiError } from '../lib/api';

interface VerifyResult {
  valid?: boolean;
  certificate_number?: string;
  student_name?: string;
  course_title?: string;
  test_title?: string;
  percentage?: string | number;
  issued_at?: string;
  status?: string;
  error?: string;
  anti_fraud?: { verified?: boolean; reason?: string };
}

/** Backend verify answers 404 {valid:false} when missing and 422 when the
 *  anti-fraud checksum fails — both arrive here as thrown ApiErrors whose
 *  detail carries the JSON body. Unpack it so invalid certs render a proper
 *  card instead of a raw error string. */
function asVerifyResult(err: unknown): VerifyResult | null {
  const detail = err instanceof Error ? (err as ApiError).detail ?? err.message : '';
  if (!detail) return null;
  try {
    const body = JSON.parse(detail) as VerifyResult;
    if (typeof body === 'object' && body !== null && ('valid' in body || 'error' in body)) {
      return body;
    }
  } catch {
    /* not a JSON body — a real request failure */
  }
  return null;
}

export default function VerifyCertificate() {
  const { number = '' } = useParams();
  const { t } = useLang();
  const { user } = useAuth();
  const [input, setInput] = useState(number);
  const [out, setOut] = useState<VerifyResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [certId, setCertId] = useState<number | null>(null);
  const [downloading, setDownloading] = useState(false);

  const verify = async (num: string) => {
    if (!num.trim()) return;
    setBusy(true);
    setErr(null);
    setOut(null);
    setCertId(null);
    try {
      // GET /api/certificates/verify/<number>/ — public, no auth needed
      // (backend also accepts POST; GET keeps this page bookmarkable).
      setOut((await Certificates.verify(num.trim())) as VerifyResult);
    } catch (e) {
      const structured = asVerifyResult(e);
      if (structured) {
        setOut(structured);
      } else {
        setErr(e instanceof Error ? e.message : t('error'));
      }
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    setInput(number);
    if (number) void verify(number);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [number]);

  // Authenticated download: match the verified number against the user's own
  // certificates (list serializer carries id + certificate_number), then
  // download the PDF with the JWT Bearer header via apiBlob (a plain <a>
  // href could not send it). Teachers/admins or strangers get no button —
  // the backend download view enforces ownership anyway.
  useEffect(() => {
    setCertId(null);
    if (!out?.valid || !user || !out.certificate_number) return;
    Certificates.mine()
      .then((page) => {
        const match = page.results.find(
          (r) => String(r.certificate_number) === String(out.certificate_number),
        );
        if (match && typeof match.id === 'number') setCertId(match.id);
      })
      .catch(() => {
        /* e.g. non-student role — download simply stays hidden */
      });
  }, [out, user]);

  const download = async () => {
    if (certId === null || !out?.certificate_number) return;
    setDownloading(true);
    try {
      const blob = await apiBlob(`/api/certificates/${certId}/download/`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${out.certificate_number}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e) {
      setErr(e instanceof Error ? e.message : t('error'));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card" style={{ maxWidth: 32 * 16 }}>
        <img src="/grandec.png" alt="GRANDEC" className="auth-logo" />
        <h1>{t('cert_verify_title')}</h1>
        <p className="muted">{t('cert_verify_subtitle')}</p>
        <div className="form">
          <div className="floating">
            <input
              id="cert-num"
              placeholder="LMS-2026-XXXXXX"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void verify(input);
              }}
            />
            <label htmlFor="cert-num">LMS-2026-XXXXXX</label>
          </div>
          <button className="btn primary" disabled={busy} onClick={() => verify(input)}>
            {busy ? t('loading') : t('cert_verify_button')}
          </button>
        </div>
        {err && <p className="error">{err}</p>}
        {out && out.valid && (
          <div className="card" style={{ marginTop: 16, textAlign: 'left' }}>
            <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 700, color: '#16a34a' }}>
              ✅ {out.certificate_number}
            </p>
            <dl style={{ margin: 0, display: 'grid', gap: 6, fontSize: 14 }}>
              {out.student_name && (
                <div><dt className="muted small" style={{ display: 'inline' }}>{t('th_student')}: </dt><dd style={{ display: 'inline', margin: 0, fontWeight: 700 }}>{out.student_name}</dd></div>
              )}
              {out.course_title && (
                <div><dt className="muted small" style={{ display: 'inline' }}>{t('th_course')}: </dt><dd style={{ display: 'inline', margin: 0 }}>{out.course_title}</dd></div>
              )}
              {out.test_title && (
                <div><dt className="muted small" style={{ display: 'inline' }}>{t('tests')}: </dt><dd style={{ display: 'inline', margin: 0 }}>{out.test_title}</dd></div>
              )}
              {out.percentage !== undefined && (
                <div><dt className="muted small" style={{ display: 'inline' }}>{t('score')}: </dt><dd style={{ display: 'inline', margin: 0, fontWeight: 700 }}>{String(out.percentage)}%</dd></div>
              )}
              {out.issued_at && (
                <div><dt className="muted small" style={{ display: 'inline' }}>{t('date')}: </dt><dd style={{ display: 'inline', margin: 0 }}>{new Date(out.issued_at).toLocaleDateString()}</dd></div>
              )}
              {out.status && (
                <div><dt className="muted small" style={{ display: 'inline' }}>{t('status')}: </dt><dd style={{ display: 'inline', margin: 0 }}>{out.status}</dd></div>
              )}
            </dl>
            {certId !== null && (
              <button className="btn primary" style={{ marginTop: 12 }} disabled={downloading} onClick={download}>
                {downloading ? t('loading') : t('mc_download')}
              </button>
            )}
          </div>
        )}
        {out && !out.valid && (
          <div className="card" style={{ marginTop: 16 }}>
            <p className="error" style={{ margin: 0 }}>
              ❌ {out.error || t('cert_verify_not_found')}
            </p>
            {out.certificate_number && (
              <p className="muted small" style={{ margin: '8px 0 0' }}>{out.certificate_number}</p>
            )}
          </div>
        )}
        <p className="muted" style={{ marginTop: 16 }}>
          <Link to="/">{t('back_home')}</Link>
        </p>
      </div>
    </div>
  );
}
