interface SafetyResourcesPanelProps {
  category: string;
  resources: Record<string, string>;
}

export default function SafetyResourcesPanel({
  category,
  resources,
}: SafetyResourcesPanelProps) {
  if (!resources || Object.keys(resources).length === 0) return null;

  const categoryLabel =
    category === 'self_harm'
      ? 'Self-Harm Support'
      : category === 'violence'
        ? 'Violence Prevention'
        : category === 'abuse'
          ? 'Abuse Support'
          : category === 'immediate_danger'
            ? 'Emergency Resources'
            : 'Safety Resources';

  return (
    <div className="space-y-3">
      <h3 className="font-semibold text-amber-200">{categoryLabel}</h3>
      {resources.message && (
        <p className="text-sm text-amber-100/80">{resources.message}</p>
      )}
      <div className="space-y-2 text-sm">
        {resources.international && (
          <div>
            <span className="text-amber-300 font-medium">International: </span>
            <span className="text-amber-100/70">{resources.international}</span>
          </div>
        )}
        {resources.us && (
          <div>
            <span className="text-amber-300 font-medium">US: </span>
            <span className="text-amber-100/70">{resources.us}</span>
          </div>
        )}
        {resources.ph && (
          <div>
            <span className="text-amber-300 font-medium">PH: </span>
            <span className="text-amber-100/70">{resources.ph}</span>
          </div>
        )}
      </div>
      <p className="text-xs text-amber-300/60 mt-2">
        Regulation coaching is suspended while safety concerns are active.
        Only minimal safety metadata is retained.
      </p>
    </div>
  );
}
