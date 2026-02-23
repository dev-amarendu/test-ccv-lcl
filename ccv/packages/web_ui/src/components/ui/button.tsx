import { forwardRef, type ButtonHTMLAttributes, type CSSProperties } from 'react';
import { Loader2 } from 'lucide-react';
import { clsx } from 'clsx';

/* ── Types ── */
export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  className?: string;
}

/* ── Variant styles ── */
const variantStyles: Record<ButtonVariant, CSSProperties> = {
  primary: {
    background: 'var(--color-primary-600)',
    color: '#fff',
    border: 'none',
  },
  secondary: {
    background: 'transparent',
    color: 'var(--color-neutral-700)',
    border: '1px solid var(--color-neutral-300)',
  },
  ghost: {
    background: 'transparent',
    color: 'var(--color-neutral-600)',
    border: '1px solid transparent',
  },
  danger: {
    background: 'var(--color-critical-600)',
    color: '#fff',
    border: 'none',
  },
};

const variantHoverBg: Record<ButtonVariant, string> = {
  primary: 'var(--color-primary-700)',
  secondary: 'var(--color-neutral-100)',
  ghost: 'var(--color-neutral-100)',
  danger: 'var(--color-critical-700)',
};

/* ── Size styles ── */
const sizeStyles: Record<ButtonSize, CSSProperties> = {
  sm: { padding: 'var(--space-1) var(--space-2)', fontSize: 'var(--font-size-xs)', height: 30 },
  md: { padding: 'var(--space-2) var(--space-4)', fontSize: 'var(--font-size-sm)', height: 36 },
  lg: { padding: 'var(--space-3) var(--space-6)', fontSize: 'var(--font-size-base)', height: 44 },
};

/* ── Spinner keyframes (injected once) ── */
const spinKeyframes = `@keyframes ccv-spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`;
let styleInjected = false;
function injectSpinKeyframes() {
  if (styleInjected || typeof document === 'undefined') return;
  const style = document.createElement('style');
  style.textContent = spinKeyframes;
  document.head.appendChild(style);
  styleInjected = true;
}

/* ── Component ── */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading = false, disabled, children, className, style, ...rest }, ref) => {
    injectSpinKeyframes();

    const isDisabled = disabled || loading;

    const baseStyle: CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 'var(--space-2)',
      fontWeight: 'var(--font-weight-semibold)',
      borderRadius: 'var(--radius-md)',
      cursor: isDisabled ? 'not-allowed' : 'pointer',
      transition: 'background var(--transition-fast), box-shadow var(--transition-fast)',
      opacity: isDisabled ? 0.55 : 1,
      lineHeight: 1,
      whiteSpace: 'nowrap',
      ...variantStyles[variant],
      ...sizeStyles[size],
      ...style,
    };

    return (
      <button
        ref={ref}
        className={clsx(className)}
        style={baseStyle}
        disabled={isDisabled}
        aria-disabled={isDisabled || undefined}
        aria-busy={loading || undefined}
        onMouseEnter={(e) => {
          if (!isDisabled) {
            (e.currentTarget as HTMLElement).style.background = variantHoverBg[variant];
          }
        }}
        onMouseLeave={(e) => {
          if (!isDisabled) {
            (e.currentTarget as HTMLElement).style.background = variantStyles[variant].background as string;
          }
        }}
        {...rest}
      >
        {loading && (
          <Loader2
            size={size === 'sm' ? 12 : size === 'lg' ? 18 : 14}
            style={{ animation: 'ccv-spin 0.8s linear infinite', flexShrink: 0 }}
            aria-hidden="true"
          />
        )}
        {children}
      </button>
    );
  },
);

Button.displayName = 'Button';
