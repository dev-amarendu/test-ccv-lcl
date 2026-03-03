import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
    Activity,
    GitBranch,
    Calendar,
    AlertCircle,
    Play,
    CheckCircle,
    XCircle,
    Clock,
    ExternalLink,
    Shield,
    RotateCcw
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';

import { fetchScan, rerunScan } from '@/api/scans';
import { fetchFindings } from '@/api/findings';
import type { Scan, ScanStatus } from '@/api/types';

/* ── Status badge helper ── */
function statusBadge(status: ScanStatus) {
    const map: Record<ScanStatus, { variant: 'success' | 'danger' | 'warning' | 'info' | 'default'; label: string; icon: any }> = {
        completed: { variant: 'success', label: 'Completed', icon: CheckCircle },
        running: { variant: 'info', label: 'Running', icon: Activity },
        queued: { variant: 'default', label: 'Queued', icon: Clock },
        failed: { variant: 'danger', label: 'Failed', icon: XCircle },
        cancelled: { variant: 'warning', label: 'Cancelled', icon: AlertCircle },
    };
    const cfg = map[status] ?? { variant: 'default' as const, label: status, icon: Activity };
    const Icon = cfg.icon;
    return (
        <Badge variant={cfg.variant} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <Icon size={12} /> {cfg.label}
        </Badge>
    );
}

export default function ScanDetailPage() {
    const { scanId } = useParams<{ scanId: string }>();
    const navigate = useNavigate();
    const { toast, ToastContainer } = useToast();

    const [scan, setScan] = useState<Scan | null>(null);
    const [findingCount, setFindingCount] = useState<number | null>(null);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [rerunning, setRerunning] = useState(false);

    useEffect(() => {
        if (!scanId) return;

        let cancelled = false;

        async function loadData() {
            try {
                const data = await fetchScan(scanId!);
                if (cancelled) return;
                setScan(data);

                // Fetch just the first page of findings to get the total count
                const findingsRes = await fetchFindings({ scan_id: scanId, page: 1, page_size: 1 });
                if (!cancelled) setFindingCount(findingsRes.total);

            } catch (err) {
                if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load scan');
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        loadData();

        return () => { cancelled = true; };
    }, [scanId]);

    /* ── Rerun handler ── */
    async function handleRerun() {
        if (!scan) return;
        setRerunning(true);
        try {
            const newScan = await rerunScan(scan.id);
            toast('success', 'Scan re-triggered successfully');
            navigate(`/scans/${newScan.id}`);
        } catch (err) {
            toast('error', err instanceof Error ? err.message : 'Failed to re-run scan');
        } finally {
            setRerunning(false);
        }
    }

    /* ── Loading ── */
    if (loading) {
        return (
            <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                <Skeleton variant="text" width={300} height={28} />
                <Skeleton variant="rect" height={250} />
            </div>
        );
    }

    /* ── Error  ── */
    if (error || !scan) {
        return (
            <div style={{ padding: 'var(--space-6)' }}>
                <Card>
                    <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--color-critical-600)' }}>
                        <AlertCircle size={40} style={{ marginBottom: 'var(--space-3)' }} />
                        <p>{error ?? 'Scan not found'}</p>
                        <Link to="/scans" style={{ color: 'var(--color-primary-600)', textDecoration: 'none', fontSize: 'var(--font-size-sm)' }}>
                            ← Back to scans
                        </Link>
                    </div>
                </Card>
            </div>
        );
    }

    return (
        <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>

            {/* Header */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                    <Link to="/scans" style={{ color: 'var(--color-neutral-500)', textDecoration: 'none', fontSize: 'var(--font-size-sm)' }}>
                        ← All Scans
                    </Link>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
                    <div>
                        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)', margin: 0, display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                            Scan Details
                            {statusBadge(scan.status)}
                        </h1>
                        <p style={{ color: 'var(--color-neutral-500)', fontSize: 'var(--font-size-sm)', margin: 'var(--space-1) 0 0 0' }}>
                            ID: {scan.id}
                        </p>
                    </div>

                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                        {scan.status === 'completed' && findingCount !== null && (
                            <Button variant="primary" onClick={() => navigate(`/findings?scan_id=${scan.id}`)}>
                                <Shield size={16} /> View {findingCount} Findings
                            </Button>
                        )}
                        <Button variant="secondary" loading={rerunning} onClick={handleRerun}>
                            <RotateCcw size={16} /> Re-run Scan
                        </Button>
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 'var(--space-4)' }}>
                {/* Left Column: Repository & Status */}
                <Card title="Configuration & Status">
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                        <MetaRow icon={Activity} label="Trigger Type" value={<span style={{ textTransform: 'capitalize' }}>{scan.trigger_type}</span>} />
                        <MetaRow icon={Activity} label="Repository" value={scan.repo_id} />
                        <MetaRow icon={GitBranch} label="Branch / Commit" value={
                            <span>{scan.branch} {scan.commit_sha && <span style={{ fontFamily: 'monospace', color: 'var(--color-neutral-500)', marginLeft: 'var(--space-2)' }}>({scan.commit_sha.slice(0, 7)})</span>}</span>
                        } />

                        <div style={{ marginTop: 'var(--space-2)', paddingTop: 'var(--space-4)', borderTop: '1px solid var(--color-neutral-200)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                            <MetaRow icon={Calendar} label="Created At" value={new Date(scan.created_at).toLocaleString()} />
                            <MetaRow icon={Play} label="Started At" value={scan.started_at ? new Date(scan.started_at).toLocaleString() : '—'} />
                            <MetaRow icon={CheckCircle} label="Finished At" value={scan.finished_at ? new Date(scan.finished_at).toLocaleString() : '—'} />
                        </div>
                    </div>
                </Card>

                {/* Right Column: Error Details & External IDs */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                    {scan.status === 'failed' && (
                        <Card title="Failure Reason" style={{ borderLeft: '4px solid var(--color-critical-500)' }}>
                            <div style={{ display: 'flex', gap: 'var(--space-3)', color: 'var(--color-critical-700)', background: 'var(--color-critical-50)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)' }}>
                                <AlertCircle size={20} style={{ flexShrink: 0, marginTop: 2 }} />
                                <span style={{ fontSize: 'var(--font-size-sm)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                                    {scan.error_message || 'An unknown pipeline error occurred.'}
                                </span>
                            </div>
                        </Card>
                    )}

                    <Card title="External System Identifiers">
                        {scan.external_build_id ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                                <MetaRow icon={ExternalLink} label="Veracode App ID" value={<span style={{ fontFamily: 'monospace' }}>{scan.external_app_id || '—'}</span>} />
                                <MetaRow icon={ExternalLink} label="Veracode Build ID" value={<span style={{ fontFamily: 'monospace' }}>{scan.external_build_id}</span>} />
                            </div>
                        ) : (
                            <p style={{ color: 'var(--color-neutral-500)', fontSize: 'var(--font-size-sm)', margin: 0 }}>
                                No remote Veracode IDs have been registered for this scan yet.
                            </p>
                        )}
                    </Card>
                </div>
            </div>

            <ToastContainer />
        </div>
    );
}

/* ── Metadata row helper ── */
function MetaRow({ icon: Icon, label, value }: { icon: any, label: string; value: React.ReactNode }) {
    return (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
            <Icon size={16} style={{ color: 'var(--color-neutral-400)', marginTop: 2 }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-500)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {label}
                </span>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-900)', fontWeight: 'var(--font-weight-medium)' }}>
                    {value}
                </div>
            </div>
        </div>
    );
}
