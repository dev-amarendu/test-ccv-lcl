import { useState, useCallback, type CSSProperties } from 'react';
import { Copy, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface CodeViewerProps {
  code: string;
  /** Starting line number (1-based). Default 1 */
  startLine?: number;
  /** Lines to visually highlight */
  highlightLines?: number[];
  /** Max visible lines before collapse. 0 = no collapse */
  maxLines?: number;
  /** File path displayed in the header */
  filePath?: string;
  /** Permalink URL (placeholder) */
  permalink?: string;
  /** Source URL (placeholder) */
  sourceUrl?: string;
  className?: string;
  style?: CSSProperties;
}

/* ── Component ── */
export function CodeViewer({
  code,
  startLine = 1,
  highlightLines = [],
  maxLines = 15,
  filePath,
  permalink,
  sourceUrl,
  className,
  style,
}: CodeViewerProps) {
  const lines = code.split('\n');
  const [expanded, setExpanded] = useState(false);
  const shouldCollapse = maxLines > 0 && lines.length > maxLines;
  const visibleLines = shouldCollapse && !expanded ? lines.slice(0, maxLines) : lines;

  const highlightSet = new Set(highlightLines);

  const handleCopyPermalink = useCallback(() => {
    if (permalink) {
      navigator.clipboard?.writeText(permalink);
    }
  }, [permalink]);

  const wrapperStyle: CSSProperties = {
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--color-neutral-200)',
    overflow: 'hidden',
    background: 'var(--color-neutral-900)',
    fontSize: 'var(--font-size-sm)',
    ...style,
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 'var(--space-2) var(--space-3)',
    background: 'var(--color-neutral-800)',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
  };

  const headerTextStyle: CSSProperties = {
    fontSize: 'var(--font-size-xs)',
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    color: 'var(--color-neutral-400)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  };

  const actionBtnStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-1)',
    padding: 'var(--space-1) var(--space-2)',
    fontSize: 'var(--font-size-xs)',
    color: 'var(--color-neutral-400)',
    background: 'none',
    border: 'none',
    borderRadius: 'var(--radius-sm)',
    cursor: 'pointer',
    transition: 'background var(--transition-fast), color var(--transition-fast)',
  };

  const codeAreaStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'auto 1fr',
    overflowX: 'auto',
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    lineHeight: '1.6',
    tabSize: 4,
  };

  return (
    <div className={clsx(className)} style={wrapperStyle}>
      {/* Header */}
      {(filePath || permalink || sourceUrl) && (
        <div style={headerStyle}>
          <span style={headerTextStyle}>{filePath ?? 'code'}</span>
          <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
            {permalink && (
              <button
                type="button"
                style={actionBtnStyle}
                onClick={handleCopyPermalink}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
                  (e.currentTarget as HTMLElement).style.color = '#fff';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'none';
                  (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-400)';
                }}
                aria-label="Copy permalink"
              >
                <Copy size={12} /> Permalink
              </button>
            )}
            {sourceUrl && (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ ...actionBtnStyle, textDecoration: 'none' }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
                  (e.currentTarget as HTMLElement).style.color = '#fff';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'none';
                  (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-400)';
                }}
                aria-label="Open in source"
              >
                <ExternalLink size={12} /> Source
              </a>
            )}
          </div>
        </div>
      )}

      {/* Code area */}
      <div style={codeAreaStyle}>
        {/* Line numbers column */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            padding: 'var(--space-3) 0',
            userSelect: 'none',
          }}
          aria-hidden="true"
        >
          {visibleLines.map((_, i) => {
            const lineNum = startLine + i;
            const isHighlighted = highlightSet.has(lineNum);
            return (
              <span
                key={lineNum}
                style={{
                  display: 'block',
                  padding: '0 var(--space-3)',
                  textAlign: 'right',
                  fontSize: 'var(--font-size-xs)',
                  color: isHighlighted ? 'var(--color-warning-400)' : 'var(--color-neutral-600)',
                  background: isHighlighted ? 'rgba(251, 191, 36, 0.1)' : 'transparent',
                  minWidth: 48,
                }}
              >
                {lineNum}
              </span>
            );
          })}
        </div>

        {/* Code lines column */}
        <pre
          style={{
            margin: 0,
            padding: 'var(--space-3) var(--space-4) var(--space-3) var(--space-2)',
            overflow: 'visible',
            whiteSpace: 'pre',
          }}
        >
          {visibleLines.map((line, i) => {
            const lineNum = startLine + i;
            const isHighlighted = highlightSet.has(lineNum);
            return (
              <div
                key={lineNum}
                style={{
                  color: isHighlighted ? 'var(--color-neutral-100)' : 'var(--color-neutral-300)',
                  background: isHighlighted ? 'rgba(251, 191, 36, 0.1)' : 'transparent',
                }}
              >
                {line || ' '}
              </div>
            );
          })}
        </pre>
      </div>

      {/* Expand / collapse toggle */}
      {shouldCollapse && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--space-1)',
            width: '100%',
            padding: 'var(--space-2)',
            fontSize: 'var(--font-size-xs)',
            color: 'var(--color-neutral-400)',
            background: 'var(--color-neutral-800)',
            border: 'none',
            borderTop: '1px solid rgba(255,255,255,0.06)',
            cursor: 'pointer',
            transition: 'background var(--transition-fast), color var(--transition-fast)',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.color = '#fff';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-400)';
          }}
          aria-expanded={expanded}
        >
          {expanded ? (
            <>
              <ChevronUp size={14} /> Show less
            </>
          ) : (
            <>
              <ChevronDown size={14} /> Show {lines.length - maxLines} more lines
            </>
          )}
        </button>
      )}
    </div>
  );
}
