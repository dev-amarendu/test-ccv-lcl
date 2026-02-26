import { useEffect, useState, type CSSProperties } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  ShieldAlert,
  TrendingUp,
  AlertCircle,
  Activity,
  Play,
  Eye,
  RotateCcw,
  BookOpen,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, type Column } from '@/components/ui/table';
import { useToast } from '@/components/ui/toast';

import { fetchScans, rerunScan } from '@/api/scans';
import { fetchFindings } from '@/api/findings';
import { fetchKBCards } from '@/api/knowledge';
import type { Scan, Finding, KBFixCard, ScanStatus } from '@/api/types';

/* ── Severity display helper ── */
/* ── Status badge variant mapping ── */
function statusBadge(status: ScanStatus) {
  const map: Record<ScanStatus, { variant: 'success' | 'danger' | 'warning' | 'info' | 'default'; label: string }> = {
    completed: { variant: 'success', label: 'Completed' },
    running: { variant: 'info', label: 'Running' },
    queued: { variant: 'default', label: 'Queued' },
    failed: { variant: 'danger', label: 'Failed' },
    cancelled: { variant: 'warning', label: 'Cancelled' },
  };
  const cfg = map[status] ?? { variant: 'default' as const, label: status };
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

/* ── KPI card ── */
function KpiCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: typeof ShieldAlert;
  label: string;
  value: string | number;
  color: string;
}) {
  const cardStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-4)',
    padding: 'var(--space-4)',
  };

  return (
    <Card padding="none">
      <div style={cardStyle}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 'var(--radius-md)',
            background: color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <Icon size={22} style={{ color: '#fff' }} />
        </div>
        <div>
          <p
            style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-neutral-500)',
              margin: 0,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              fontWeight: 'var(--font-weight-semibold)',
            }}
          >
            {label}
          </p>
          <p
            style={{
              fontSize: 'var(--font-size-2xl)',
              fontWeight: 'var(--font-weight-bold)',
              color: 'var(--color-neutral-900)',
              margin: 0,
              lineHeight: 1.2,
            }}
          >
            {value}
          </p>
        </div>
      </div>
    </Card>
  );
}

/* ── Scan row type for Table ── */
interface ScanRow extends Record<string, unknown> {
  id: string;
  status: ScanStatus;
  repo_id: string;
  branch: string;
  created_at: string;
  trigger_type: string;
}

