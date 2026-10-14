import { useMemo } from 'react';

interface RadarItem {
  id: number;
  name: string;
  percent: number;
  score: string;
}

interface HologramRadarProps {
  items: RadarItem[];
  activeId: number;
  size?: number;
}

export default function HologramRadar3D({ items, activeId, size = 260 }: HologramRadarProps) {
  const center = size / 2;
  const radius = size * 0.4;
  const count = items.length;

  // Calculate polygon points
  const points = useMemo(() => {
    return items.map((item, i) => {
      const angle = (Math.PI * 2 / count) * i - Math.PI / 2;
      const r = radius * (item.percent / 100);
      const x = center + r * Math.cos(angle);
      const y = center + r * Math.sin(angle);
      return { x, y, angle, r, item };
    });
  }, [items, count, center, radius]);

  const polygonPath = useMemo(() => {
    return points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  }, [points]);

  // Concentric guideline rings
  const rings = [0.25, 0.5, 0.75, 1.0];

  return (
    <div
      className="hologram-radar-container"
      style={{
        position: 'relative',
        width: size,
        height: size,
        margin: '0 auto',
        perspective: '800px',
      }}
    >
      <style>{`
        .radar-sweep {
          position: absolute;
          inset: 0;
          border-radius: 50%;
          background: conic-gradient(from 0deg, transparent 0deg, transparent 300deg, rgba(16, 185, 129, 0.25) 360deg);
          animation: radarSpin 6s linear infinite;
          pointer-events: none;
        }
        @keyframes radarSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .hologram-mesh {
          transform: rotateX(24deg) rotateY(0deg);
          transition: transform 0.5s cubic-bezier(0.16, 1, 0.3, 1);
          transform-style: preserve-3d;
        }
        .hologram-mesh:hover {
          transform: rotateX(12deg) rotateY(6deg);
        }
      `}</style>

      {/* 3D Tilted SVG Surface */}
      <div className="hologram-mesh" style={{ width: '100%', height: '100%' }}>
        <div className="radar-sweep" />

        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          style={{ overflow: 'visible' }}
        >
          <defs>
            <radialGradient id="radarFill" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.5" />
              <stop offset="60%" stopColor="#f59e0b" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.1" />
            </radialGradient>
            <filter id="radarGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Guideline Concentric Webs */}
          {rings.map((ringFactor, idx) => (
            <circle
              key={idx}
              cx={center}
              cy={center}
              r={radius * ringFactor}
              fill="none"
              stroke="rgba(148, 163, 184, 0.12)"
              strokeDasharray={idx === rings.length - 1 ? 'none' : '3 3'}
              strokeWidth={idx === rings.length - 1 ? 1.5 : 1}
            />
          ))}

          {/* Axes from center to each criterion */}
          {items.map((_, i) => {
            const angle = (Math.PI * 2 / count) * i - Math.PI / 2;
            const x = center + radius * Math.cos(angle);
            const y = center + radius * Math.sin(angle);
            return (
              <line
                key={i}
                x1={center}
                y1={center}
                x2={x}
                y2={y}
                stroke="rgba(148, 163, 184, 0.14)"
                strokeWidth={1}
              />
            );
          })}

          {/* Data Polygon Shape */}
          <polygon
            points={polygonPath}
            fill="url(#radarFill)"
            stroke="#10b981"
            strokeWidth={2}
            filter="url(#radarGlow)"
            style={{ transition: 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)' }}
          />

          {/* Vertex Points & Active Pulse */}
          {points.map((p) => {
            const isActive = p.item.id === activeId;
            return (
              <g key={p.item.id} style={{ cursor: 'pointer' }}>
                {isActive && (
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={9}
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    opacity={0.8}
                  >
                    <animate
                      attributeName="r"
                      values="6;12;6"
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                    <animate
                      attributeName="opacity"
                      values="0.9;0.2;0.9"
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={isActive ? 5 : 3.5}
                  fill={isActive ? '#f59e0b' : '#10b981'}
                  stroke="#090d16"
                  strokeWidth={1.5}
                  filter="url(#radarGlow)"
                />
              </g>
            );
          })}
        </svg>
      </div>

      {/* Hologram Floating Benchmark Badge */}
      <div
        style={{
          position: 'absolute',
          bottom: 4,
          left: '50%',
          transform: 'translateX(-50%)',
          padding: '3px 10px',
          borderRadius: 8,
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          background: 'rgba(16, 185, 129, 0.14)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          color: '#34d399',
          boxShadow: '0 0 14px rgba(16, 185, 129, 0.25)',
          whiteSpace: 'nowrap',
        }}
      >
        3D Gologramma Tahlili
      </div>
    </div>
  );
}
