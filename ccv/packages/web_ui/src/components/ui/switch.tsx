import { useId, type CSSProperties } from 'react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  className?: string;
  style?: CSSProperties;
}

/* ── Component ── */
export function Switch({ checked, onChange, label, disabled = false, className, style }: SwitchProps) {
  const autoId = useId();
  const inputId = `switch-${autoId}`;

  const wrapperStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    ...style,
  };

  const trackStyle: CSSProperties = {
    position: 'relative',
    width: 40,
    height: 22,
    borderRadius: 'var(--radius-full)',
    background: checked ? 'var(--color-primary-600)' : 'var(--color-neutral-300)',
    transition: 'background var(--transition-fast)',
    flexShrink: 0,
  };

  const thumbStyle: CSSProperties = {
    position: 'absolute',
    top: 2,
    left: checked ? 20 : 2,
    width: 18,
    height: 18,
    borderRadius: 'var(--radius-full)',
    background: '#fff',
    boxShadow: 'var(--shadow-sm)',
    transition: 'left var(--transition-fast)',
  };

  return (
    <label className={clsx(className)} style={wrapperStyle} htmlFor={inputId}>
      {/* Hidden native checkbox for accessibility */}
      <input
        type="checkbox"
        id={inputId}
        role="switch"
        aria-checked={checked}
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
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
      />
      <span style={trackStyle} aria-hidden="true">
        <span style={thumbStyle} />
      </span>
      {label && (
        <span
          style={{
            fontSize: 'var(--font-size-sm)',
            fontWeight: 'var(--font-weight-medium)',
            color: 'var(--color-neutral-700)',
            userSelect: 'none',
          }}
        >
          {label}
        </span>
      )}
    </label>
  );
}
