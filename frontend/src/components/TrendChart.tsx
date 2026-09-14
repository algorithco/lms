import { useEffect, useRef, useState } from 'react';
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

const SERIES: { key: keyof Omit<TrendPoint, 'date'>; name: string; color: string; fill: boolean }[] = [
  { key: 'attempts', name: 'Urinishlar', color: '#FACC15', fill: true },
  { key: 'avg', name: "O'rtacha %", color: '#22D3EE', fill: false },
  { key: 'certs', name: 'Sertifikatlar', color: '#A78BFA', fill: false },
  { key: 'students', name: "O'quvchilar", color: '#F8FAFC', fill: false },
  { key: 'essays', name: 'Esselar', color: '#FB923C', fill: false },
];

function DarkTooltip({
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
  // Dedupe by series (hit-areas share dataKeys) then apply hover focus.
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
      ? date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
      : String(label ?? '');
  return (
    <div
      style={{
        background: '#111111',
        border: '1px solid #2b2b2b',
        borderRadius: 12,
        padding: '10px 14px',
        fontSize: 12,
      }}
    >
      <p style={{ margin: '0 0 6px', color: '#b8b8b8', fontWeight: 700 }}>{title}</p>
      {rows.map((p) => (
        <p key={p.name} style={{ margin: '2px 0', color: '#ffffff' }}>
          <span
            style={{
              display: 'inline-block',
              width: 8,
              height: 8,
              borderRadius: 999,
              background: p.color ?? '#FACC15',
              marginRight: 6,
            }}
          />
          {p.name}: <b>{Number(p.value).toLocaleString()}</b>
        </p>
      ))}
    </div>
  );
}

export interface TrendLabels {
  attempts?: string;
  avg?: string;
  certs?: string;
  students?: string;
  essays?: string;
}

export default function TrendChart({
  data,
  labels,
  emptyText,
}: {
  data: TrendPoint[];
  labels?: TrendLabels;
  emptyText?: string;
}) {
  const series = SERIES.map((s) => ({
    ...s,
    name: labels?.[s.key] ?? s.name,
  }));
  // Hovered series stays vivid, the rest fade — tooltip follows the focus.
  const [focus, setFocus] = useState<string | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const rafRef = useRef(0);

  // Nearest-line hover: stacked fat hit-areas blanket each other (topmost
  // always wins), so instead measure the real cursor distance to each
  // rendered curve and focus the closest one within threshold.
  const handleMove = (e: ReactMouseEvent<HTMLDivElement>) => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const { clientX, clientY } = e;
    cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      const curves = wrap.querySelectorAll<SVGGeometryElement>(
        '.recharts-area-curve',
      );
      let best: string | null = null;
      let bestD = 40; // px — outside this, show everything
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
      setFocus((prev) => (prev === best ? prev : best));
    });
  };

  const handleLeave = () => {
    cancelAnimationFrame(rafRef.current);
    setFocus(null);
  };

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  if (!data || data.length === 0) {
    return <p className="muted">{emptyText ?? '—'}</p>;
  }

  return (
    <div style={{ width: '100%' }}>
      <style>{`
        .trend-area .recharts-area-curve,
        .trend-area .recharts-area-area {
          transition: opacity 0.3s ease, stroke-opacity 0.3s ease, fill-opacity 0.3s ease;
        }
      `}</style>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px 16px',
          justifyContent: 'center',
          marginBottom: 8,
          fontSize: 12,
          fontWeight: 600,
          color: '#b8b8b8',
        }}
      >
        {series.map((s) => (
          <span
            key={s.key}
            onMouseEnter={() => setFocus(s.key)}
            onMouseLeave={() => setFocus(null)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              cursor: 'default',
              opacity: !focus || focus === s.key ? 1 : 0.35,
              transition: 'opacity 0.3s ease',
            }}
          >
            <span
              style={{
                width: 18,
                height: 3,
                borderRadius: 999,
                background: s.color,
                display: 'inline-block',
              }}
            />
            {s.name}
          </span>
        ))}
      </div>
      <div
        style={{ width: '100%', height: 'clamp(340px, 42vw, 480px)' }}
        ref={wrapRef}
        onMouseMove={handleMove}
        onMouseLeave={handleLeave}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ left: 4, right: 8, top: 12, bottom: 4 }}
            className="trend-area"
          >
            <defs>
              <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#FACC15" stopOpacity={0.55} />
                <stop offset="95%" stopColor="#FACC15" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid vertical={false} stroke="#2b2b2b" strokeOpacity={0.6} />

            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tickMargin={12}
              interval="preserveStartEnd"
              tickFormatter={(value: string) =>
                new Date(value).toLocaleDateString(undefined, { month: 'short' })
              }
              tick={{ fill: '#b8b8b8', fontSize: 12 }}
              padding={{ left: 10, right: 10 }}
            />

            <YAxis
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
              tick={{ fill: '#b8b8b8', fontSize: 12 }}
              tickFormatter={(value: number) => Number(value).toLocaleString()}
              width={44}
            />

            <Tooltip
              content={<DarkTooltip focus={focus} />}
              cursor={{ stroke: '#EAB308', strokeWidth: 1 }}
            />

            {series.map((s) => {
              const dim = focus !== null && focus !== s.key;
              return (
                <Area
                  key={s.key}
                  dataKey={s.key}
                  name={s.name}
                  type="monotone"
                  stroke={s.color}
                  strokeWidth={2.5}
                  strokeOpacity={dim ? 0.12 : 1}
                  fill={s.fill ? 'url(#trendFill)' : 'none'}
                  fillOpacity={s.fill ? (dim ? 0.04 : 0.35) : 0}
                  activeDot={{ r: 4, fill: '#111111', stroke: s.color, strokeWidth: 2 }}
                  dot={false}
                  animationDuration={1400}
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
