import { useState } from "react";

import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { EXPORT_FORMATS } from "../../../constants/logs";
import { NUMBER_LOCALE } from "../../../constants/ui";
import { useCopyText } from "../../../hooks/useCopyText";
import { toNdjson } from "../../../lib/copyFormats";
import type { useLogExport } from "../hooks/useLogExport";
import type { LogItem } from "../types";

const numberFormat = new Intl.NumberFormat(NUMBER_LOCALE);

interface ExportMenuProps {
  rows: LogItem[];
  /** Lines the whole search matches (the download), or undefined while counting. */
  matchCount: number | undefined;
  exporter: ReturnType<typeof useLogExport>;
}

/** Copy the lines on screen, or download everything the search matches as CSV or JSON lines. */
export function ExportMenu({ rows, matchCount, exporter }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const copyLines = useCopyText();
  const lines = matchCount === undefined ? "" : `${numberFormat.format(matchCount)} lines · `;
  return (
    <div
      className="menu"
      onKeyDown={(event) => {
        if (event.key === "Escape") setOpen(false);
      }}
    >
      <Button
        aria-expanded={open}
        aria-haspopup="menu"
        disabled={exporter.downloading}
        onClick={() => {
          setOpen(!open);
        }}
      >
        {exporter.downloading ? "Downloading..." : copyLines.copied ? "Copied" : "Export"} ▾
      </Button>
      {open && (
        <div className="menu-list" role="menu">
          <button
            type="button"
            role="menuitem"
            className="menu-item"
            disabled={rows.length === 0}
            onClick={() => {
              copyLines.copy(toNdjson(rows));
              setOpen(false);
            }}
          >
            Copy {numberFormat.format(rows.length)} visible lines
            <span className="menu-item-detail">as JSON lines</span>
          </button>
          {EXPORT_FORMATS.map((choice) => (
            <button
              key={choice.format}
              type="button"
              role="menuitem"
              className="menu-item"
              disabled={exporter.unavailable !== null || matchCount === 0}
              title={exporter.unavailable ?? undefined}
              onClick={() => {
                exporter.download(choice.format);
                setOpen(false);
              }}
            >
              {choice.label}
              <span className="menu-item-detail">{exporter.unavailable ?? `${lines}${choice.detail}`}</span>
            </button>
          ))}
        </div>
      )}
      {exporter.error && <ErrorBanner error={exporter.error} />}
    </div>
  );
}
