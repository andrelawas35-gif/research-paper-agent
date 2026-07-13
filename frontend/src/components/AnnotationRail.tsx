interface AnnotationStep {
  label: string;
  state: 'active' | 'completed' | 'future';
}

interface AnnotationRailProps {
  steps: AnnotationStep[];
  currentIndex: number;
  className?: string;
}

export function AnnotationRail({ steps, currentIndex, className = '' }: AnnotationRailProps) {
  return (
    <nav className={`annotation-rail ${className}`} aria-label="Regulation progress">
      {steps.map((step, i) => {
        const state = i < currentIndex ? 'completed' : i === currentIndex ? 'active' : 'future';
        return (
          <div key={i} className={`annotation-node ${state}`} aria-current={state === 'active' ? 'step' : undefined}>
            <span className={`annotation-dot ${state}`} aria-hidden="true" />
            <span className="text-xs">{step.label}</span>
          </div>
        );
      })}
    </nav>
  );
}
