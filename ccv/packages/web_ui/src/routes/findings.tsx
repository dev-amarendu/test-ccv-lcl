import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
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
import { SeverityBadge, type Severity } from '@/components/severity_badge';

import { fetchFindings } from '@/api/findings';
import { fetchRepos } from '@/api/repos';
import type { Finding, FindingFilters, Repo, Severity as SeverityType } from '@/api/types';

/* ── Severity display mapping ── */
const severityDisplayMap: Record<SeverityType, Severity> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Informational',
};

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
  const { toast, ToastContainer } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [repos, setRepos] = useState<Repo[]>([]);
  const [total, setTotal] = useState(0);

  /* Filters */
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterRepo, setFilterRepo] = useState('');
  const [filterFilePath, setFilterFilePath] = useState('');
  const [filterSearch, setFilterSearch] = useState('');
  const [filterConfMin, setFilterConfMin] = useState('');
  const [filterConfMax, setFilterConfMax] = useState('');

  const loadFindings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: FindingFilters = { page: 1, page_size: 50 };
      if (filterSeverity) filters.severity = filterSeverity as SeverityType;

      const [findingsRes, reposRes] = await Promise.all([
        fetchFindings(filters),
        fetchRepos(),
      ]);

      let items = findingsRes.items;

      /* Client-side filtering for fields not in API filter */
      if (filterFilePath) {
        items = items.filter((f) =>
          f.file_path.toLowerCase().includes(filterFilePath.toLowerCase()),
        );
      }
      if (filterSearch) {
        const q = filterSearch.toLowerCase();
        items = items.filter(
          (f) =>
            f.title.toLowerCase().includes(q) ||
            f.fingerprint.toLowerCase().includes(q),
        );
      }
      if (filterConfMin) {
        const min = parseFloat(filterConfMin);
        if (!isNaN(min)) items = items.filter((f) => (f.enrichment_confidence ?? 0) >= min);
      }
      if (filterConfMax) {
        const max = parseFloat(filterConfMax);
        if (!isNaN(max)) items = items.filter((f) => (f.enrichment_confidence ?? 1) <= max);
      }

      setFindings(items);
      setTotal(findingsRes.total);
      setRepos(reposRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load findings');
    } finally {
      setLoading(false);
    }
  }, [filterSeverity, filterFilePath, filterSearch, filterConfMin, filterConfMax]);

  useEffect(() => {
    loadFindings();
  }, [loadFindings]);

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
      render: (val) => <SeverityBadge severity={severityDisplayMap[val as SeverityType]} />,
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
      header: 'Enrichment',
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
      header: 'Confidence',
      accessor: 'enrichment_confidence',
      width: '100px',
      align: 'center',
      render: (val) =>
        val != null ? (
          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-semibold)' }}>
            {Math.round((val as number) * 100)}%
          </span>
        ) : (
          <span style={{ color: 'var(--color-neutral-400)' }}>—</span>
        ),
    },
    {
      header: 'Actions',
      accessor: 'id',
      width: '180px',
      render: (_val, row) => (
        <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
          <Button size="sm" variant="secondary" onClick={() => navigate(`/findings/${row.id}`)}>
            <Eye size={14} /> View
          </Button>
          <Button size="sm" variant="ghost" onClick={() => handleCopyLink(row.id)}>
            <Copy size={14} />
          </Button>
        </div>
      ),
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
          Findings
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
          <Input
            label="Conf. min"
            type="number"
            placeholder="0"
            value={filterConfMin}
            onChange={(e) => setFilterConfMin(e.target.value)}
            wrapperStyle={{ minWidth: 80 }}
            min={0}
            max={1}
            step={0.1}
          />
          <Input
            label="Conf. max"
            type="number"
            placeholder="1"
            value={filterConfMax}
            onChange={(e) => setFilterConfMax(e.target.value)}
            wrapperStyle={{ minWidth: 80 }}
            min={0}
            max={1}
            step={0.1}
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
        <Table<FindingRow>
          columns={columns}
          data={findings as unknown as FindingRow[]}
          rowKey={(row) => row.id}
        />
      )}

      <ToastContainer />
    </div>
  );
}
