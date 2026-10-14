import { useState, useRef } from 'react';
import type { ReactNode, MouseEvent as ReactMouseEvent, CSSProperties } from 'react';

interface TiltCardProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  maxTilt?: number;
  glare?: boolean;
  scale?: number;
}

export default function TiltCard({
  children,
  className = '',
  style = {},
  maxTilt = 10,
  glare = true,
  scale = 1.02,
}: TiltCardProps) {
  const cardRef = useRef<HTMLDivElement | null>(null);
  const [transform, setTransform] = useState<string>('perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)');
  const [glareStyle, setGlareStyle] = useState<{ x: number; y: number; opacity: number }>({
    x: 50,
    y: 50,
    opacity: 0,
  });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: ReactMouseEvent<HTMLDivElement>) => {
    const card = cardRef.current;
    if (!card) return;

    // Check prefers-reduced-motion
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -maxTilt;
    const rotateY = ((x - centerX) / centerX) * maxTilt;

    setTransform(`perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) scale3d(${scale}, ${scale}, ${scale})`);

    if (glare) {
      const glareX = (x / rect.width) * 100;
      const glareY = (y / rect.height) * 100;
      setGlareStyle({ x: glareX, y: glareY, opacity: 0.35 });
    }
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    setTransform('perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)');
    setGlareStyle((prev) => ({ ...prev, opacity: 0 }));
  };

  return (
    <div
      ref={cardRef}
      className={`tilt-card-wrapper ${className}`.trim()}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        transform,
        transition: isHovered
          ? 'transform 0.1s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease'
          : 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.4s ease',
        transformStyle: 'preserve-3d',
        position: 'relative',
        willChange: 'transform',
        ...style,
      }}
    >
      {/* 3D Multi-Layer Children */}
      {children}

      {/* Dynamic Glare / Sheen Overlay */}
      {glare && (
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: 'inherit',
            pointerEvents: 'none',
            background: `radial-gradient(circle 280px at ${glareStyle.x}% ${glareStyle.y}%, rgba(245, 158, 11, ${glareStyle.opacity}) 0%, transparent 80%)`,
            transition: 'opacity 0.3s ease',
            zIndex: 10,
            mixBlendMode: 'screen',
          }}
        />
      )}
    </div>
  );
}
