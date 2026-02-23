import { useState, useRef, type ReactNode, type CSSProperties } from 'react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface TooltipProps {
  content: ReactNode;
  /** Position relative to trigger. Currently only 'top' is implemented. */
  position?: 'top';
  children: ReactNode;
  className?: string;
}

/* ── Component ── */
export function Tooltip({ content, position = 'top', children, className }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const tooltipId = useRef(`tooltip-${Math.random().toString(36).slice(2, 9)}`).current;

  const show = () => {
    clearTimeout(timeoutRef.current);
    setVisible(true);
  };

  const hide = () => {
    timeoutRef.current = setTimeout(() => setVisible(false), 100);
  };

  const wrapperStyle: CSSProperties = {
    position: 'relative',
    display: 'inline-flex',
  };

  const tipStyle: CSSProperties = {
    position: 'absolute',
    bottom: 'calc(100% + 6px)',
    left: '50%',
    transform: 'translateX(-50%)',
    padding: 'var(--space-1) var(--space-2)',
    fontSize: 'var(--font-size-xs)',
    fontWeight: 'var(--font-weight-medium)',
    color: '#fff',
    background: 'var(--color-neutral-800)',
    borderRadius: 'var(--radius-sm)',
    whiteSpace: 'nowrap',
    pointerEvents: 'none',
    opacity: visible ? 1 : 0,
    transition: 'opacity var(--transition-fast)',
    zIndex: 50,
    boxShadow: 'var(--shadow-md)',
  };

  return (
    <span
      className={clsx(className)}
      style={wrapperStyle}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      <span aria-describedby={visible ? tooltipId : undefined}>
        {children}
      </span>
      <span
        id={tooltipId}
        role="tooltip"
        style={tipStyle}
        aria-hidden={!visible}
      >
        {content}
      </span>
    </span>
  );
}
