import type { ReactNode, CSSProperties } from 'react';
import { clsx } from 'clsx';

/* ── Types ── */
export type CardPadding = 'sm' | 'md' | 'lg' | 'none';

export interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  footer?: ReactNode;
  padding?: CardPadding;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}

/* ── Padding map ── */
const paddingMap: Record<CardPadding, string> = {
  none: '0',
  sm: 'var(--space-3)',
  md: 'var(--space-4)',
  lg: 'var(--space-6)',
};

/* ── Component ── */
export function Card({
  title,
  subtitle,
  footer,
  padding = 'md',
  className,
  style,
  children,
}: CardProps) {
  const cardStyle: CSSProperties = {
    background: '#fff',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--color-neutral-200)',
    boxShadow: 'var(--shadow-sm)',
    overflow: 'hidden',
    ...style,
  };

  const headerStyle: CSSProperties = {
    padding: `${paddingMap[padding]} ${paddingMap[padding]} 0`,
  };

  const bodyStyle: CSSProperties = {
    padding: paddingMap[padding],
  };

  const footerStyle: CSSProperties = {
    padding: `0 ${paddingMap[padding]} ${paddingMap[padding]}`,
    borderTop: '1px solid var(--color-neutral-200)',
    paddingTop: paddingMap[padding],
    marginTop: padding === 'none' ? 0 : undefined,
  };

  return (
    <div className={clsx(className)} style={cardStyle}>
      {(title || subtitle) && (
        <div style={headerStyle}>
          {title && (
            <h3
              style={{
                fontSize: 'var(--font-size-md)',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--color-neutral-900)',
                lineHeight: 'var(--line-height-tight)',
              }}
            >
              {title}
            </h3>
          )}
          {subtitle && (
            <p
              style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-neutral-500)',
                marginTop: 'var(--space-1)',
              }}
            >
              {subtitle}
            </p>
          )}
        </div>
      )}

      <div style={bodyStyle}>{children}</div>

      {footer && <div style={footerStyle}>{footer}</div>}
    </div>
  );
}
