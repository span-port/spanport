import { MAIN_LEVELS } from "../../../constants/logs";
import { NUMBER_LOCALE } from "../../../constants/ui";
import { LevelTag } from "./LevelTag";

interface LevelCardsProps {
  /** Lines per level in the range (with the other filters, never the level filter); undefined while loading. */
  byLevel: Record<string, number> | undefined;
  /** Levels picked; empty means all are shown. */
  shownLevels: string[];
  onToggle: (level: string) => void;
  onShowAll: () => void;
}

const numberFormat = new Intl.NumberFormat(NUMBER_LOCALE);
const mainLevels = new Set<string>(MAIN_LEVELS);

/**
 * The level filter: one card per level with its count in the range. Click to show only that
 * level, click more to add them, click again to remove. Counts never drop to 0 because a level
 * is hidden; hidden cards say so instead.
 */
export function LevelCards({ byLevel, shownLevels, onToggle, onShowAll }: LevelCardsProps) {
  const otherLevels = Object.keys(byLevel ?? {}).filter((level) => !mainLevels.has(level));
  const filtering = shownLevels.length > 0;
  return (
    <section className="level-cards-section" aria-label="Levels">
      <div className="level-cards">
        {[...MAIN_LEVELS, ...otherLevels].map((level) => {
          const shown = !filtering || shownLevels.includes(level);
          return (
            <button
              key={level}
              type="button"
              className="level-card"
              aria-pressed={filtering && shown}
              data-hidden={!shown}
              onClick={() => {
                onToggle(level);
              }}
            >
              <span className="level-card-label">
                <LevelTag level={level} /> {shown ? "in this range" : "hidden"}
              </span>
              <span className="level-card-count">
                {byLevel ? numberFormat.format(byLevel[level] ?? 0) : "..."}
              </span>
            </button>
          );
        })}
      </div>
      <p className="level-cards-hint text-secondary text-sm">
        {filtering ? (
          <>
            Showing {shownLevels.join(" and ")} only.{" "}
            <button type="button" className="link-button" onClick={onShowAll}>
              Show all levels
            </button>
          </>
        ) : (
          "Click a level to show only those lines."
        )}
      </p>
    </section>
  );
}
