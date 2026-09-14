import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { apiBlob, Certificates } from '../lib/api';
import { listCertsPage, num, type CertListItem } from '../lib/testing';

/**
 * Student certificates — GET /api/certificates/my-certificates/ (JWT),
 * download via Certificates.downloadUrl (JWT blob fetch), public verify
 * via Certificates.verify (supports GET, no auth).
 */
export default function MyCertificates() {
  const { t } = useLang();
  const [certs, setCerts] = useState<CertListItem[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [verifyNum, setVerifyNum] = useState('');
  const [verifyOut, setVerifyOut] = useState<Record<string, unknown> | null>(null);
  const [verifyErr, setVerifyErr] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [downloading, setDownloading] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    listCertsPage(page)
      .then((p) => {
        if (cancelled) return;
        setCerts((p.results ?? []) as CertListItem[]);
        setCount(p.count ?? 0);
        setHasNext(Boolean(p.next));
        setHasPrev(Boolean(p.previous));
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : t('err_retry_js'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const download = async (id: number) => {
    setDownloading(id);
    setErr(null);
    try {
      // JWT Bearer via apiBlob so 401 refresh-and-retry works; plain <a href> can't send it.
      const blob = await apiBlob(`/api/certificates/${id}/download/`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${String(certs.find((x) => x.id === id)?.certificate_number ?? `cert-${id}`)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : t('err_retry_js');
      // CertificateDownloadView returns 202 when PDF not yet generated
      if (msg.includes('202') || msg.toLowerCase().includes('pending')) {
        setErr(t('take_cert_pending'));
      } else {
        setErr(msg);
      }
    } finally {
      setDownloading(null);
    }
  };

  const verify = async () => {
    const v = verifyNum.trim();
    if (!v) return;
    setVerifying(true);
    setVerifyErr(null);
    setVerifyOut(null);
    try {
      const out = await Certificates.verify(v);
      setVerifyOut(out as Record<string, unknown>);
    } catch (e) {
      setVerifyErr(e instanceof Error ? e.message : t('err_retry_js'));
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div>
      <h1>
        {t('my_certificates')} ({count})
      </h1>
      <p className="muted">{t('my_certificates_hint')}</p>

      {loading && <p className="muted">{t('loading')}</p>}
      {err && <p className="error">{err}</p>}

      {!loading && !err && certs.length === 0 && (
        <div className="card">
          <h3>{t('mc_none_title')}</h3>
          <p className="muted">{t('mc_none_hint')}</p>
          <Link className="btn primary" to="/tests">
            {t('view_tests')}
          </Link>
        </div>
      )}

      <div className="grid">
        {certs.map((c) => (
          <div key={c.id} className="card">
            <strong>{String(c.course_title ?? c.test_title ?? `#${c.id}`)}</strong>
            {c.test_title && c.course_title && (
              <span className="muted small">{String(c.test_title)}</span>
            )}
            <span className="muted small">
              {t('mc_number')} {String(c.certificate_number ?? '—')}
            </span>
            <span className="muted small">
              {t('score')}: {num(c.percentage, 0)}%
            </span>
            <span className="muted small">
              {t('date')}:{' '}
              {c.issued_at
                ? new Date(String(c.issued_at)).toLocaleDateString()
                : '—'}
              {' · '}
              <span className="badge green">{String(c.status ?? '')}</span>
            </span>
            <button
              className="btn sm"
              disabled={downloading === c.id}
              onClick={() => download(c.id)}
            >
              {downloading === c.id ? t('loading') : t('mc_download')}
            </button>
          </div>
        ))}
      </div>

      {(hasNext || hasPrev) && (
        <div className="toolbar" style={{ marginTop: 16 }}>
          <button
            className="btn sm"
            disabled={!hasPrev}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← {t('back')}
          </button>
          <span className="muted small">{page}</span>
          <button
            className="btn sm"
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            {t('next')} →
          </button>
        </div>
      )}

      <h2>{t('take_verify_title')}</h2>
      <div className="form">
        <label>
          {t('take_verify_label')}
          <input
            value={verifyNum}
            onChange={(e) => setVerifyNum(e.target.value)}
            placeholder="LMS-2026-XXXXXX"
          />
        </label>
        <div className="toolbar">
          <button className="btn" disabled={verifying || !verifyNum.trim()} onClick={verify}>
            {verifying ? t('loading') : t('take_verify_btn')}
          </button>
          <Link className="btn ghost" to={`/verify/${verifyNum.trim()}`}>
            {t('take_verify_open')}
          </Link>
        </div>
        {verifyErr && <p className="error">{verifyErr}</p>}
        {verifyOut && (
          <div className="card">
            <p>
              <span className={`badge ${verifyOut.valid ? 'green' : 'rose'}`}>
                {verifyOut.valid ? t('status_passed') : t('status_failed')}
              </span>{' '}
              <strong>{String(verifyOut.certificate_number ?? '')}</strong>
            </p>
            <p className="muted small">
              {String(verifyOut.student_name ?? '')} ·{' '}
              {String(verifyOut.test_title ?? verifyOut.course_title ?? '')} ·{' '}
              {String(verifyOut.percentage ?? '')}%
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
