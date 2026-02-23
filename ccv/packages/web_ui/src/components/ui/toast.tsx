import { useState, useCallback, useRef, useEffect, type CSSProperties, type ReactNode } from 'react';
import { X, CheckCircle, AlertTriangle, AlertCircle, Info } from 'lucide-react';
import { clsx } from 'clsx';

/* ── Types ── */
export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastMessage {
  id: string;
  type: ToastType;
  message: ReactNode;
  duration?: number;
}

export interface ToastContainerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
  className?: string;
}

/* ── Colours per type ── */
const typeConfig: Record<ToastType, { bg: string; border: string; icon: typeof CheckCircle; iconColor: string }> = {
  success: { bg: 'var(--color-success-50)', border: 'var(--color-success-400)', icon: CheckCircle, iconColor: 'var(--color-success-600)' },
  error: { bg: 'var(--color-critical-50)', border: 'var(--color-critical-400)', icon: AlertCircle, iconColor: 'var(--color-critical-600)' },
  warning: { bg: 'var(--color-warning-50)', border: 'var(--color-warning-400)', icon: AlertTriangle, iconColor: 'var(--color-warning-600)' },
  info: { bg: 'var(--color-primary-50)', border: 'var(--color-primary-400)', icon: Info, iconColor: 'var(--color-primary-600)' },
};

/* ── Single Toast ── */
function ToastItem({ toast, onDismiss }: { toast: ToastMessage; onDismiss: (id: string) => void }) {
  const cfg = typeConfig[toast.type];
  const Icon = cfg.icon;
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    const duration = toast.duration ?? 5000;
    if (duration > 0) {
      timerRef.current = setTimeout(() => onDismiss(toast.id), duration);
    }
    return () => clearTimeout(timerRef.current);
  }, [toast.id, toast.duration, onDismiss]);

  const itemStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 'var(--space-3)',
    padding: 'var(--space-3) var(--space-4)',
    background: cfg.bg,
    borderLeft: `4px solid ${cfg.border}`,
    borderRadius: 'var(--radius-md)',
    boxShadow: 'var(--shadow-md)',
    minWidth: 300,
    maxWidth: 420,
    animation: 'ccv-toast-in 0.25s ease',
  };

  return (
    <div style={itemStyle} role="alert" aria-live="assertive">
      <Icon size={18} style={{ color: cfg.iconColor, flexShrink: 0, marginTop: 2 }} aria-hidden="true" />
      <div style={{ flex: 1, fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-800)' }}>
        {toast.message}
      </div>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 24,
          height: 24,
          borderRadius: 'var(--radius-sm)',
          color: 'var(--color-neutral-400)',
          cursor: 'pointer',
          border: 'none',
          background: 'none',
          flexShrink: 0,
          transition: 'color var(--transition-fast)',
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-700)'; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-400)'; }}
        aria-label="Dismiss notification"
      >
        <X size={14} />
      </button>
    </div>
  );
}

/* ── Toast Container ── */
export function ToastContainer({ toasts, onDismiss, className }: ToastContainerProps) {
  const containerStyle: CSSProperties = {
    position: 'fixed',
    top: 'var(--space-4)',
    right: 'var(--space-4)',
    zIndex: 2000,
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
    pointerEvents: 'none',
  };

  return (
    <div className={clsx(className)} style={containerStyle}>
      {toasts.map((t) => (
        <div key={t.id} style={{ pointerEvents: 'auto' }}>
          <ToastItem toast={t} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}

/* ── Keyframe injection ── */
const toastKeyframes = `@keyframes ccv-toast-in{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}`;
let toastStyleInjected = false;
function injectToastKeyframes() {
  if (toastStyleInjected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.textContent = toastKeyframes;
  document.head.appendChild(s);
  toastStyleInjected = true;
}

/* ── useToast hook ── */
let idCounter = 0;

export function useToast() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  injectToastKeyframes();

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((type: ToastType, message: ReactNode, duration?: number) => {
    const id = `toast-${++idCounter}`;
    setToasts((prev) => [...prev, { id, type, message, duration }]);
    return id;
  }, []);

  const Container = useCallback(
    () => <ToastContainer toasts={toasts} onDismiss={dismiss} />,
    [toasts, dismiss],
  );

  return {
    toast,
    dismiss,
    ToastContainer: Container,
  };
}
