import { useEffect, useRef, useState } from 'react';
import { Headphones, Pause, Play, RotateCcw, Volume2, VolumeX } from 'lucide-react';

interface AudioPlayerBarProps {
  src: string;
  title?: string;
  sectionName?: string;
}

function formatAudioTime(seconds: number): string {
  if (!seconds || isNaN(seconds)) return '00:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export default function AudioPlayerBar({ src, title, sectionName }: AudioPlayerBarProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState<number>(1);
  const [isMuted, setIsMuted] = useState(false);

  useEffect(() => {
    // Reset state on audio src change
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate;
      audioRef.current.load();
    }
  }, [src, playbackRate]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch(() => setIsPlaying(false));
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration || 0);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setCurrentTime(val);
    if (audioRef.current) {
      audioRef.current.currentTime = val;
    }
  };

  const cycleSpeed = () => {
    const speeds = [1, 1.25, 1.5];
    const nextIdx = (speeds.indexOf(playbackRate) + 1) % speeds.length;
    const nextSpeed = speeds[nextIdx];
    setPlaybackRate(nextSpeed);
    if (audioRef.current) {
      audioRef.current.playbackRate = nextSpeed;
    }
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    const next = !isMuted;
    audioRef.current.muted = next;
    setIsMuted(next);
  };

  const restartAudio = () => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = 0;
    setCurrentTime(0);
    audioRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
  };

  return (
    <div
      className="audio-player-bar-container"
      style={{
        margin: '12px 0 16px',
        padding: '12px 16px',
        borderRadius: 14,
        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.98))',
        border: '1px solid rgba(59, 130, 246, 0.35)',
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
        color: '#f8fafc',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={() => setIsPlaying(false)}
      />

      {/* Top Header info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: 'rgba(59, 130, 246, 0.2)',
              border: '1px solid rgba(59, 130, 246, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#60a5fa',
            }}
          >
            <Headphones size={20} className={isPlaying ? 'animate-pulse' : ''} />
          </div>
          <div>
            <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#f1f5f9' }}>
              {title || 'IELTS Listening Audio Track'}
            </div>
            {sectionName && (
              <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
                Bo'lim: <span style={{ color: '#60a5fa', fontWeight: 600 }}>{sectionName}</span>
              </div>
            )}
          </div>
        </div>

        {/* Speed & Mute & Restart controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            type="button"
            onClick={restartAudio}
            title="Boshidan o'ynatish"
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 8,
              padding: '6px 10px',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: '0.76rem',
              fontWeight: 600,
            }}
          >
            <RotateCcw size={13} />
          </button>

          <button
            type="button"
            onClick={cycleSpeed}
            title="Ijro tezligi"
            style={{
              background: playbackRate > 1 ? 'rgba(59, 130, 246, 0.2)' : 'rgba(255, 255, 255, 0.06)',
              border: `1px solid ${playbackRate > 1 ? 'rgba(59, 130, 246, 0.5)' : 'rgba(255, 255, 255, 0.12)'}`,
              borderRadius: 8,
              padding: '6px 10px',
              color: playbackRate > 1 ? '#60a5fa' : '#94a3b8',
              cursor: 'pointer',
              fontSize: '0.76rem',
              fontWeight: 700,
            }}
          >
            {playbackRate}x
          </button>

          <button
            type="button"
            onClick={toggleMute}
            title={isMuted ? "Ovozni yoqish" : "Ovozni o'chirish"}
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 8,
              padding: '6px 10px',
              color: isMuted ? '#f87171' : '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {isMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
          </button>
        </div>
      </div>

      {/* Main playback control bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          type="button"
          onClick={togglePlay}
          style={{
            width: 44,
            height: 44,
            borderRadius: '50%',
            background: isPlaying ? '#2563eb' : '#3b82f6',
            border: 'none',
            color: '#fff',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)',
            transition: 'transform 0.1s ease',
          }}
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? <Pause size={20} fill="#fff" /> : <Play size={20} fill="#fff" style={{ marginLeft: 2 }} />}
        </button>

        <span style={{ fontSize: '0.8rem', color: '#94a3b8', minWidth: 42, fontVariantNumeric: 'tabular-nums' }}>
          {formatAudioTime(currentTime)}
        </span>

        <input
          type="range"
          min={0}
          max={duration || 100}
          value={currentTime}
          onChange={handleSeek}
          style={{
            flex: 1,
            height: 6,
            borderRadius: 3,
            accentColor: '#3b82f6',
            cursor: 'pointer',
          }}
        />

        <span style={{ fontSize: '0.8rem', color: '#94a3b8', minWidth: 42, fontVariantNumeric: 'tabular-nums' }}>
          {formatAudioTime(duration)}
        </span>
      </div>
    </div>
  );
}
