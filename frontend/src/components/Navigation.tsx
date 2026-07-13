interface NavItem {
  label: string;
  href: string;
  active?: boolean;
  disabled?: boolean;
  icon?: string;
}

/* ── AppNav ───────────────────────────────────────────────────────── */

interface AppNavProps {
  items: NavItem[];
  className?: string;
}

export function AppNav({ items, className = '' }: AppNavProps) {
  return (
    <nav className={`safe-bottom bg-surface border-t border-border ${className}`} aria-label="Main navigation">
      <ul className="flex justify-around py-2">
        {items.map((item) => (
          <li key={item.href}>
            {item.disabled ? (
              <span className="flex flex-col items-center gap-0.5 px-3 py-2 text-muted/40 cursor-not-allowed text-xs">
                <span className="text-lg">{item.icon || '○'}</span>
                {item.label}
              </span>
            ) : (
              <a
                href={item.href}
                className={`flex flex-col items-center gap-0.5 px-3 py-2 text-xs transition-colors duration-inline
                  ${item.active ? 'text-action font-semibold' : 'text-muted hover:text-ink'}`}
                aria-current={item.active ? 'page' : undefined}
              >
                <span className="text-lg">{item.icon || '○'}</span>
                {item.label}
              </a>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}

/* ── FocusedFlowNav ───────────────────────────────────────────────── */

interface FocusedFlowNavProps {
  onBack: () => void;
  onSafety?: () => void;
  title?: string;
}

export function FocusedFlowNav({ onBack, onSafety, title }: FocusedFlowNavProps) {
  return (
    <nav className="safe-top flex items-center justify-between px-4 py-3 bg-surface border-b border-border" aria-label="Focused navigation">
      <button onClick={onBack} className="text-action font-semibold text-sm hover:underline focus-visible:ring-3 focus-visible:ring-action rounded-control px-2 py-1">
        ← Back
      </button>
      {title && <span className="text-sm font-semibold text-ink truncate mx-2">{title}</span>}
      {onSafety && (
        <button
          onClick={onSafety}
          className="text-xs text-muted hover:text-danger transition-colors duration-inline focus-visible:ring-3 focus-visible:ring-danger rounded-control px-2 py-1"
        >
          Need immediate help?
        </button>
      )}
    </nav>
  );
}
