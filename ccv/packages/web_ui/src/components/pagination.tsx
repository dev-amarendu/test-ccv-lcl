import { Button } from '@/components/ui/button';

type PaginationProps = {
  page: number;                // 1-based
  totalPages: number;
  onPageChange: (p: number) => void;
  siblingCount?: number;       // how many neighbors around the current page
};

function range(start: number, end: number) {
  const out: number[] = [];
  for (let i = start; i <= end; i++) out.push(i);
  return out;
}

function usePagination(current: number, total: number, siblingCount = 1) {
  // Returns an array of numbers and '…' for ellipsis
  const totalNumbers = siblingCount * 2 + 5; // first, last, current + 2*sibling + 2 ellipses
  if (total <= totalNumbers) return range(1, total);

  const leftSibling = Math.max(current - siblingCount, 1);
  const rightSibling = Math.min(current + siblingCount, total);

  const showLeftEllipsis = leftSibling > 2;
  const showRightEllipsis = rightSibling < total - 1;

  const items: (number | '…')[] = [];

  items.push(1);

  if (showLeftEllipsis) items.push('…');

  const start = showLeftEllipsis ? leftSibling : 2;
  const end = showRightEllipsis ? rightSibling : total - 1;
  range(start, end).forEach(n => items.push(n));

  if (showRightEllipsis) items.push('…');

  if (total > 1) items.push(total);

  return items;
}

function Pagination({ page, totalPages, onPageChange, siblingCount = 1 }: PaginationProps) {
  const items = usePagination(page, totalPages, siblingCount);

  const go = (p: number) => {
    if (p < 1 || p > totalPages || p === page) return;
    onPageChange(p);
  };

  return (
    <nav aria-label="Pagination" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
      <Button
        variant="secondary"
        size="sm"
        disabled={page <= 1}
        onClick={() => go(page - 1)}
        aria-label="Previous page"
      >
        ‹ Prev
      </Button>

      {items.map((it, idx) => {
        if (it === '…') {
          return (
            <span key={`ellipsis-${idx}`} style={{ padding: '0 6px', color: 'var(--color-neutral-500)' }}>
              …
            </span>
          );
        }
        const isActive = it === page;
        return (
          <Button
            key={it}
            size="sm"
            variant={isActive ? 'primary' : 'secondary'}
            onClick={() => go(it as number)}
            aria-current={isActive ? 'page' : undefined}
          >
            {it}
          </Button>
        );
      })}

      <Button
        variant="secondary"
        size="sm"
        disabled={page >= totalPages}
        onClick={() => go(page + 1)}
        aria-label="Next page"
      >
        Next ›
      </Button>
    </nav>
  );
}

export default Pagination;