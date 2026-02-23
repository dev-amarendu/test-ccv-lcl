import { type CSSProperties } from 'react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface ProgressProps {
  /** Value between 0 and 100 */
  value: number;
  /** Override the fill colour */
  color?: string;
  /** Show animated stripe pattern */
  animated?: boolean;
  /** Accessible label */
  label?: string;
  /** Height in px */
  height?: number;
  className?: string;
  style?: CSSProperties;
}

/* ── Keyframe injection ── */
const stripeKeyframes = `@keyframes ccv-progress-stripe{from{background-position:1rem 0}to{background-position:0 0}}`;
let stripeInjected = false;
function injectStripe() {
  if (stripeInjected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.textContent = stripeKeyframes;
  document.head.appendChild(s);
  stripeInjected = true;
}

/* ── Component ── */
export function Progress({
  value,
  color = 'var(--color-primary-600)',
  animated = false,
  label,
  height = 8,
  className,
  style,
}: ProgressProps) {
  if (animated) injectStripe();

  const clamped = Math.min(100, Math.max(0, value));

  const trackStyle: CSSProperties = {
    width: '100%',
    height,
    background: 'var(--color-neutral-200)',
    borderRadius: 'var(--radius-full)',
    overflow: 'hidden',
    ...style,
  };

  const fillStyle: CSSProperties = {
    width: `${clamped}%`,
    height: '100%',
    background: color,
    borderRadius: 'var(--radius-full)',
    transition: 'width var(--transition-normal)',
    ...(animated
      ? {
          backgroundImage:
            'linear-gradient(45deg, rgba(255,255,255,0.15) 25%, transparent 25%, transparent 50%, rgba(255,255,255,0.15) 50%, rgba(255,255,255,0.15) 75%, transparent 75%, transparent)',
          backgroundSize: '1rem 1rem',
          animation: 'ccv-progress-stripe 1s linear infinite',
        }
      : {}),
  };

  return (
    <div className={clsx(className)} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
      {label && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)' }}>
          <span>{label}</span>
          <span style={{ fontWeight: 'var(--font-weight-semibold)' }}>{clamped}%</span>
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? `${clamped}% complete`}
        style={trackStyle}
      >
        <div style={fillStyle} />
      </div>
    </div>
  );
}
