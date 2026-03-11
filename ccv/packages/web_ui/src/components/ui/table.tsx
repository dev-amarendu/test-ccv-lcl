import { type ReactNode, type CSSProperties, useState } from 'react';
import { clsx } from 'clsx';
import { Card } from './card';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from './button';
import { CircleX, Eye, RotateCcw } from 'lucide-react';
import { cancelScan, rerunScan } from '@/api/scans';
import { useToast } from './toast';
import { Scan } from '@/api/types';

/* ── Types ── */
export interface Column<T> {
  header: string;
  accessor: keyof T & string;
  render?: (value: T[keyof T], row: T, index: number) => ReactNode;
  width?: string;
  align?: 'left' | 'center' | 'right';
}

export interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T, index: number) => void;
  rowKey?: (row: T, index: number) => string | number;
  emptyMessage?: string;
  className?: string;
  style?: CSSProperties;
  expandedId?: string | null;
  scans?: Scan[];
}

/* ── Styles ── */
const tableStyle: CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 'var(--font-size-sm)',
};

const thStyle: CSSProperties = {
  textAlign: 'left',
  padding: 'var(--space-3) var(--space-4)',
  fontWeight: 'var(--font-weight-semibold)',
  fontSize: 'var(--font-size-xs)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: 'var(--color-neutral-500)',
  borderBottom: '2px solid var(--color-neutral-200)',
  background: 'var(--color-neutral-50)',
  whiteSpace: 'nowrap',
};

const tdStyle: CSSProperties = {
  padding: 'var(--space-3) var(--space-4)',
  borderBottom: '1px solid var(--color-neutral-100)',
  color: 'var(--color-neutral-700)',
};

/* ── Component ── */
export function Table<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  rowKey,
  emptyMessage = 'No data to display',
  className,
  style,
  expandedId,
  scans
}: TableProps<T>) {
  const navigate = useNavigate();
  const [rerunning, setRerunning] = useState<string | null>(null);
  const { toast } = useToast();

   /* ── Rerun ── */
  async function handleRerun(scanId: string) {
    setRerunning(scanId);
    try {
      const newScan = await rerunScan(scanId);
      toast('success', 'Scan re-triggered');
      navigate(`/scans/${newScan.id}`);
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Re-run failed');
    } finally {
      setRerunning(null);
    }
  }

  async function handleCancel(scanId: string){
    setRerunning(scanId);
    try {
      await cancelScan(scanId);
      toast('success', 'Scan Cancelled');
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Cancel scan failed');
    } finally {
      setRerunning(null);
    }
  }

  return (
    <div
      className={clsx(className)}
      style={{ overflowX: 'auto', borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-neutral-200)', ...style }}
    >
      <table style={tableStyle}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.accessor}
                style={{
                  ...thStyle,
                  width: col.width,
                  textAlign: col.align ?? 'left',
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                style={{
                  ...tdStyle,
                  textAlign: 'center',
                  padding: 'var(--space-8)',
                  color: 'var(--color-neutral-400)',
                }}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, idx) => (
              <>
              <tr
                key={rowKey ? rowKey(row, idx) : idx}
                onClick={onRowClick ? () => onRowClick(row, idx) : undefined}
                style={{
                  background: idx % 2 === 0 ? '#fff' : 'var(--color-neutral-50)',
                  cursor: onRowClick ? 'pointer' : 'default',
                  transition: 'background var(--transition-fast)',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'var(--color-primary-50)';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background =
                    idx % 2 === 0 ? '#fff' : 'var(--color-neutral-50)';
                }}
              >
                {columns.map((col) => (
                  <td
                    key={col.accessor}
                    style={{ ...tdStyle, textAlign: col.align ?? 'left' }}
                  >
                    {col.render
                      ? col.render(row[col.accessor], row, idx)
                      : (row[col.accessor] as ReactNode)}
                  </td>
                ))}
              </tr>
              {/* Expanded row detail */}
          {(expandedId === row.id) && (() => {
            const scan = scans?.find((s) => s.id === expandedId);
            if (!scan) return null;
            return (
              <tr>
                <td colSpan={columns.length} style={{ padding: 0, borderBottom: 'none'}}>
              <Card style={{ width: '100%', maxWidth: '100%', display: 'block', borderLeft: '4px solid var(--color-primary-400)' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                  <h3 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)' }}>
                    Scan Summary
                  </h3>
                  <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)' }}>
                    {scan.status === 'failed'
                      ? `Error: ${scan.error_message ?? 'Unknown error'}`
                      : `Scan on ${scan.repo_id} / ${scan.branch} triggered by ${scan.trigger_type}.`}
                  </p>

                  {scan.status === 'failed' && scan.error_message && (
                    <div
                      style={{
                        padding: 'var(--space-3)',
                        background: 'var(--color-critical-50)',
                        border: '1px solid var(--color-critical-200)',
                        borderRadius: 'var(--radius-md)',
                        fontSize: 'var(--font-size-sm)',
                        color: 'var(--color-critical-700)',
                      }}
                    >
                      {scan.error_message}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <Link to={`/findings?scan_id=${scan.id}`} style={{ textDecoration: 'none' }}>
                      <Button size="sm" variant="secondary">
                        <Eye size={14} /> View findings
                      </Button>
                    </Link>
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={rerunning === scan.id}
                      onClick={() => handleRerun(scan.id)}
                    >
                      <RotateCcw size={14} /> Re-run
                    </Button>
                    {(scan.status.toLowerCase() === 'running') &&
                    <Button 
                      size="sm" 
                      variant="secondary"
                      onClick={() => handleCancel(scan.id)}
                      >
                        <CircleX size={14} /> Cancel
                      </Button>}
                  </div>
                </div>
              </Card>
              </td></tr>
            );
          })()}
            </>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