/* ── Main component ── */
export default function DashboardPage() {
  const navigate = useNavigate();
  const { toast, ToastContainer } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [scans, setScans] = useState<Scan[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [kbCards, setKbCards] = useState<KBFixCard[]>([]);
  const [rerunning, setRerunning] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [scansRes, findingsRes, kbRes] = await Promise.all([
          fetchScans({ page: 1, page_size: 10 }),
          fetchFindings({ page: 1, page_size: 200 }),
          fetchKBCards(),
        ]);
        if (cancelled) return;
        setScans(scansRes.items);
        setFindings(findingsRes.items);
        setKbCards(kbRes);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  /* ── Derived KPIs ── */
  const totalOpenFindings = findings.length;
  const criticalOpen = findings.filter((f) => f.severity === 'critical').length;

  const oneWeekAgo = new Date();
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
  const newThisWeek = findings.filter((f) => new Date(f.created_at) >= oneWeekAgo).length;

  const lastScan = scans[0];
  const lastScanStatus = lastScan ? lastScan.status : '—';

  /* ── Rerun handler ── */
  async function handleRerun(scanId: string) {
    setRerunning(scanId);
    try {
      const newScan = await rerunScan(scanId);
      toast('success', 'Scan re-triggered successfully');
      navigate(`/scans/${newScan.id}`);
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to re-run scan');
    } finally {
      setRerunning(null);
    }
  }

  /* ── Scan table columns ── */
  const scanColumns: Column<ScanRow>[] = [
    {
      header: 'Status',
      accessor: 'status',
      width: '120px',
      render: (val) => statusBadge(val as ScanStatus),
    },
    { header: 'Repository', accessor: 'repo_id' },
    { header: 'Branch', accessor: 'branch' },
    {
      header: 'Date',
      accessor: 'created_at',
      render: (val) => new Date(val as string).toLocaleString(),
    },
    {
      header: 'Actions',
      accessor: 'id',
      width: '220px',
      render: (_val, row) => (
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Button size="sm" variant="secondary" onClick={() => navigate(`/scans/${row.id}`)}>
            <Eye size={14} /> View
          </Button>
          <Button
            size="sm"
            variant="ghost"
            loading={rerunning === row.id}
            onClick={() => handleRerun(row.id)}
          >
            <RotateCcw size={14} /> Re-run
          </Button>
        </div>
      ),
    },
  ];

  /* ── Loading state ── */
  if (loading) {
    return (
      <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
          Dashboard
        </h1>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--space-4)' }}>
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} variant="rect" height={88} />
          ))}
        </div>
        <Skeleton variant="rect" height={300} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rect" height={140} />
          ))}
        </div>
      </div>
    );
  }

  /* ── Error state ── */
  if (error) {
    return (
      <div style={{ padding: 'var(--space-6)' }}>
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
            <AlertCircle size={40} style={{ color: 'var(--color-critical-500)', marginBottom: 'var(--space-3)' }} />
            <p style={{ color: 'var(--color-critical-600)', fontSize: 'var(--font-size-md)' }}>{error}</p>
            <Button variant="secondary" onClick={() => window.location.reload()} style={{ marginTop: 'var(--space-4)' }}>
              Retry
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  /* ── Empty state ── */
  if (scans.length === 0 && findings.length === 0) {
    return (
      <div style={{ padding: 'var(--space-6)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)', marginBottom: 'var(--space-6)' }}>
          Dashboard
        </h1>
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-10)' }}>
            <Activity size={48} style={{ color: 'var(--color-neutral-300)', marginBottom: 'var(--space-4)' }} />
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-700)', marginBottom: 'var(--space-2)' }}>
              No scans yet
            </h2>
            <p style={{ color: 'var(--color-neutral-500)', fontSize: 'var(--font-size-sm)', marginBottom: 'var(--space-6)' }}>
              Get started by triggering your first vulnerability scan.
            </p>
            <Button onClick={() => navigate('/scans/manual')}>
              <Play size={16} /> Trigger your first scan
            </Button>
          </div>
        </Card>
        <ToastContainer />
      </div>
    );
  }

  /* ── Normal state ── */
  return (
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
        Dashboard
      </h1>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--space-4)' }}>
        <KpiCard icon={ShieldAlert} label="Total Open Findings" value={totalOpenFindings} color="var(--color-primary-600)" />
        <KpiCard icon={TrendingUp} label="New This Week" value={newThisWeek} color="var(--color-warning-600)" />
        <KpiCard icon={AlertCircle} label="Critical Open" value={criticalOpen} color="var(--color-critical-600)" />
        <KpiCard icon={Activity} label="Last Scan Status" value={lastScanStatus} color="var(--color-success-600)" />
      </div>

      {/* Recent scans */}
      <Card title="Recent Scans">
        <Table<ScanRow>
          columns={scanColumns}
          data={scans as unknown as ScanRow[]}
          rowKey={(row) => row.id}
          emptyMessage="No scans found"
        />
      </Card>

      {/* KB Spotlight */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
          <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-900)' }}>
            Recent Validated Learnings
          </h2>
          <Link to="/knowledge-base" style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-primary-600)', textDecoration: 'none' }}>
            View all →
          </Link>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
          {kbCards.length === 0 ? (
            <Card>
              <div style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--color-neutral-500)' }}>
                <BookOpen size={32} style={{ marginBottom: 'var(--space-2)', color: 'var(--color-neutral-300)' }} />
                <p style={{ fontSize: 'var(--font-size-sm)' }}>No validated learnings yet. Enrich findings to build your knowledge base.</p>
              </div>
            </Card>
          ) : (
            kbCards.slice(0, 3).map((card) => (
              <Card key={card.id}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)', fontSize: 'var(--font-size-sm)' }}>
                      {card.title}
                    </span>
                    {card.approved && <Badge variant="success" size="sm">Approved</Badge>}
                  </div>
                  <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                    <Badge variant="info" size="sm">CWE-{card.cwe_id}</Badge>
                    {card.tags.slice(0, 3).map((t) => (
                      <Badge key={t} size="sm">{t}</Badge>
                    ))}
                  </div>
                  {card.summary && (
                    <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)', margin: 0, lineHeight: 'var(--line-height-relaxed)' }}>
                      {card.summary.length > 120 ? `${card.summary.slice(0, 120)}…` : card.summary}
                    </p>
                  )}
                  <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-400)', margin: 0 }}>
                    Used {card.usage_count} time{card.usage_count !== 1 ? 's' : ''}
                  </p>
                </div>
              </Card>
            ))
          )}
        </div>
      </div>

      <ToastContainer />
    </div>
  );
}
