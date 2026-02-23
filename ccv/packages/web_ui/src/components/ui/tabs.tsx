import {
  useState,
  useRef,
  useCallback,
  createContext,
  useContext,
  type ReactNode,
  type CSSProperties,
  type KeyboardEvent,
} from 'react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface TabsProps {
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  children: ReactNode;
  className?: string;
}

export interface TabListProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export interface TabProps {
  value: string;
  children: ReactNode;
  disabled?: boolean;
  className?: string;
}

export interface TabPanelProps {
  value: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

/* ── Context ── */
interface TabsContextValue {
  activeTab: string;
  setActiveTab: (v: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext() {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error('Tabs compound components must be used within <Tabs>');
  return ctx;
}

/* ── Tabs root ── */
export function Tabs({ defaultValue = '', value, onValueChange, children, className }: TabsProps) {
  const [internal, setInternal] = useState(defaultValue);
  const activeTab = value ?? internal;
  const setActiveTab = useCallback(
    (v: string) => {
      if (value === undefined) setInternal(v);
      onValueChange?.(v);
    },
    [value, onValueChange],
  );

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div className={clsx(className)}>{children}</div>
    </TabsContext.Provider>
  );
}

/* ── TabList ── */
export function TabList({ children, className, style }: TabListProps) {
  const listRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    const tabs = listRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]:not([disabled])');
    if (!tabs || tabs.length === 0) return;

    const tabsArr = Array.from(tabs);
    const currentIdx = tabsArr.findIndex((t) => t === document.activeElement);
    let nextIdx = currentIdx;

    if (e.key === 'ArrowRight') {
      nextIdx = (currentIdx + 1) % tabsArr.length;
    } else if (e.key === 'ArrowLeft') {
      nextIdx = (currentIdx - 1 + tabsArr.length) % tabsArr.length;
    } else if (e.key === 'Home') {
      nextIdx = 0;
    } else if (e.key === 'End') {
      nextIdx = tabsArr.length - 1;
    } else {
      return;
    }

    e.preventDefault();
    tabsArr[nextIdx].focus();
    tabsArr[nextIdx].click();
  }, []);

  const listStyle: CSSProperties = {
    display: 'flex',
    gap: 'var(--space-1)',
    borderBottom: '2px solid var(--color-neutral-200)',
    ...style,
  };

  return (
    <div
      ref={listRef}
      role="tablist"
      className={clsx(className)}
      style={listStyle}
      onKeyDown={handleKeyDown}
    >
      {children}
    </div>
  );
}

/* ── Tab trigger ── */
export function Tab({ value, children, disabled, className }: TabProps) {
  const { activeTab, setActiveTab } = useTabsContext();
  const isActive = activeTab === value;

  const tabStyle: CSSProperties = {
    padding: 'var(--space-2) var(--space-4)',
    fontSize: 'var(--font-size-sm)',
    fontWeight: isActive ? 'var(--font-weight-semibold)' : 'var(--font-weight-medium)',
    color: isActive ? 'var(--color-primary-600)' : 'var(--color-neutral-500)',
    background: 'none',
    border: 'none',
    borderBottom: `2px solid ${isActive ? 'var(--color-primary-600)' : 'transparent'}`,
    marginBottom: -2,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    transition: 'color var(--transition-fast), border-color var(--transition-fast)',
    whiteSpace: 'nowrap',
  };

  return (
    <button
      role="tab"
      aria-selected={isActive}
      aria-controls={`tabpanel-${value}`}
      id={`tab-${value}`}
      tabIndex={isActive ? 0 : -1}
      disabled={disabled}
      className={clsx(className)}
      style={tabStyle}
      onClick={() => !disabled && setActiveTab(value)}
      onMouseEnter={(e) => {
        if (!isActive && !disabled) {
          (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-700)';
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive && !disabled) {
          (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-500)';
        }
      }}
    >
      {children}
    </button>
  );
}

/* ── TabPanel ── */
export function TabPanel({ value, children, className, style }: TabPanelProps) {
  const { activeTab } = useTabsContext();
  if (activeTab !== value) return null;

  return (
    <div
      role="tabpanel"
      id={`tabpanel-${value}`}
      aria-labelledby={`tab-${value}`}
      tabIndex={0}
      className={clsx(className)}
      style={{ padding: 'var(--space-4) 0', ...style }}
    >
      {children}
    </div>
  );
}
