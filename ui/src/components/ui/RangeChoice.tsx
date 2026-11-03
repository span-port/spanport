interface RangeChoiceProps {
  choices: readonly { key: string; label: string }[];
  value: string;
  onChange: (key: string) => void;
  label: string;
}

/** A row of buttons where one is chosen, e.g. the time range 15m / 1h / 6h. */
export function RangeChoice({ choices, value, onChange, label }: RangeChoiceProps) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {choices.map((choice) => (
        <button
          key={choice.key}
          type="button"
          className="segment"
          aria-pressed={choice.key === value}
          onClick={() => {
            onChange(choice.key);
          }}
        >
          {choice.label}
        </button>
      ))}
    </div>
  );
}
