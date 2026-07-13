interface SourceStampProps {
  sourceType: 'paper' | 'note' | 'model' | 'import' | 'backfill';
  domain?: string;
  date?: string;
  sensitivity?: 'low' | 'medium' | 'high' | 'identity_shaping';
  processing?: string;
}

const sourceLabels: Record<string, string> = {
  paper: 'Paper',
  note: 'Note',
  model: 'Model-assisted',
  import: 'Import',
  backfill: 'Historical backfill',
};

const sensitivityIcons: Record<string, string> = {
  low: '',
  medium: '◐',
  high: '●',
  identity_shaping: '⬤',
};

export function SourceStamp({ sourceType, domain, date, sensitivity }: SourceStampProps) {
  return (
    <div className="source-stamp" title={`Source: ${sourceLabels[sourceType]}${sensitivity ? ` · ${sensitivity.replace('_', ' ')}` : ''}`}>
      <span className="font-semibold">{sourceLabels[sourceType] || sourceType}</span>
      {domain && <span>· {domain}</span>}
      {sensitivity && sensitivity !== 'low' && (
        <span className="text-caution" aria-label={`Sensitivity: ${sensitivity.replace('_', ' ')}`}>
          {sensitivityIcons[sensitivity]}
        </span>
      )}
      {date && <span>· {date}</span>}
    </div>
  );
}
