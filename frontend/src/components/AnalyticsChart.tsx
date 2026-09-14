import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export interface AnalyticsPoint {
  date: string;
  attempts: number;
  avg: number;
}

function weekLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const end = new Date(date);
  end.setDate(date.getDate() + 6);
  if (date.getMonth() === end.getMonth()) {
    return `${date.toLocaleDateString(undefined, { month: 'long' })} ${date.getDate()}-${end.getDate()}, ${end.getFullYear()}`;
  }
  return `${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} - ${end.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`;
}

function DarkTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number | string }[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
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
      <p style={{ margin: '0 0 6px', color: '#b8b8b8', fontWeight: 700 }}>
        {label ? weekLabel(String(label)) : ''}
      </p>
      {payload.map((p) => (
        <p key={p.name} style={{ margin: '2px 0', color: '#ffffff' }}>
          {p.name}: <b style={{ color: '#FACC15' }}>{Number(p.value).toLocaleString()}</b>
        </p>
      ))}
    </div>
  );
}

export default function AnalyticsChart({
  data,
  attemptsLabel = 'Urinishlar',
  avgLabel = "O'rtacha %",
}: {
  data: AnalyticsPoint[];
  attemptsLabel?: string;
  avgLabel?: string;
}) {
  const tickDates = data
    .filter((_, i) => i % Math.max(1, Math.floor(data.length / 7)) === 0)
    .map((d) => d.date);

  return (
    <div style={{ width: '100%', height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ left: 4, right: 4, top: 12, bottom: 4 }}
        >
          <CartesianGrid vertical={false} stroke="#2b2b2b" />

          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tickMargin={12}
            interval="preserveStartEnd"
            ticks={tickDates}
            tickFormatter={(value: string) =>
              new Date(value).toLocaleDateString(undefined, {
                day: 'numeric',
                month: 'short',
              })
            }
            tick={{ fill: '#b8b8b8', fontSize: 12 }}
          />

          <YAxis
            yAxisId="left"
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
            tick={{ fill: '#b8b8b8', fontSize: 12 }}
            tickFormatter={(value: number) => Number(value).toLocaleString()}
            width={40}
          />

          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, 100]}
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#b8b8b8', fontSize: 12 }}
            width={36}
          />

          <Tooltip
            content={<DarkTooltip />}
            cursor={{ fill: 'rgba(250,204,21,.08)' }}
          />

          <Bar
            yAxisId="left"
            name={attemptsLabel}
            dataKey="attempts"
            fill="#EAB308"
            maxBarSize={14}
            radius={[4, 4, 0, 0]}
          />
          <Line
            yAxisId="right"
            name={avgLabel}
            dataKey="avg"
            type="monotone"
            stroke="#22D3EE"
            strokeWidth={2}
            strokeDasharray="0.1 8"
            strokeLinecap="round"
            activeDot={false}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
