import { type CSSProperties } from 'react';
import { clsx } from 'clsx';

/* ── Types ── */
export type SkeletonVariant = 'text' | 'circle' | 'rect';

export interface SkeletonProps {
  variant?: SkeletonVariant;
  width?: number | string;
  height?: number | string;
  className?: string;
  style?: CSSProperties;
  /** Number of text lines to render (only for variant="text") */
  lines?: number;
}

/* ── Keyframe injection ── */
const shimmerKeyframes = `@keyframes ccv-shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}`;
let shimmerInjected = false;
function injectShimmer() {
  if (shimmerInjected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.textContent = shimmerKeyframes;
  document.head.appendChild(s);
  shimmerInjected = true;
}

/* ── Base shimmer style ── */
const baseShimmer: CSSProperties = {
  background: `linear-gradient(90deg, var(--color-neutral-200) 25%, var(--color-neutral-100) 50%, var(--color-neutral-200) 75%)`,
  backgroundSize: '200% 100%',
  animation: 'ccv-shimmer 1.5s ease-in-out infinite',
};

/* ── Component ── */
export function Skeleton({
  variant = 'text',
  width,
  height,
  className,
  style,
  lines = 1,
}: SkeletonProps) {
  injectShimmer();

  if (variant === 'text' && lines > 1) {
    return (
      <div className={clsx(className)} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', ...style }}>
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            style={{
              ...baseShimmer,
              height: height ?? 14,
              width: i === lines - 1 ? '60%' : (width ?? '100%'),
              borderRadius: 'var(--radius-sm)',
            }}
            aria-hidden="true"
          />
        ))}
      </div>
    );
  }

  const variantStyles: Record<SkeletonVariant, CSSProperties> = {
    text: {
      width: width ?? '100%',
      height: height ?? 14,
      borderRadius: 'var(--radius-sm)',
    },
    circle: {
      width: width ?? 40,
      height: height ?? width ?? 40,
      borderRadius: 'var(--radius-full)',
    },
    rect: {
      width: width ?? '100%',
      height: height ?? 100,
      borderRadius: 'var(--radius-md)',
    },
  };

  return (
    <div
      className={clsx(className)}
      style={{ ...baseShimmer, ...variantStyles[variant], ...style }}
      role="status"
      aria-label="Loading"
      aria-busy="true"
    >
      <span
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
          overflow: 'hidden',
          clip: 'rect(0,0,0,0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
      >
        Loading...
      </span>
    </div>
  );
}
