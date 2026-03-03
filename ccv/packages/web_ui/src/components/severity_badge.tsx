import { ShieldAlert, ShieldClose, AlertTriangle, Info, ShieldCheck, type LucideIcon } from 'lucide-react';
import { Badge, type BadgeSize } from './ui/badge';
import type { CSSProperties } from 'react';
import { clsx } from 'clsx';

/* ── Types ── */
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export interface SeverityBadgeProps {
  severity: Severity;
  size?: BadgeSize;
  className?: string;
  style?: CSSProperties;
}

/* ── Severity config ── */
interface SeverityConfig {
  bg: string;
  text: string;
  icon: LucideIcon;
}

const severityMap: Record<Severity, SeverityConfig> = {
  critical: {
    bg: 'var(--color-critical-100)',
    text: 'var(--color-critical-700)',
    icon: ShieldClose,
  },
  high: {
    bg: '#fff7ed', // orange-50
    text: '#c2410c', // orange-700
    icon: ShieldAlert,
  },
  medium: {
    bg: 'var(--color-warning-100)',
    text: 'var(--color-warning-700)',
    icon: AlertTriangle,
  },
  low: {
    bg: 'var(--color-success-100)',
    text: 'var(--color-success-700)',
    icon: ShieldCheck,
  },
  info: {
    bg: 'var(--color-neutral-100)',
    text: 'var(--color-neutral-600)',
    icon: Info,
  },
};

/* ── Component ── */
export function SeverityBadge({ severity, size = 'sm', className, style }: SeverityBadgeProps) {
  let normalizedSev = severity?.toLowerCase() as Severity;
  // Handle old un-normalized database values
  if (normalizedSev === 'informational' as any) normalizedSev = 'info';
  if (normalizedSev === 'very high' as any) normalizedSev = 'high';
  if (normalizedSev === 'very low' as any) normalizedSev = 'low';

  const config = severityMap[normalizedSev] || severityMap.info; // Default fallback to prevent crash
  const Icon = config.icon;

  return (
    <Badge
      className={clsx(className)}
      size={size}
      style={{
        background: config.bg,
        color: config.text,
        textTransform: 'capitalize',
        ...style,
      }}
    >
      <Icon size={size === 'sm' ? 12 : 14} aria-hidden="true" />
      {severity}
    </Badge>
  );
}
