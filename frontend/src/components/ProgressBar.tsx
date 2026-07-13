interface Step {
  id: string;
  label: string;
  number: number;
}

interface ProgressBarProps {
  steps: readonly Step[];
  currentStep: string;
  completed: boolean;
}

export default function ProgressBar({
  steps,
  currentStep,
  completed,
}: ProgressBarProps) {
  const currentIndex = steps.findIndex((s) => s.id === currentStep);
  const progress = completed
    ? 100
    : ((currentIndex) / (steps.length - 1)) * 100;

  return (
    <div className="space-y-3">
      {/* Dots + labels */}
      <div className="flex items-center justify-between">
        {steps.map((step, i) => {
          const isActive = step.id === currentStep;
          const isPast = i < currentIndex || completed;
          return (
            <div key={step.id} className="flex flex-col items-center gap-1">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
                  completed || isPast
                    ? 'bg-emerald-600 border-emerald-500 text-white'
                    : isActive
                      ? 'bg-indigo-600 border-indigo-400 text-white'
                      : 'bg-slate-800 border-slate-700 text-slate-500'
                }`}
              >
                {completed || isPast ? '✓' : step.number}
              </div>
              <span
                className={`text-[10px] hidden sm:block ${
                  isActive ? 'text-indigo-300' : 'text-slate-500'
                }`}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
