import { useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export interface TrendPoint {
  date: string;
  attempts: number;
  avg: number;
  certs: number;
  students: number;
  essays: number;
}

export interface TrendLabels {
  attempts?: string;
  avg?: string;
  certs?: string;
  students?: string;
  essays?: string;
}

const SERIES_CONFIG: {
  key: keyof Omit<TrendPoint, 'date'>;
  name: string;
  color: string;
  gradientId: string;
}[] = [
  { key: 'attempts', name: 'Urinishlar', color: '#F59E0B', gradientId: 'gradAttempts' },
  { key: 'avg', name: "O'rtacha ball %", color: '#10B981', gradientId: 'gradAvg' },
  { key: 'certs', name: 'Sertifikatlar', color: '#8B5CF6', gradientId: 'gradCerts' },
  { key: 'students', name: "O'quvchilar", color: '#38BDF8', gradientId: 'gradStudents' },
  { key: 'essays', name: 'AI Esselar', color: '#F43F5E', gradientId: 'gradEssays' },
];

const BENCHMARK_SAMPLE_TREND: TrendPoint[] = [
  { date: '2025-11-01', attempts: 180, avg: 54, certs: 18, students: 120, essays: 65 },
  { date: '2025-12-01', attempts: 320, avg: 61, certs: 34, students: 210, essays: 140 },
  { date: '2026-01-01', attempts: 540, avg: 69, certs: 58, students: 380, essays: 260 },
  { date: '2026-02-01', attempts: 820, avg: 76, certs: 89, students: 560, essays: 420 },
  { date: '2026-03-01', attempts: 1150, avg: 83, certs: 135, students: 780, essays: 610 },
  { date: '2026-04-01', attempts: 1580, avg: 91, certs: 195, students: 1040, essays: 890 },
];

function ModernTooltip({
  active,
  payload,
  label,
  focus,
}: {
  active?: boolean;
  payload?: { name: string; value: number | string; color?: string; dataKey?: string | number }[];
  label?: string;
  focus?: string | null;
}) {
  if (!active || !payload || payload.length === 0) return null;

  const seen = new Set<string>();
  const unique = payload.filter((p) => {
    const k = String(p.dataKey);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });

  const rows = focus ? unique.filter((p) => String(p.dataKey) === focus) : unique;
  if (rows.length === 0) return null;

  const date = label ? new Date(label) : null;
  const title =
    date && !Number.isNaN(date.getTime())
      ? date.toLocaleDateString('uz-UZ', { month: 'long', year: 'numeric' })
      : String(label ?? '');

  return (
    <div
      style={{
        background: 'var(--card)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid var(--border)',
        boxShadow: '0 20px 40px -10px rgba(0, 0, 0, 0.3)',
        borderRadius: 14,
        padding: '12px 16px',
        fontSize: 12,
        minWidth: 180,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(148, 163, 184, 0.12)',
          paddingBottom: 6,
          marginBottom: 8,
        }}
      >
        <span style={{ color: '#94a3b8', fontWeight: 700, fontSize: 11, textTransform: 'capitalize' }}>
          {title}
        </span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 800,
            padding: '2px 6px',
            borderRadius: 6,
            background: 'rgba(245, 158, 11, 0.12)',
            color: '#F59E0B',
          }}
        >
          LMS Live
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {rows.map((p) => (
          <div
            key={String(p.dataKey)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#e2e8f0' }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  background: p.color ?? '#F59E0B',
                  boxShadow: `0 0 8px ${p.color ?? '#F59E0B'}`,
                }}
              />
              <span style={{ fontSize: 12, fontWeight: 500 }}>{p.name}</span>
            </span>
            <span style={{ color: '#f8fafc', fontWeight: 800, fontSize: 13, fontVariantNumeric: 'tabular-nums' }}>
              {Number(p.value).toLocaleString()}
              {String(p.dataKey) === 'avg' ? '%' : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TrendChart({
  data,
  labels,
}: {
  data: TrendPoint[];
  labels?: TrendLabels;
  emptyText?: string;
}) {
  const [selectedRange, setSelectedRange] = useState<'6m' | '12m'>('12m');
  const [activeMetric, setActiveMetric] = useState<string | null>(null);
  const [hoveredMetric, setHoveredMetric] = useState<string | null>(null);

  const series = useMemo(
    () =>
      SERIES_CONFIG.map((s) => ({
        ...s,
        name: labels?.[s.key] ?? s.name,
      })),
    [labels],
  );

  const isBenchmark = !data || data.length === 0;
  const filteredData = useMemo(() => {
    const source = isBenchmark ? BENCHMARK_SAMPLE_TREND : data;
    if (selectedRange === '6m') {
      return source.slice(-6);
    }
    return source;
  }, [data, isBenchmark, selectedRange]);

  const wrapRef = useRef<HTMLDivElement | null>(null);
  const rafRef = useRef(0);

  const handleMouseMove = (e: ReactMouseEvent<HTMLDivElement>) => {
    if (activeMetric) return; // If pinned, don't auto-switch
    const wrap = wrapRef.current;
    if (!wrap) return;
    const { clientX, clientY } = e;
    cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      const curves = wrap.querySelectorAll<SVGGeometryElement>('.recharts-area-curve');
      let best: string | null = null;
      let bestD = 40;
      curves.forEach((path) => {
        const ctm = path.getScreenCTM();
        if (!ctm) return;
        let p: DOMPoint;
        try {
          p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
        } catch {
          return;
        }
        const len = path.getTotalLength();
        const steps = 24;
        for (let i = 0; i <= steps; i++) {
          const pt = path.getPointAtLength((len * i) / steps);
          const d = Math.hypot(pt.x - p.x, pt.y - p.y);
          if (d < bestD) {
            bestD = d;
            const seriesName = path.getAttribute('name');
            best = series.find((s) => s.name === seriesName)?.key ?? null;
          }
        }
      });
      setHoveredMetric(best);
    });
  };

  const handleMouseLeave = () => {
    cancelAnimationFrame(rafRef.current);
    setHoveredMetric(null);
  };

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

// Benchmark fallback is used when live data is empty

  const effectiveFocus = activeMetric || hoveredMetric;

  return (
    <div
      role="region"
      aria-label="Platforma o'sishi ko'rsatkichlari grafigi"
      className="glass-card"
      style={{
        width: '100%',
        background: 'var(--card)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid var(--border)',
        borderRadius: 20,
        padding: '20px 20px 16px',
        boxShadow: '0 20px 48px -12px rgba(0, 0, 0, 0.3)',
      }}
    >
      <style>{`
        .trend-area .recharts-area-curve,
        .trend-area .recharts-area-area {
          transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1), stroke-opacity 0.3s ease, fill-opacity 0.3s ease;
        }
        .metric-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          min-height: 44px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          background: var(--card-2);
          border: 1px solid var(--border);
          color: #94a3b8;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .metric-pill:hover {
          background: rgba(30, 41, 59, 0.8);
          color: #f8fafc;
          border-color: rgba(148, 163, 184, 0.25);
        }
        .metric-pill.is-active {
          background: rgba(245, 158, 11, 0.15);
          border-color: rgba(245, 158, 11, 0.5);
          color: #f8fafc;
          box-shadow: 0 0 16px rgba(245, 158, 11, 0.15);
        }
        .range-toggle-btn {
          padding: 4px 10px;
          min-height: 44px;
          display: inline-flex;
          align-items: center;
          border-radius: 8px;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
          border: none;
          background: transparent;
          color: #94a3b8;
          transition: all 0.2s ease;
        }
        .range-toggle-btn.active {
          background: rgba(245, 158, 11, 0.2);
          color: #F59E0B;
        }
      `}</style>

      {/* Benchmark Notice if demo data is shown */}
      {isBenchmark && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 12px', borderRadius: 999, background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.35)', color: '#F59E0B', fontSize: 11, fontWeight: 800, marginBottom: 12 }}>
          <span>📈 O'sish dinamikasi simulyatsiyasi (B1 ➔ C1 / Milliy Sertifikat A daraja)</span>
        </div>
      )}

      {/* Header controls: Metric selector & Time range */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 16,
          paddingBottom: 14,
          borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
          <button
            type="button"
            className={`metric-pill ${activeMetric === null ? 'is-active' : ''}`}
            onClick={() => setActiveMetric(null)}
            aria-label="Barcha metrikalarni ko'rsatish"
          >
            <span>Barchasi</span>
          </button>
          {series.map((s) => {
            const isSelected = activeMetric === s.key;
            return (
              <button
                key={s.key}
                type="button"
                className={`metric-pill ${isSelected ? 'is-active' : ''}`}
                onClick={() => setActiveMetric(isSelected ? null : s.key)}
                onMouseEnter={() => !activeMetric && setHoveredMetric(s.key)}
                onMouseLeave={() => !activeMetric && setHoveredMetric(null)}
                aria-label={`${s.name} bo'yicha filtrlash`}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    background: s.color,
                    boxShadow: isSelected ? `0 0 8px ${s.color}` : 'none',
                  }}
                />
                <span>{s.name}</span>
              </button>
            );
          })}
        </div>

        {/* Range switcher */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: 3,
            borderRadius: 10,
            background: 'rgba(30, 41, 59, 0.6)',
            border: '1px solid rgba(148, 163, 184, 0.12)',
          }}
        >
          <button
            type="button"
            className={`range-toggle-btn ${selectedRange === '6m' ? 'active' : ''}`}
            onClick={() => setSelectedRange('6m')}
            aria-label="So'nggi 6 oylik ma'lumotlar"
          >
            6 oy
          </button>
          <button
            type="button"
            className={`range-toggle-btn ${selectedRange === '12m' ? 'active' : ''}`}
            onClick={() => setSelectedRange('12m')}
            aria-label="So'nggi 12 oylik ma'lumotlar"
          >
            12 oy
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div
        style={{ width: '100%', height: 'clamp(320px, 38vw, 440px)' }}
        ref={wrapRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={filteredData}
            margin={{ left: 0, right: 10, top: 12, bottom: 4 }}
            className="trend-area"
          >
            <defs>
              <linearGradient id="gradAttempts" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradAvg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10B981" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradCerts" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradStudents" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#38BDF8" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradEssays" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#F43F5E" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid vertical={false} stroke="rgba(148, 163, 184, 0.08)" strokeDasharray="3 3" />

            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tickMargin={12}
              interval="preserveStartEnd"
              tickFormatter={(value: string) => {
                const d = new Date(value);
                return d.toLocaleDateString('uz-UZ', { month: 'short' });
              }}
              tick={{ fill: '#94a3b8', fontSize: 12, fontWeight: 500 }}
              padding={{ left: 12, right: 12 }}
            />

            <YAxis
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
              tick={{ fill: '#94a3b8', fontSize: 12, fontWeight: 500 }}
              tickFormatter={(value: number) => Number(value).toLocaleString()}
              width={42}
            />

            <Tooltip
              content={<ModernTooltip focus={effectiveFocus} />}
              cursor={{ stroke: 'rgba(245, 158, 11, 0.4)', strokeWidth: 1.5, strokeDasharray: '4 4' }}
            />

            {series.map((s) => {
              const isDim = effectiveFocus !== null && effectiveFocus !== s.key;
              const isHighlighted = effectiveFocus === s.key;
              return (
                <Area
                  key={s.key}
                  dataKey={s.key}
                  name={s.name}
                  type="monotone"
                  stroke={s.color}
                  strokeWidth={isHighlighted ? 3 : 2}
                  strokeOpacity={isDim ? 0.12 : 1}
                  fill={`url(#${s.gradientId})`}
                  fillOpacity={isDim ? 0.02 : isHighlighted ? 0.45 : 0.22}
                  activeDot={{
                    r: 5,
                    fill: '#090d16',
                    stroke: s.color,
                    strokeWidth: 2.5,
                  }}
                  dot={false}
                  animationDuration={1000}
                  animationEasing="ease-out"
                />
              );
            })}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
