import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Shield,
  FileCode,
  Brain,
  Copy,
  BookPlus,
  ExternalLink,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/toast';
import { CodeViewer } from '@/components/code_viewer';
import { SeverityBadge } from '@/components/severity_badge';

import { fetchFinding, fetchFindingAnalysis, requestAnalysis } from '@/api/findings';
import { createKBCard } from '@/api/knowledge';
import type { Finding, FindingAnalysis } from '@/api/types';



/* ── Parse code snippet from JSON ── */
function parseCodeSnippet(json: Record<string, unknown> | null | undefined): {
  code: string;
  startLine: number;
  highlightLines: number[];
  filePath: string;
} {
  if (!json) return { code: '// No code snippet available', startLine: 1, highlightLines: [], filePath: '' };
  const code = (json.code as string) ?? (json.snippet as string) ?? '// No code snippet available';
  const startLine = (json.start_line as number) ?? (json.startLine as number) ?? 1;
  const highlightLines = (json.highlight_lines as number[]) ?? (json.highlightLines as number[]) ?? [];
  const filePath = (json.file_path as string) ?? (json.filePath as string) ?? '';
  return { code, startLine, highlightLines, filePath };
}

/* ── Parse fix steps from JSON ── */
function parseFixSteps(analysis: FindingAnalysis): string[] {
  const guidance = analysis.fix_guidance;
  if (!guidance) return [];
  // Split by numbered list or newline
  const lines = guidance.split(/\n/).filter((l) => l.trim());
  return lines.map((l) => l.replace(/^\d+\.\s*/, '').trim());
}

/* ── Parse references ── */
function parseReferences(json: Record<string, unknown> | null | undefined): { label: string; url: string }[] {
  if (!json) return [];
  return Object.entries(json).map(([label, url]) => ({ label, url: String(url) }));
}

