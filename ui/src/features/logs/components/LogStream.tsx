import { useCurrentUser } from "../../auth";
import type { LogExplorer } from "../hooks/useLogExplorer";
import { useLogExport } from "../hooks/useLogExport";
import { ExportMenu } from "./ExportMenu";
import { FilterBar } from "./FilterBar";
import { LogTable } from "./LogTable";

/** The log lines with their filters and export. */
export function LogStream({ explorer }: { explorer: LogExplorer }) {
  const { state, rows } = explorer;
  const exporter = useLogExport(explorer.exportRequest, explorer.matchCount, useCurrentUser().data?.role);
  return (
    <section aria-label="Log lines" className="stream">
      <FilterBar
        rows={rows}
        filters={state.filters}
        query={state.query}
        queryMode={state.queryMode}
        matchCount={explorer.matchCount}
        onAddFilter={explorer.addFilter}
        onRemoveFilter={explorer.removeFilter}
        onRemoveLast={explorer.removeLastFilter}
        onClearFilters={explorer.clearFilters}
        onApplyQuery={explorer.applyQuery}
        onSwitchToQuery={explorer.switchToQuery}
        onSwitchToChips={explorer.switchToChips}
      />
      <div className="stream-header">
        <span className="text-secondary text-sm">
          Times in {explorer.timeZone} · newest first · click a line for its fields
        </span>
        <ExportMenu rows={rows} matchCount={explorer.matchCount} exporter={exporter} />
      </div>
      <LogTable
        rows={rows}
        timeZone={explorer.timeZone}
        expandedLogId={explorer.expandedLogId}
        onToggle={explorer.toggleExpanded}
        onFilter={explorer.addFilter}
        onNearEnd={explorer.loadMore}
        footer={explorer.tableMessage}
      />
    </section>
  );
}
