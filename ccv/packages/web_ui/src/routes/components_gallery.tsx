import { useState } from 'react';
import {
  Star,
  CheckCircle,
  AlertTriangle,
  Info,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Table, type Column } from '@/components/ui/table';
import { Modal } from '@/components/ui/modal';
import { useToast } from '@/components/ui/toast';
import { Tooltip } from '@/components/ui/tooltip';
import { Tabs, TabList, Tab, TabPanel } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { Switch } from '@/components/ui/switch';
import { SeverityBadge } from '@/components/severity_badge';

/* ── Section helper ── */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
      <h2
        style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-semibold)',
          color: 'var(--color-neutral-800)',
          margin: 0,
          borderBottom: '2px solid var(--color-neutral-200)',
          paddingBottom: 'var(--space-2)',
        }}
      >
        {title}
      </h2>
      {children}
    </div>
  );
}

/* ── Sample table data ── */
interface SampleRow extends Record<string, unknown> {
  id: string;
  name: string;
  role: string;
  status: string;
}

const sampleData: SampleRow[] = [
  { id: '1', name: 'Alice', role: 'Engineer', status: 'Active' },
  { id: '2', name: 'Bob', role: 'Designer', status: 'Inactive' },
  { id: '3', name: 'Charlie', role: 'Manager', status: 'Active' },
];

const sampleColumns: Column<SampleRow>[] = [
  { header: 'Name', accessor: 'name' },
  { header: 'Role', accessor: 'role' },
  {
    header: 'Status',
    accessor: 'status',
    render: (val) => (
      <Badge variant={val === 'Active' ? 'success' : 'default'}>{val as string}</Badge>
    ),
  },
];

