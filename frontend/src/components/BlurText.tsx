import { motion } from 'motion/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ElementType } from 'react';

type KeyframeMap = Record<string, (string | number)[]>;

const buildKeyframes = (
  from: Record<string, string | number>,
  steps: Record<string, string | number>[],
): KeyframeMap => {
  const keys = new Set([
    ...Object.keys(from),
    ...steps.flatMap((s) => Object.keys(s)),
  ]);

  const keyframes: KeyframeMap = {};
  keys.forEach((k) => {
    keyframes[k] = [from[k], ...steps.map((s) => s[k])];
  });
  return keyframes;
};

interface BlurTextProps {
  text?: string;
  delay?: number;
  className?: string;
  /** Extra class applied to every animated word (e.g. per-word gradient). */
  wordClassName?: string;
  style?: CSSProperties;
  as?: ElementType;
  animateBy?: 'words' | 'chars';
  direction?: 'top' | 'bottom';
  threshold?: number;
  rootMargin?: string;
  animationFrom?: Record<string, string | number>;
  animationTo?: Record<string, string | number>[];
  easing?: (t: number) => number;
  onAnimationComplete?: () => void;
  stepDuration?: number;
}

const BlurText = ({
  text = '',
  delay = 200,
  className = '',
  wordClassName = '',
  style,
  as,
  animateBy = 'words',
  direction = 'top',
  threshold = 0.1,
  rootMargin = '0px',
  animationFrom,
  animationTo,
  easing = (t: number) => t,
  onAnimationComplete,
  stepDuration = 0.35,
}: BlurTextProps) => {
  const elements =
    animateBy === 'words' ? text.split(' ') : text.split('');
  const [inView, setInView] = useState(false);
  // Safety net: headlines must never stay invisible (e.g. if the
  // animation engine stalls, force the final resting state on a timer).
  const [done, setDone] = useState(false);
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.unobserve(el);
        }
      },
      { threshold, rootMargin },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  const defaultFrom = useMemo(
    () =>
      direction === 'top'
        ? { filter: 'blur(10px)', opacity: 0, y: -50 }
        : { filter: 'blur(10px)', opacity: 0, y: 50 },
    [direction],
  );

  const defaultTo = useMemo(
    () => [
      {
        filter: 'blur(5px)',
        opacity: 0.5,
        y: direction === 'top' ? 5 : -5,
      },
      { filter: 'blur(0px)', opacity: 1, y: 0 },
    ],
    [direction],
  );

  const fromSnapshot = animationFrom ?? defaultFrom;
  const toSnapshots = animationTo ?? defaultTo;

  const stepCount = toSnapshots.length + 1;
  const totalDuration = stepDuration * (stepCount - 1);
  // Memoized: stable identity across parent re-renders so the animation
  // never restarts (which would flash words back to opacity 0).
  const times = useMemo(
    () =>
      Array.from({ length: stepCount }, (_, i) =>
        stepCount === 1 ? 0 : i / (stepCount - 1),
      ),
    [stepCount],
  );
  const animateKeyframes = useMemo(
    () => buildKeyframes(fromSnapshot, toSnapshots),
    [fromSnapshot, toSnapshots],
  );
  const baseTransition = useMemo(
    () => ({ duration: totalDuration, times, ease: easing }),
    [totalDuration, times, easing],
  );

  // Worst-case finish time of the last word, plus buffer.
  const finishMs = (elements.length - 1) * delay + totalDuration * 1000 + 600;

  useEffect(() => {
    if (!inView || done) return;
    const id = setTimeout(() => setDone(true), finishMs);
    return () => clearTimeout(id);
  }, [inView, done, finishMs]);

  const Tag = (as ?? 'p') as ElementType;

  return (
    <Tag
      ref={ref}
      className={className}
      style={{ display: 'flex', flexWrap: 'wrap', ...style }}
    >
      {elements.map((segment, index) => {
        // Forced final state: plain spans, always visible.
        if (done) {
          return (
            <span className={`inline-block${wordClassName ? ` ${wordClassName}` : ''}`} key={index}>
              {segment === ' ' ? ' ' : segment}
              {animateBy === 'words' && index < elements.length - 1 && ' '}
            </span>
          );
        }
        const spanTransition = {
          ...baseTransition,
          delay: (index * delay) / 1000,
        };

        return (
          <motion.span
            className={`inline-block will-change-[transform,filter,opacity]${wordClassName ? ` ${wordClassName}` : ''}`}
            key={index}
            initial={fromSnapshot}
            animate={inView ? animateKeyframes : fromSnapshot}
            transition={spanTransition}
            onAnimationComplete={
              index === elements.length - 1 ? onAnimationComplete : undefined
            }
          >
            {segment === ' ' ? '\u00A0' : segment}
            {animateBy === 'words' && index < elements.length - 1 && '\u00A0'}
          </motion.span>
        );
      })}
    </Tag>
  );
};

export default BlurText;