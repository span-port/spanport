import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { useLogExplorer } from "../hooks/useLogExplorer";
import { LevelCards } from "./LevelCards";
import { LogsHeader } from "./LogsHeader";
import { LogStream } from "./LogStream";

/** The Logs screen: follow new lines live, or search a range, with filters and per-level counts. */
export function LogsPage() {
  const explorer = useLogExplorer();
  const errors = [
    explorer.projects.error,
    explorer.search.error,
    explorer.counts.error,
    explorer.tailError,
  ].filter((error) => error !== null);
  return (
    <div className="logs-page">
      <LogsHeader explorer={explorer} />
      {errors.map((error, index) => (
        <ErrorBanner key={index} error={error} />
      ))}
      <LevelCards
        byLevel={explorer.counts.data?.by_level}
        shownLevels={explorer.shownLevels}
        onToggle={explorer.toggleLevel}
        onShowAll={explorer.showAllLevels}
      />
      <LogStream explorer={explorer} />
    </div>
  );
}
