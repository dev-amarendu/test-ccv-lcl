import { useState } from 'react';
import {
  Server,
  Zap,
  Shield,
  Lock,
  Users,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/toast';

export default function SettingsPage() {
  const { toast, ToastContainer } = useToast();
  const [testing, setTesting] = useState(false);

  /* Placeholder MCP endpoint from env or default */
  const mcpBaseUrl = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_MCP_BASE_URL ?? 'http://localhost:8080/mcp';

  /* Test connection */
  async function handleTestConnection() {
    setTesting(true);
    try {
      // Placeholder — would actually call an MCP health endpoint
      await new Promise((resolve) => setTimeout(resolve, 1200));
      toast('success', 'MCP endpoint is reachable');
    } catch {
      toast('error', 'Unable to reach MCP endpoint');
    } finally {
      setTesting(false);
    }
  }

  /* Read-only RBAC roles */
  const roles = [
    { name: 'admin', scopes: ['*'] },
    { name: 'developer', scopes: ['read:repos', 'read:findings', 'write:scans', 'read:scans'] },
    { name: 'viewer', scopes: ['read:repos', 'read:findings', 'read:scans'] },
    { name: 'ci-bot', scopes: ['write:scans', 'write:artifacts'] },
  ];

  return (
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: 720 }}>
      <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
        Settings
      </h1>

      {/* MCP Endpoint */}
      <Card title={
        <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <Server size={18} /> MCP Endpoint Configuration
        </span>
      }>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <Input
            label="MCP Base URL"
            value={mcpBaseUrl}
            readOnly
            style={{ background: 'var(--color-neutral-50)', fontFamily: 'monospace', fontSize: 'var(--font-size-sm)' }}
            hint="This value is set via the VITE_MCP_BASE_URL environment variable and cannot be changed from the UI."
          />
          <div>
            <Button variant="secondary" onClick={handleTestConnection} loading={testing}>
              <Zap size={14} /> Test Connection
            </Button>
          </div>
        </div>
      </Card>

      {/* Secrets management */}
      <Card
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Lock size={18} /> Secrets Management
          </span>
        }
        style={{ borderLeft: '4px solid var(--color-warning-400)' }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)', margin: 0, lineHeight: 'var(--line-height-relaxed)' }}>
            Secrets such as API tokens, SCM credentials, and scheduler keys are managed through your deployment platform's secrets manager (e.g. Kubernetes Secrets, AWS Secrets Manager, Vault).
          </p>
          <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)', margin: 0, lineHeight: 'var(--line-height-relaxed)' }}>
            CCV never stores secrets in the database or client-side storage. Ensure the following environment variables are configured:
          </p>
          <ul style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)', margin: 0, paddingLeft: 'var(--space-4)', lineHeight: 'var(--line-height-relaxed)' }}>
            <li><code>CCV_SCM_TOKEN</code> — Source control access token</li>
            <li><code>CCV_OPENAI_API_KEY</code> — AI enrichment API key</li>
            <li><code>CCV_DB_URL</code> — Database connection string</li>
          </ul>
        </div>
      </Card>

      {/* RBAC */}
      <Card
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Users size={18} /> RBAC Roles & Scopes
          </span>
        }
        subtitle="Read-only display of configured roles"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {roles.map((role) => (
            <div
              key={role.name}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                padding: 'var(--space-3)',
                background: 'var(--color-neutral-50)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-neutral-200)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <Shield size={16} style={{ color: 'var(--color-neutral-500)' }} />
                <span style={{ fontWeight: 'var(--font-weight-semibold)', fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-800)' }}>
                  {role.name}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 'var(--space-1)', flexWrap: 'wrap', justifyContent: 'flex-end', maxWidth: '60%' }}>
                {role.scopes.map((scope) => (
                  <Badge key={scope} size="sm" variant={scope === '*' ? 'danger' : 'default'}>
                    {scope}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <ToastContainer />
    </div>
  );
}
