import type { ReactNode, CSSProperties } from 'react';
import { clsx } from 'clsx';

/* ── Types ── */
export type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';
export type BadgeSize = 'sm' | 'md';

export interface BadgeProps {
  variant?: BadgeVariant;
  size?: BadgeSize;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

/* ── Variant colours ── */
const variantColors: Record<BadgeVariant, { bg: string; text: string }> = {
  default: { bg: 'var(--color-neutral-100)', text: 'var(--color-neutral-700)' },
  success: { bg: 'var(--color-success-100)', text: 'var(--color-success-700)' },
  warning: { bg: 'var(--color-warning-100)', text: 'var(--color-warning-700)' },
  danger: { bg: 'var(--color-critical-100)', text: 'var(--color-critical-700)' },
  info: { bg: 'var(--color-primary-100)', text: 'var(--color-primary-700)' },
};

/* ── Size styles ── */
const sizeStyles: Record<BadgeSize, CSSProperties> = {
  sm: { padding: '1px var(--space-2)', fontSize: 'var(--font-size-xs)' },
  md: { padding: 'var(--space-1) var(--space-2)', fontSize: 'var(--font-size-sm)' },
};

/* ── Component ── */
export function Badge({
  variant = 'default',
  size = 'sm',
  children,
  className,
  style,
}: BadgeProps) {
  const colors = variantColors[variant];

  const badgeStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-1)',
    fontWeight: 'var(--font-weight-semibold)',
    lineHeight: 'var(--line-height-normal)',
    borderRadius: 'var(--radius-full)',
    whiteSpace: 'nowrap',
    background: colors.bg,
    color: colors.text,
    ...sizeStyles[size],
    ...style,
  };

  return (
    <span className={clsx(className)} style={badgeStyle}>
      {children}
    </span>
  );
}
