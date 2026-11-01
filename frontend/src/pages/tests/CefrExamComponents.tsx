import React, { useState } from 'react';
import {
  Volume2Icon,
  VolumeXIcon,
  PlayIcon,
  PauseIcon,
  CheckIcon,
  MapPinIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from 'lucide-react';

// ============================================================================
// 1. INTERACTIVE COMMUNITY CENTRE PLAN (SVG MAP)
// ============================================================================
export interface AssignedRoomInfo {
  qNum: number;
  placeName: string;
}

interface CommunityCentrePlanSvgProps {
  selectedLetter?: string; // e.g. "D" or "Room D"
  onSelectLetter: (letter: string) => void;
  assignedRooms: Record<string, AssignedRoomInfo>; // e.g. { "D": { qNum: 19, placeName: "Bike racks" } }
  availableLetters?: string[];
}

export const CommunityCentrePlanSvg: React.FC<CommunityCentrePlanSvgProps> = ({
  selectedLetter,
  onSelectLetter,
  assignedRooms,
  availableLetters,
}) => {
  // Normalize selectedLetter (e.g. "Room D" -> "D")
  const activeChar = (selectedLetter || '').replace(/^Room\s+/i, '').trim().toUpperCase();

  // SVG Rooms definition
  const letterRooms: Array<{
    letter: string;
    x: number;
    y: number;
    width: number;
    height: number;
  }> = [
    { letter: 'C', x: 175, y: 40, width: 85, height: 75 },
    { letter: 'E', x: 395, y: 40, width: 80, height: 75 },
    { letter: 'A', x: 165, y: 130, width: 75, height: 85 },
    { letter: 'F', x: 250, y: 130, width: 70, height: 85 },
    { letter: 'B', x: 330, y: 130, width: 70, height: 85 },
    { letter: 'D', x: 40, y: 230, width: 80, height: 75 },
    { letter: 'G', x: 130, y: 230, width: 70, height: 75 },
    { letter: 'H', x: 210, y: 230, width: 70, height: 75 },
  ];

  return (
    <div className="w-full bg-slate-900/90 rounded-2xl border border-slate-700/80 p-4 shadow-xl select-none">
      <div className="flex items-center justify-between pb-3 mb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <MapPinIcon className="h-4 w-4 text-amber-400" />
          <span className="font-bold text-xs uppercase tracking-wider text-slate-200">
            Community Centre Plan (Map)
          </span>
        </div>
        <span className="text-[11px] text-slate-400">
          Xaritadagi harfni bosing yoki yondagi ro'yxatdan tanlang
        </span>
      </div>

      <div className="relative w-full aspect-[620/390] overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <svg
          viewBox="0 0 620 390"
          className="w-full h-full text-slate-100"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Floor Outline */}
          <rect
            x="20"
            y="20"
            width="580"
            height="350"
            rx="12"
            fill="#0b1120"
            stroke="#1e293b"
            strokeWidth="3"
          />

          {/* Grid lines subtle */}
          <line x1="20" y1="120" x2="600" y2="120" stroke="#1e293b" strokeDasharray="4 4" strokeWidth="1" />
          <line x1="20" y1="220" x2="600" y2="220" stroke="#1e293b" strokeDasharray="4 4" strokeWidth="1" />

          {/* FIXED ROOMS (Named) */}
          {/* Medical Centre */}
          <rect x="40" y="40" width="125" height="75" rx="6" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
          <text x="102" y="75" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="700">
            Medical
          </text>
          <text x="102" y="90" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="700">
            Centre
          </text>

          {/* Computer room */}
          <rect x="270" y="40" width="115" height="75" rx="6" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
          <text x="327" y="75" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="700">
            Computer
          </text>
          <text x="327" y="90" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="700">
            room
          </text>

          {/* Gym */}
          <rect x="485" y="40" width="95" height="75" rx="6" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
          <text x="532" y="82" textAnchor="middle" fill="#94a3b8" fontSize="12" fontWeight="700">
            Gym
          </text>

          {/* Baby Care room */}
          <rect x="485" y="125" width="95" height="85" rx="6" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
          <text x="532" y="162" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="700">
            Baby Care
          </text>
          <text x="532" y="177" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="700">
            room
          </text>

          {/* Games room */}
          <rect x="40" y="125" width="115" height="85" rx="6" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
          <text x="97" y="162" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="700">
            Games
          </text>
          <text x="97" y="177" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="700">
            room
          </text>

          {/* Sports Hall */}
          <rect x="410" y="130" width="65" height="175" rx="6" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
          <text x="442" y="210" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="700" transform="rotate(-90 442 210)">
            Sports Hall
          </text>

          {/* Library */}
          <rect x="290" y="230" width="110" height="75" rx="6" fill="#1e293b" stroke="#334155" strokeWidth="1.5" />
          <text x="345" y="272" textAnchor="middle" fill="#94a3b8" fontSize="12" fontWeight="700">
            Library
          </text>

          {/* Reception & Main Entrance */}
          <rect x="130" y="315" width="235" height="48" rx="8" fill="#1e293b" stroke="#475569" strokeWidth="1.5" />
          <text x="247" y="344" textAnchor="middle" fill="#cbd5e1" fontSize="12" fontWeight="800">
            Reception
          </text>
          <polygon points="247,367 241,377 253,377" fill="#38bdf8" />
          <text x="247" y="386" textAnchor="middle" fill="#38bdf8" fontSize="9" fontWeight="800">
            ENTRANCE
          </text>

          {/* INTERACTIVE LETTER ROOMS (A to H) */}
          {letterRooms.map((r) => {
            const isSelected = activeChar === r.letter;
            const assigned = assignedRooms[r.letter];

            return (
              <g
                key={r.letter}
                onClick={() => onSelectLetter(r.letter)}
                className="cursor-pointer transition-transform hover:opacity-90"
              >
                {/* Room Rectangle */}
                <rect
                  x={r.x}
                  y={r.y}
                  width={r.width}
                  height={r.height}
                  rx="6"
                  fill={
                    isSelected
                      ? '#1e3a8a'
                      : assigned
                      ? '#064e3b'
                      : '#0f172a'
                  }
                  stroke={
                    isSelected
                      ? '#60a5fa'
                      : assigned
                      ? '#10b981'
                      : '#475569'
                  }
                  strokeWidth={isSelected ? '2.5' : '1.5'}
                />

                {/* Letter Circle Badge */}
                <circle
                  cx={r.x + r.width / 2}
                  cy={r.y + (assigned ? r.height / 2 - 8 : r.height / 2)}
                  r="15"
                  fill={
                    isSelected
                      ? '#2563eb'
                      : assigned
                      ? '#059669'
                      : '#334155'
                  }
                  stroke={isSelected ? '#93c5fd' : '#64748b'}
                  strokeWidth="1.5"
                />
                <text
                  x={r.x + r.width / 2}
                  y={r.y + (assigned ? r.height / 2 - 4 : r.height / 2 + 4)}
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="13"
                  fontWeight="900"
                >
                  {r.letter}
                </text>

                {/* Assigned Question Tag Badge */}
                {assigned && (
                  <g>
                    <rect
                      x={r.x + 4}
                      y={r.y + r.height - 20}
                      width={r.width - 8}
                      height="15"
                      rx="4"
                      fill="#065f46"
                    />
                    <text
                      x={r.x + r.width / 2}
                      y={r.y + r.height - 9}
                      textAnchor="middle"
                      fill="#6ee7b7"
                      fontSize="9"
                      fontWeight="700"
                    >
                      Q{assigned.qNum}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Quick Letter Bar below map */}
      <div className="flex items-center justify-between gap-1.5 mt-3 pt-3 border-t border-slate-800 overflow-x-auto">
        <span className="text-xs font-semibold text-slate-400 shrink-0 mr-1">Xonalar:</span>
        {(availableLetters && availableLetters.length > 0
          ? availableLetters
          : ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        ).map((letter) => {
          const isSelected = activeChar === letter;
          const assigned = assignedRooms[letter];

          return (
            <button
              key={letter}
              type="button"
              onClick={() => onSelectLetter(letter)}
              className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all flex flex-col items-center justify-center ${
                isSelected
                  ? 'bg-blue-600 text-white ring-2 ring-blue-400 shadow-lg scale-105'
                  : assigned
                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/50'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700'
              }`}
            >
              <span>{letter}</span>
              {assigned && (
                <span className="text-[9px] text-emerald-400 font-normal">Q{assigned.qNum}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

// ============================================================================
// 2. HEADINGS MATCHING VIEW (Reading Part 3 — Canada)
// ============================================================================
interface HeadingsMatchingViewProps {
  currentQNum: number;
  selectedHeadingLetter?: string;
  onSelectHeading: (letter: string) => void;
  headings: Array<{ letter: string; title: string }>;
  usedHeadings: Record<string, number>; // e.g. { "E": 15, "A": 16 }
}

export const HeadingsMatchingView: React.FC<HeadingsMatchingViewProps> = ({
  currentQNum,
  selectedHeadingLetter,
  onSelectHeading,
  headings,
  usedHeadings,
}) => {
  return (
    <div className="space-y-4 pt-2">
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 flex items-center justify-between text-xs">
        <span className="text-slate-300 font-semibold">
          Paragraph {currentQNum} uchun to'g'ri sarlavhani tanlang:
        </span>
        <span className="text-slate-400">Ishlatilganlari chiziladi</span>
      </div>

      <div className="space-y-2">
        {headings.map((h) => {
          const isSelected = selectedHeadingLetter === h.letter;
          const usedByOther = usedHeadings[h.letter] && usedHeadings[h.letter] !== currentQNum;

          return (
            <button
              key={h.letter}
              type="button"
              onClick={() => onSelectHeading(h.letter)}
              className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-center gap-3 group cursor-pointer ${
                isSelected
                  ? 'bg-blue-600/20 border-blue-500 text-white ring-1 ring-blue-500 shadow-md'
                  : usedByOther
                  ? 'bg-slate-900/40 border-slate-800/60 text-slate-500 hover:bg-slate-900'
                  : 'bg-slate-900/90 border-slate-800 text-slate-200 hover:bg-slate-800 hover:border-slate-700'
              }`}
            >
              <span
                className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black shrink-0 ${
                  isSelected
                    ? 'bg-blue-600 text-white shadow-sm'
                    : usedByOther
                    ? 'bg-slate-800 text-slate-500 line-through'
                    : 'bg-slate-800 text-slate-300 border border-slate-700'
                }`}
              >
                {h.letter}
              </span>

              <span
                className={`flex-1 text-sm font-medium ${
                  usedByOther ? 'line-through text-slate-500' : ''
                }`}
              >
                {h.title}
              </span>

              {usedByOther && (
                <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                  Para {usedHeadings[h.letter]}
                </span>
              )}

              {isSelected && <CheckIcon className="h-4 w-4 text-blue-400 shrink-0" />}
            </button>
          );
        })}
      </div>
    </div>
  );
};

// ============================================================================
// 3. MATCHING STATEMENTS (Reading Part 2 — Picnic Spots A–J)
// ============================================================================
interface MatchingStatementsViewProps {
  selectedLetter?: string;
  onSelectLetter: (letter: string) => void;
  statements: Array<{ letter: string; desc: string }>;
}

export const MatchingStatementsView: React.FC<MatchingStatementsViewProps> = ({
  selectedLetter,
  onSelectLetter,
  statements,
}) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="space-y-4 pt-2">
      {/* Horizontal Fast Pill Selector */}
      <div className="space-y-2">
        <label className="text-xs text-slate-400 font-semibold uppercase tracking-wider block">
          Mos keluvchi bayonotni tanlang (A–J):
        </label>
        <div className="grid grid-cols-5 sm:grid-cols-10 gap-2">
          {statements.map((s) => {
            const isSelected = selectedLetter === s.letter;
            return (
              <button
                key={s.letter}
                type="button"
                onClick={() => onSelectLetter(s.letter)}
                className={`py-3 rounded-xl font-bold text-sm transition-all flex flex-col items-center justify-center cursor-pointer ${
                  isSelected
                    ? 'bg-blue-600 text-white ring-2 ring-blue-400 shadow-lg scale-105 font-black'
                    : 'bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-white hover:border-slate-700'
                }`}
                title={s.desc}
              >
                <span>{s.letter}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Currently Selected Statement Summary */}
      {selectedLetter && (
        <div className="bg-blue-950/40 border border-blue-500/30 rounded-xl p-3.5 flex items-start gap-3">
          <span className="w-6 h-6 rounded-md bg-blue-600 text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
            {selectedLetter}
          </span>
          <p className="text-xs sm:text-sm text-blue-200 leading-relaxed">
            {statements.find((s) => s.letter === selectedLetter)?.desc || ''}
          </p>
        </div>
      )}

      {/* Accordion to inspect all A–J statements */}
      <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-900/60">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="w-full p-3 flex items-center justify-between text-xs font-semibold text-slate-300 hover:bg-slate-800/80 transition-colors"
        >
          <span>Barcha fikrlar ro'yxati (Statements A–J)</span>
          {expanded ? <ChevronUpIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
        </button>

        {expanded && (
          <div className="p-3 space-y-2 border-t border-slate-800 max-h-64 overflow-y-auto">
            {statements.map((s) => (
              <div
                key={s.letter}
                onClick={() => onSelectLetter(s.letter)}
                className={`p-2.5 rounded-lg flex items-start gap-2.5 text-xs cursor-pointer transition-colors ${
                  selectedLetter === s.letter
                    ? 'bg-blue-600/20 text-white border border-blue-500/40'
                    : 'text-slate-300 hover:bg-slate-800/60'
                }`}
              >
                <span className="font-bold text-amber-400 shrink-0 w-4">{s.letter}.</span>
                <span className="leading-relaxed">{s.desc}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// 4. TRUE / FALSE / NO INFORMATION (Reading Part 4 Questions 25–29)
// ============================================================================
interface TfngRadioGroupProps {
  value?: string; // "True" | "False" | "No Information"
  onChange: (val: string) => void;
}

export const TfngRadioGroup: React.FC<TfngRadioGroupProps> = ({ value, onChange }) => {
  const options = [
    {
      label: 'True',
      desc: 'Matndagi faktga toʻliq mos keladi',
      activeClass: 'bg-emerald-950/60 border-emerald-500 text-white ring-2 ring-emerald-500/50',
      dotColor: 'bg-emerald-400',
    },
    {
      label: 'False',
      desc: 'Matndagi faktga zid keladi',
      activeClass: 'bg-rose-950/60 border-rose-500 text-white ring-2 ring-rose-500/50',
      dotColor: 'bg-rose-400',
    },
    {
      label: 'No Information',
      desc: 'Matnda bu haqida hech qanday maʼlumot yoʻq',
      activeClass: 'bg-amber-950/60 border-amber-500 text-white ring-2 ring-amber-500/50',
      dotColor: 'bg-amber-400',
    },
  ];

  return (
    <div className="space-y-3 pt-3">
      {options.map((opt) => {
        const isSelected = (value || '').toLowerCase() === opt.label.toLowerCase();

        return (
          <button
            key={opt.label}
            type="button"
            onClick={() => onChange(opt.label)}
            className={`w-full text-left p-4 rounded-2xl border transition-all flex items-center justify-between group cursor-pointer ${
              isSelected
                ? opt.activeClass
                : 'bg-slate-900/90 border-slate-800 text-slate-300 hover:bg-slate-800/80 hover:border-slate-700 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-3.5">
              <span
                className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${
                  isSelected ? 'border-white' : 'border-slate-600 group-hover:border-slate-400'
                }`}
              >
                {isSelected && <span className={`w-3 h-3 rounded-full ${opt.dotColor}`} />}
              </span>
              <div>
                <span className="font-extrabold text-base tracking-wide block">{opt.label}</span>
                <span className="text-xs text-slate-400">{opt.desc}</span>
              </div>
            </div>

            {isSelected && <CheckIcon className="h-5 w-5 text-white shrink-0" />}
          </button>
        );
      })}
    </div>
  );
};

// ============================================================================
// 5. INLINE GAP-FILL INPUT
// ============================================================================
interface InlineGapFillInputProps {
  questionText: string;
  value: string;
  onChange: (val: string) => void;
  onEnterOrTab?: () => void;
  placeholder?: string;
  gapNumber?: number;
}

export const InlineGapFillInput: React.FC<InlineGapFillInputProps> = ({
  questionText,
  value,
  onChange,
  onEnterOrTab,
  placeholder = 'Javobni kiriting...',
  gapNumber,
}) => {
  // Regex to match (9) __________ or [blank-1] or similar
  const gapRegex = /(?:\(\d+\)\s*_{2,}|_{3,}|\[blank[^\]]*\])/i;
  const match = questionText.match(gapRegex);

  if (!match) {
    return (
      <div className="space-y-3 pt-2">
        <p className="text-slate-200 text-base">{questionText}</p>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === 'Tab') {
              if (onEnterOrTab) onEnterOrTab();
            }
          }}
          placeholder={placeholder}
          className="w-full bg-slate-900 border-2 border-slate-700 rounded-xl px-4 py-3 text-white text-base focus:border-amber-400 focus:outline-none"
        />
      </div>
    );
  }

  const parts = questionText.split(gapRegex);
  const prefix = parts[0] || '';
  const suffix = parts.slice(1).join(' ') || '';

  return (
    <div className="pt-3">
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 text-base sm:text-lg leading-loose text-slate-100 flex flex-wrap items-center">
        <span>{prefix}</span>
        <span className="relative inline-flex items-center mx-2 my-1">
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === 'Tab') {
                if (onEnterOrTab) onEnterOrTab();
              }
            }}
            placeholder={gapNumber ? `(${gapNumber})` : '...'}
            className="px-3 py-1.5 min-w-[140px] max-w-[240px] bg-slate-950 border-2 border-amber-400/80 focus:border-blue-400 rounded-xl text-amber-300 font-bold text-center outline-none shadow-inner transition-all focus:ring-2 focus:ring-blue-400/30"
            autoFocus
          />
        </span>
        <span>{suffix}</span>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400 mt-2 px-1">
        <span>Bo'shliqqa 1 ta so'z yoki raqam yozing</span>
        <span className="font-mono text-[11px] bg-slate-800 px-2 py-0.5 rounded text-slate-300">
          Enter / Tab ➔ Keyingisi
        </span>
      </div>
    </div>
  );
};

// ============================================================================
// 6. AUTHENTIC LISTENING AUDIO PLAYER
// ============================================================================
interface ListeningAudioBarProps {
  audioUrl?: string;
  isStrict: boolean;
  volume: number;
  isMuted: boolean;
  onVolumeChange: (vol: number) => void;
  onToggleMute: () => void;
}

export const ListeningAudioBar: React.FC<ListeningAudioBarProps> = ({
  audioUrl,
  isStrict,
  volume,
  isMuted,
  onVolumeChange,
  onToggleMute,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [playCount, setPlayCount] = useState(1);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);

  if (!audioUrl) return null;

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  };

  return (
    <div className="flex items-center gap-2 bg-slate-800/90 px-3 py-1.5 rounded-xl border border-slate-700 shadow-sm">
      {/* Play/Pause Button */}
      <button
        type="button"
        onClick={togglePlay}
        className="w-7 h-7 rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center transition-colors"
        title={isPlaying ? 'Pauza' : 'Ijro'}
      >
        {isPlaying ? <PauseIcon className="h-3.5 w-3.5" /> : <PlayIcon className="h-3.5 w-3.5 ml-0.5" />}
      </button>

      {/* Plays indicator */}
      <div className="hidden sm:flex flex-col text-[10px] leading-tight">
        <span className="font-bold text-slate-200">Listening Audio</span>
        <span className="text-amber-400 font-mono">
          {isStrict ? `Play ${playCount} of 2` : 'Practice audio'}
        </span>
      </div>

      {/* Volume Icon Button */}
      <button
        type="button"
        onClick={onToggleMute}
        className="text-slate-400 hover:text-white transition-colors"
        title={isMuted ? 'Ovozni yoqish' : 'Ovozni o\'chirish'}
      >
        {isMuted ? (
          <VolumeXIcon className="h-4 w-4 text-rose-400" />
        ) : (
          <Volume2Icon className="h-4 w-4 text-emerald-400" />
        )}
      </button>

      {/* Volume Slider */}
      <input
        type="range"
        min="0"
        max="1"
        step="0.05"
        value={isMuted ? 0 : volume}
        onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
        className="w-16 h-1 accent-blue-500 cursor-pointer"
        title="Ovoz balandligi"
      />

      <audio
        ref={audioRef}
        src={audioUrl}
        autoPlay={isStrict}
        onEnded={() => {
          setIsPlaying(false);
          setPlayCount((prev) => Math.min(2, prev + 1));
        }}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />
    </div>
  );
};