export default function ComponentsGalleryPage() {
  const { toast, ToastContainer } = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [switchOn, setSwitchOn] = useState(false);
  const [inputVal, setInputVal] = useState('');
  const [selectVal, setSelectVal] = useState('option1');
  const [progress, setProgress] = useState(65);

  return (
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-8)', maxWidth: 960 }}>
      <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
        Components Gallery
      </h1>
      <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)', margin: 0 }}>
        Showcase of all CCV UI components with interactive examples.
      </p>

      {/* ─── Buttons ─── */}
      <Section title="Button">
        <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'center' }}>
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button variant="primary" size="sm">Small</Button>
          <Button variant="primary" size="lg">Large</Button>
          <Button variant="primary" loading>Loading</Button>
          <Button variant="primary" disabled>Disabled</Button>
          <Button variant="secondary"><Star size={14} /> With Icon</Button>
        </div>
      </Section>

      {/* ─── Badge ─── */}
      <Section title="Badge">
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="default">Default</Badge>
          <Badge variant="success">Success</Badge>
          <Badge variant="warning">Warning</Badge>
          <Badge variant="danger">Danger</Badge>
          <Badge variant="info">Info</Badge>
          <Badge variant="success" size="md">Medium</Badge>
        </div>
      </Section>

      {/* ─── SeverityBadge ─── */}
      <Section title="SeverityBadge">
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', alignItems: 'center' }}>
          <SeverityBadge severity="critical" />
          <SeverityBadge severity="high" />
          <SeverityBadge severity="medium" />
          <SeverityBadge severity="low" />
          <SeverityBadge severity="info" />
          <SeverityBadge severity="critical" size="md" />
        </div>
      </Section>

      {/* ─── Card ─── */}
      <Section title="Card">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
          <Card title="Basic Card" subtitle="With subtitle">
            <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)' }}>
              Card body content goes here.
            </p>
          </Card>
          <Card title="Card with Footer" footer={<Button size="sm">Action</Button>}>
            <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)' }}>
              This card has a footer with a button.
            </p>
          </Card>
          <Card padding="lg">
            <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)' }}>
              Large padding, no title.
            </p>
          </Card>
        </div>
      </Section>

      {/* ─── Input ─── */}
      <Section title="Input">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 'var(--space-4)' }}>
          <Input
            label="Standard Input"
            placeholder="Type something…"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
          />
          <Input label="With Error" value="bad value" error="This field is invalid" onChange={() => { }} />
          <Input label="With Hint" value="" hint="This is a helpful hint." onChange={() => { }} />
          <Input label="Disabled" value="Cannot edit" disabled onChange={() => { }} />
        </div>
      </Section>

      {/* ─── Select ─── */}
      <Section title="Select">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 'var(--space-4)' }}>
          <Select
            label="Standard Select"
            options={[
              { value: 'option1', label: 'Option One' },
              { value: 'option2', label: 'Option Two' },
              { value: 'option3', label: 'Option Three' },
            ]}
            value={selectVal}
            onChange={(e) => setSelectVal(e.target.value)}
          />
          <Select
            label="With Placeholder"
            placeholder="Choose…"
            options={[
              { value: 'a', label: 'Alpha' },
              { value: 'b', label: 'Bravo' },
            ]}
            value=""
            onChange={() => { }}
          />
          <Select
            label="With Error"
            options={[{ value: 'x', label: 'X' }]}
            value="x"
            error="Invalid selection"
            onChange={() => { }}
          />
        </div>
      </Section>

      {/* ─── Table ─── */}
      <Section title="Table">
        <Table<SampleRow>
          columns={sampleColumns}
          data={sampleData}
          rowKey={(row) => row.id}
        />
      </Section>

      {/* ─── Modal ─── */}
      <Section title="Modal">
        <Button onClick={() => setModalOpen(true)}>Open Modal</Button>
        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Example Modal">
          <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)' }}>
            This is a modal dialog. Click outside or press Escape to close.
          </p>
          <div style={{ marginTop: 'var(--space-4)', display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)' }}>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={() => setModalOpen(false)}>Confirm</Button>
          </div>
        </Modal>
      </Section>

      {/* ─── Toast ─── */}
      <Section title="Toast">
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          <Button variant="secondary" onClick={() => toast('success', 'Operation succeeded!')}>
            <CheckCircle size={14} /> Success Toast
          </Button>
          <Button variant="secondary" onClick={() => toast('error', 'Something went wrong.')}>
            <AlertTriangle size={14} /> Error Toast
          </Button>
          <Button variant="secondary" onClick={() => toast('warning', 'Please be careful.')}>
            <AlertTriangle size={14} /> Warning Toast
          </Button>
          <Button variant="secondary" onClick={() => toast('info', 'Here is some info.')}>
            <Info size={14} /> Info Toast
          </Button>
        </div>
      </Section>

      {/* ─── Tooltip ─── */}
      <Section title="Tooltip">
        <div style={{ display: 'flex', gap: 'var(--space-4)', alignItems: 'center' }}>
          <Tooltip content="This is a tooltip!">
            <Button variant="secondary">Hover me</Button>
          </Tooltip>
          <Tooltip content="Another tooltip with longer text explaining something">
            <Badge variant="info">Hover this badge</Badge>
          </Tooltip>
        </div>
      </Section>

      {/* ─── Tabs ─── */}
      <Section title="Tabs">
        <Tabs defaultValue="tab1">
          <TabList>
            <Tab value="tab1">First Tab</Tab>
            <Tab value="tab2">Second Tab</Tab>
            <Tab value="tab3" disabled>Disabled</Tab>
          </TabList>
          <TabPanel value="tab1">
            <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)' }}>
              Content for the first tab panel.
            </p>
          </TabPanel>
          <TabPanel value="tab2">
            <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)' }}>
              Content for the second tab panel.
            </p>
          </TabPanel>
          <TabPanel value="tab3">
            <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)' }}>
              You should not see this (disabled tab).
            </p>
          </TabPanel>
        </Tabs>
      </Section>

      {/* ─── Skeleton ─── */}
      <Section title="Skeleton">
        <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', width: 200 }}>
            <Skeleton variant="text" />
            <Skeleton variant="text" lines={3} />
          </div>
          <Skeleton variant="circle" width={48} />
          <Skeleton variant="rect" width={200} height={80} />
        </div>
      </Section>

      {/* ─── Progress ─── */}
      <Section title="Progress">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', maxWidth: 400 }}>
          <Progress value={progress} label="Upload Progress" />
          <Progress value={45} animated color="var(--color-success-600)" label="Build Progress" />
          <Progress value={90} color="var(--color-warning-600)" />
          <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
            <Button size="sm" variant="secondary" onClick={() => setProgress((p) => Math.max(0, p - 10))}>
              -10
            </Button>
            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)' }}>{progress}%</span>
            <Button size="sm" variant="secondary" onClick={() => setProgress((p) => Math.min(100, p + 10))}>
              +10
            </Button>
          </div>
        </div>
      </Section>

      {/* ─── Switch ─── */}
      <Section title="Switch">
        <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', alignItems: 'center' }}>
          <Switch checked={switchOn} onChange={setSwitchOn} label={switchOn ? 'On' : 'Off'} />
          <Switch checked={true} onChange={() => { }} label="Always On" />
          <Switch checked={false} onChange={() => { }} label="Disabled" disabled />
        </div>
      </Section>

      <ToastContainer />
    </div>
  );
}