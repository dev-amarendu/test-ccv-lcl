import { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Eye,
  Copy,
  Filter,
  FileWarning,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { Tooltip } from '@/components/ui/tooltip';
import { Table, type Column } from '@/components/ui/table';
import { SeverityBadge } from '@/components/severity_badge';

import { fetchFindings } from '@/api/findings';
import type { Finding, FindingFilters, Severity as SeverityType } from '@/api/types';
import Pagination from '@/components/pagination';

/* ── Row type ── */
interface FindingRow extends Record<string, unknown> {
  id: string;
  severity: SeverityType;
  fingerprint: string;
  title: string;
  scan_id: string;
  file_path: string;
  line: number | null;
  enrichment_summary: string | null;
  enrichment_confidence: number | null;
  created_at: string;
}

export default function FindingsPage() {
  const navigate = useNavigate();
const { scanId: paramScanId } = useParams<{ scanId?: string }>();
  const [searchParams] = useSearchParams();
  const scanId = paramScanId || searchParams.get('scan_id') || undefined;
  const { toast, ToastContainer } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [total, setTotal] = useState(0);

// Pagination state (client-side)
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10)

  /* Filters */
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterFilePath, setFilterFilePath] = useState('');
  const [filterSearch, setFilterSearch] = useState('');

  const loadFindings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: FindingFilters = { page: 1, page_size: 500 };
      if (scanId) filters.scan_id = scanId;
      if (filterSeverity) filters.severity = filterSeverity as SeverityType;

      const findingsRes = await fetchFindings(filters);

      let items = findingsRes.items;

      /* Client-side filtering for fields not in API filter */
      if (filterFilePath) {
        items = items.filter((f: Finding) =>
          f.file_path.toLowerCase().includes(filterFilePath.toLowerCase()),
        );
      }
      if (filterSearch) {
        const q = filterSearch.toLowerCase();
        items = items.filter(
          (f: Finding) =>
            f.title.toLowerCase().includes(q) ||
            f.fingerprint.toLowerCase().includes(q),
        );
      }

      setFindings(items);
      setTotal(findingsRes.total);
      setPage(1)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load findings');
    } finally {
      setLoading(false);
    }
  }, [scanId, filterSeverity, filterFilePath, filterSearch]);

  useEffect(() => {
    loadFindings();
  }, [loadFindings]);
  
 // Derived totals for pagination (based on filtered items)
  const totalItems = findings.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

  // Clamp page if page > totalPages (e.g., when pageSize changes or filters shrink results)
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  // Current page of data
  const pagedData = useMemo(() => {
    const start = (page - 1) * pageSize;
    return findings.slice(start, start + pageSize) as unknown as FindingRow[];
  }, [findings, page, pageSize]);


  /* ── Copy link ── */
  function handleCopyLink(findingId: string) {
    const url = `${window.location.origin}/findings/${findingId}`;
    navigator.clipboard?.writeText(url);
    toast('info', 'Link copied to clipboard');
  }

  /* ── Table columns ── */
  const columns: Column<FindingRow>[] = [
    {
      header: 'Severity',
      accessor: 'severity',
      width: '130px',
      render: (val) => <SeverityBadge severity={val as SeverityType} />,
    },
    {
      header: 'Fingerprint',
      accessor: 'fingerprint',
      width: '130px',
      render: (val) => (
        <Tooltip content={val as string}>
          <span style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)' }}>
            {(val as string).slice(0, 12)}…
          </span>
        </Tooltip>
      ),
    },
    {
      header: 'Title',
      accessor: 'title',
      render: (val) => (
        <span style={{ fontWeight: 'var(--font-weight-medium)', color: 'var(--color-neutral-800)' }}>
          {val as string}
        </span>
      ),
    },
    {
      header: 'File',
      accessor: 'file_path',
      render: (val, row) => (
        <span style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)' }}>
          {val as string}{row.line ? `:${row.line}` : ''}
        </span>
      ),
    },
    {
      header: 'Recommendation',
      accessor: 'enrichment_summary',
      width: '200px',
      render: (val) =>
        val ? (
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)' }}>
            {(val as string).length > 60 ? `${(val as string).slice(0, 60)}…` : (val as string)}
          </span>
        ) : (
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-400)' }}>—</span>
        ),
    },
    {
      header: 'Scan ID',
      accessor: 'scan_id',
      width: '120px',
      render: (val) => (
        <Tooltip content={val as string}>
          <span style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)' }}>
            {(val as string).split('-').slice(0, 2).join('-')}…
          </span>
        </Tooltip>
      ),
    },
    {
      header: 'Created',
      accessor: 'created_at',
      width: '120px',
      render: (val) => (
        <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)' }}>
          {new Date(val as string).toLocaleDateString()}
        </span>
        ),
    },
    {
      header: 'Actions',
      accessor: 'id',
      width: '180px',
      render: (_val, row) => {
        const detailUrl = `/findings/${row.id}`;

        return (
        <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
            <Button size="sm" variant="secondary" onClick={() => navigate(detailUrl)}>
            <Eye size={14} /> View
          </Button>
          <Button size="sm" variant="ghost" onClick={() => handleCopyLink(row.id)}>
            <Copy size={14} />
          </Button>
        </div>
        );
      },
    },
  ];

  /* ── Loading ── */
  if (loading) {
    return (
      <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
          Findings
        </h1>
        <Skeleton variant="rect" height={60} />
        <Skeleton variant="rect" height={500} />
      </div>
    );
  }

  /* ── Error ── */
  if (error) {
    return (
      <div style={{ padding: 'var(--space-6)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)', marginBottom: 'var(--space-4)' }}>
          Findings
        </h1>
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--color-critical-600)' }}>
            <p>{error}</p>
            <Button variant="secondary" onClick={loadFindings} style={{ marginTop: 'var(--space-4)' }}>
              Retry
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
          {scanId ? `Findings for Scan ${scanId.substring(0, 8)}...` : 'Findings'}
          <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-500)', fontWeight: 'var(--font-weight-normal)', marginLeft: 'var(--space-2)' }}>
            ({total} total)
          </span>
        </h1>
      </div>

      {/* Filters */}
      <Card padding="sm">
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          <Filter size={16} style={{ color: 'var(--color-neutral-400)', marginBottom: 8 }} />
          <Select
            label="Severity"
            options={[
              { value: '', label: 'All' },
              { value: 'critical', label: 'Critical' },
              { value: 'high', label: 'High' },
              { value: 'medium', label: 'Medium' },
              { value: 'low', label: 'Low' },
              { value: 'info', label: 'Info' },
            ]}
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            wrapperStyle={{ minWidth: 120 }}
          />
          <Input
            label="File path contains"
            placeholder="src/..."
            value={filterFilePath}
            onChange={(e) => setFilterFilePath(e.target.value)}
            wrapperStyle={{ minWidth: 160 }}
          />
          <Input
            label="Search"
            placeholder="Fingerprint or title"
            value={filterSearch}
            onChange={(e) => setFilterSearch(e.target.value)}
            wrapperStyle={{ minWidth: 180 }}
          />
        </div>
      </Card>

      {/* Table or empty */}
      {findings.length === 0 ? (
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
            <FileWarning size={40} style={{ color: 'var(--color-neutral-300)', marginBottom: 'var(--space-3)' }} />
            <p style={{ color: 'var(--color-neutral-500)', fontSize: 'var(--font-size-sm)' }}>
              No findings match the current filters.
            </p>
          </div>
        </Card>
      ) : ( 
    <>
      <Table<FindingRow>
        columns={columns}
        data={pagedData}
        rowKey={(row) => row.id}
     />
    <div
      style={{
        marginTop: 'var(--space-4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 'var(--space-3)',
        flexWrap: 'wrap',
      }}
    >
      {/* Left: per-page */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
        <span style={{ color: 'var(--color-neutral-600)', fontSize: 'var(--font-size-sm)' }}>
          Rows per page:
        </span>
        <select
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
          style={{ padding: '6px 8px', borderRadius: 6 }}
          aria-label="Rows per page"
        >
          {[10, 20, 50, 100].map(size => (
            <option key={size} value={size}>{size}</option>
          ))}
        </select>
        <span style={{ color: 'var(--color-neutral-600)', fontSize: 'var(--font-size-sm)' }}>
          {totalItems === 0 ? '0' : ((page - 1) * pageSize + 1)}–
          {Math.min(page * pageSize, totalItems)} of {totalItems}
        </span>
      </div>

      {/* Right: numbered pages + prev/next */}
      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
      />
    </div>
  </>
      )}

      <ToastContainer />
    </div>
  );
}
