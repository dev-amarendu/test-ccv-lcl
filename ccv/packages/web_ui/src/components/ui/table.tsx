import { type ReactNode, type CSSProperties } from 'react';
import { clsx } from 'clsx';

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
}: TableProps<T>) {
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
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