export default function FindingDetailPage() {
  const { findingId } = useParams<{ findingId: string }>();
  const { toast, ToastContainer } = useToast();

  const [finding, setFinding] = useState<Finding | null>(null);
  const [analysis, setAnalysis] = useState<FindingAnalysis | null>(null);
  const [loadingFinding, setLoadingFinding] = useState(true);
  const [loadingAnalysis, setLoadingAnalysis] = useState(true);
  const [errorFinding, setErrorFinding] = useState<string | null>(null);
  const [errorAnalysis, setErrorAnalysis] = useState<string | null>(null);
  const [addingToKB, setAddingToKB] = useState(false);
  const [generatingAnalysis, setGeneratingAnalysis] = useState(false);

  useEffect(() => {
    if (!findingId) return;

    let cancelled = false;

    async function loadFinding() {
      try {
        const data = await fetchFinding(findingId!);
        if (!cancelled) setFinding(data);
      } catch (err) {
        if (!cancelled) setErrorFinding(err instanceof Error ? err.message : 'Failed to load finding');
      } finally {
        if (!cancelled) setLoadingFinding(false);
      }
    }

    async function loadAnalysis() {
      try {
        const data = await fetchFindingAnalysis(findingId!);
        if (!cancelled) setAnalysis(data);
      } catch (err) {
        if (!cancelled) {
          setErrorAnalysis(err instanceof Error ? err.message : 'No enrichment available');
          // Start polling automatically assuming backend is processing it
          const interval = setInterval(async () => {
            if (cancelled) {
              clearInterval(interval);
              return;
            }
            try {
              const data = await fetchFindingAnalysis(findingId!);
              setAnalysis(data);
              setErrorAnalysis(null);
              clearInterval(interval);
            } catch {
              // Ignore, keep polling
            }
          }, 3000);
        }
      } finally {
        if (!cancelled) setLoadingAnalysis(false);
      }
    }

    loadFinding();
    loadAnalysis();

    return () => { cancelled = true; };
  }, [findingId]);

  /* ── Copy fix steps ── */
  function handleCopyFix() {
    if (!analysis) return;
    const steps = parseFixSteps(analysis);
    const text = steps.map((s, i) => `${i + 1}. ${s}`).join('\n');
    navigator.clipboard?.writeText(text);
    toast('info', 'Fix steps copied to clipboard');
  }

  /* ── Add to validated learnings ── */
  async function handleAddToKB() {
    if (!finding || !analysis) return;
    setAddingToKB(true);
    try {
      await createKBCard({
        cwe_id: finding.cwe_id,
        title: finding.title,
        tags: [`CWE-${finding.cwe_id}`, finding.severity],
        summary: analysis.root_cause,
        fix_steps_json: { steps: parseFixSteps(analysis) },
        content: analysis.fix_guidance,
        source: `finding:${finding.id}`,
      });
      toast('success', 'Added to Knowledge Base as validated learning');
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to add to KB');
    } finally {
      setAddingToKB(false);
    }
  }

  /* ── Generate AI Analysis ── */
  async function handleGenerateAnalysis() {
    if (!findingId) return;
    setGeneratingAnalysis(true);
    setErrorAnalysis(null);
    try {
      await requestAnalysis(findingId);
      // Poll until analysis is ready
      const poll = setInterval(async () => {
        try {
          const data = await fetchFindingAnalysis(findingId);
          setAnalysis(data);
          setErrorAnalysis(null);
          setGeneratingAnalysis(false);
          clearInterval(poll);
        } catch {
          // Keep polling
        }
      }, 3000);
      // Safety timeout after 2 min
      setTimeout(() => {
        clearInterval(poll);
        setGeneratingAnalysis(false);
      }, 120_000);
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to request analysis');
      setGeneratingAnalysis(false);
    }
  }

  /* ── Full loading ── */
  if (loadingFinding) {
    return (
      <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <Skeleton variant="text" width={300} height={28} />
        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 320px', gap: 'var(--space-4)' }}>
          <Skeleton variant="rect" height={350} />
          <Skeleton variant="rect" height={350} />
          <Skeleton variant="rect" height={350} />
        </div>
      </div>
    );
  }

  /* ── Error loading finding ── */
  if (errorFinding || !finding) {
    return (
      <div style={{ padding: 'var(--space-6)' }}>
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--color-critical-600)' }}>
            <Shield size={40} style={{ marginBottom: 'var(--space-3)' }} />
            <p>{errorFinding ?? 'Finding not found'}</p>
            <Link to="/findings" style={{ color: 'var(--color-primary-600)', textDecoration: 'none', fontSize: 'var(--font-size-sm)' }}>
              ← Back to findings
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  // Prioritize Vertex AI excerpt from Analysis, fallback to raw SAST finding JSON mapping.
  const snippet = (analysis?.code_snippet)
    ? {
      code: analysis.code_snippet,
      startLine: 1, // LLM rarely provides strict line numbers natively without line injection
      highlightLines: [],
      filePath: finding.file_path,
    }
    : parseCodeSnippet(finding.code_snippet_json);

  const fixSteps = analysis ? parseFixSteps(analysis) : [];
  const references = analysis ? parseReferences(analysis.references_json) : [];

  return (
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
        <Link to="/findings" style={{ color: 'var(--color-neutral-500)', textDecoration: 'none', fontSize: 'var(--font-size-sm)' }}>
          ← Findings
        </Link>
        <SeverityBadge severity={finding.severity} />
        <h1 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)', margin: 0 }}>
          {finding.title}
        </h1>
      </div>

      {/* Three column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 320px', gap: 'var(--space-4)', alignItems: 'start' }}>

        {/* Left column: Metadata */}
        <Card title="Metadata">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <MetaRow label="CWE" value={`CWE-${finding.cwe_id}`} />
            <MetaRow label="Severity" value={<SeverityBadge severity={finding.severity} size="sm" />} />
            <MetaRow
              label="Fingerprint"
              value={
                <Tooltip content={finding.fingerprint}>
                  <span style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-xs)' }}>
                    {finding.fingerprint.slice(0, 16)}…
                  </span>
                </Tooltip>
              }
            />
            <MetaRow label="File" value={<span style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-xs)', wordBreak: 'break-all' }}>{finding.file_path}{finding.line ? `:${finding.line}` : ''}</span>} />
            <MetaRow
              label="Scan"
              value={
                <Link to={`/scans/${finding.scan_id}`} style={{ color: 'var(--color-primary-600)', textDecoration: 'none', fontSize: 'var(--font-size-xs)' }}>
                  {finding.scan_id.slice(0, 8)}… <ExternalLink size={10} style={{ verticalAlign: 'middle' }} />
                </Link>
              }
            />
            <MetaRow label="Created" value={new Date(finding.created_at).toLocaleString()} />
          </div>
        </Card>

        {/* Center: CodeViewer */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <FileCode size={18} style={{ color: 'var(--color-neutral-500)' }} />
            <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)', margin: 0 }}>
              Code Snippet
            </h2>
          </div>
          <CodeViewer
            code={snippet.code}
            startLine={snippet.startLine}
            highlightLines={snippet.highlightLines}
            filePath={snippet.filePath || finding.file_path}
          />
        </div>

        {/* Right column: AI Enrichment */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Brain size={18} style={{ color: 'var(--color-primary-600)' }} />
            <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)', margin: 0 }}>
              AI Enrichment
            </h2>
          </div>

          {loadingAnalysis ? (
            <Card>
              <Skeleton variant="text" lines={6} />
            </Card>
          ) : errorAnalysis || !analysis ? (
            <Card>
              <div style={{ padding: 'var(--space-4)', textAlign: 'center' }}>
                {generatingAnalysis ? (
                  <>
                    <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)', marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--space-2)' }}>
                      <Brain size={16} /> Generating AI Enrichment...
                    </p>
                    <Skeleton variant="text" width="60%" />
                    <Skeleton variant="text" lines={4} />
                  </>
                ) : (
                  <>
                    <Brain size={32} style={{ color: 'var(--color-neutral-300)', marginBottom: 'var(--space-3)' }} />
                    <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-500)', marginBottom: 'var(--space-4)' }}>
                      No AI analysis has been generated yet for this finding.
                    </p>
                    <Button variant="primary" onClick={handleGenerateAnalysis}>
                      <Brain size={16} /> Generate AI Analysis
                    </Button>
                  </>
                )}
              </div>
            </Card>
          ) : (
            <Card>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                {/* Summary */}
                <div>
                  <h4 style={{ fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', color: 'var(--color-neutral-500)', margin: '0 0 var(--space-1)', letterSpacing: '0.04em' }}>
                    Root Cause
                  </h4>
                  <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)', margin: 0, lineHeight: 'var(--line-height-relaxed)' }}>
                    {analysis.root_cause}
                  </p>
                </div>

                {/* Risk */}
                <div>
                  <h4 style={{ fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', color: 'var(--color-neutral-500)', margin: '0 0 var(--space-1)', letterSpacing: '0.04em' }}>
                    Risk
                  </h4>
                  <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)', margin: 0, lineHeight: 'var(--line-height-relaxed)' }}>
                    {analysis.risk}
                  </p>
                </div>

                {/* Fix Steps */}
                {fixSteps.length > 0 && (
                  <div>
                    <h4 style={{ fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', color: 'var(--color-neutral-500)', margin: '0 0 var(--space-1)', letterSpacing: '0.04em' }}>
                      Fix Steps
                    </h4>
                    <ol style={{ margin: 0, paddingLeft: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                      {fixSteps.map((step, i) => (
                        <li key={i} style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)', lineHeight: 'var(--line-height-relaxed)' }}>
                          {step}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {/* Patch guidance */}
                <div>
                  <h4 style={{ fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', color: 'var(--color-neutral-500)', margin: '0 0 var(--space-1)', letterSpacing: '0.04em' }}>
                    Fix Guidance
                  </h4>
                  <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)', margin: 0, lineHeight: 'var(--line-height-relaxed)' }}>
                    {analysis.fix_guidance}
                  </p>
                </div>

                {/* Confidence */}
                {analysis.confidence != null && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>
                      Confidence
                    </span>
                    <Tooltip content="Model confidence in the analysis quality">
                      <Badge variant={analysis.confidence >= 0.8 ? 'success' : analysis.confidence >= 0.5 ? 'warning' : 'danger'}>
                        {Math.round(analysis.confidence * 100)}%
                      </Badge>
                    </Tooltip>
                  </div>
                )}

                {/* References */}
                {references.length > 0 && (
                  <div>
                    <h4 style={{ fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', color: 'var(--color-neutral-500)', margin: '0 0 var(--space-1)', letterSpacing: '0.04em' }}>
                      References
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                      {references.map((ref) => (
                        <a
                          key={ref.label}
                          href={ref.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-primary-600)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 'var(--space-1)' }}
                        >
                          <ExternalLink size={10} /> {ref.label}
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Provenance */}
                {analysis.provenance_json && (
                  <div>
                    <h4 style={{ fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', color: 'var(--color-neutral-500)', margin: '0 0 var(--space-1)', letterSpacing: '0.04em' }}>
                      Provenance (KB Chunks)
                    </h4>
                    <pre style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)', background: 'var(--color-neutral-50)', padding: 'var(--space-2)', borderRadius: 'var(--radius-sm)', overflow: 'auto', maxHeight: 120 }}>
                      {JSON.stringify(analysis.provenance_json, null, 2)}
                    </pre>
                  </div>
                )}

                {/* CTAs */}
                <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)', flexWrap: 'wrap' }}>
                  <Button size="sm" variant="secondary" onClick={handleCopyFix}>
                    <Copy size={14} /> Copy fix steps
                  </Button>
                  <Button size="sm" variant="primary" onClick={handleAddToKB} loading={addingToKB}>
                    <BookPlus size={14} /> Add to learnings
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      <ToastContainer />
    </div>
  );
}

/* ── Metadata row helper ── */
function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-500)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </span>
      <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)' }}>
        {value}
      </div>
    </div>
  );
}
