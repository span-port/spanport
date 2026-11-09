import { useState } from "react";

import { Button } from "../../../components/ui/Button";
import { CustomRangeDialog } from "../../../components/ui/CustomRangeDialog";
import { TimeRangePicker } from "../../../components/ui/TimeRangePicker";
import { TRACE_RANGE_RULES } from "../../../constants/traces";
import type { useRequestRange } from "../hooks/useRequestRange";

/** The APIs screens' time range: quick ranges, Custom (with its dialog), timezone and Refresh. */
export function RangeControls({ range }: { range: ReturnType<typeof useRequestRange> }) {
  const [customOpen, setCustomOpen] = useState(false);
  return (
    <div className="logs-header-controls">
      <TimeRangePicker
        range={range.range}
        timeZone={range.timeZone}
        customOpen={customOpen}
        rules={TRACE_RANGE_RULES}
        onSelectRange={(next) => {
          setCustomOpen(false);
          range.selectRange(next);
        }}
        onSelectTimeZone={range.setTimeZone}
        onToggleCustom={() => {
          setCustomOpen(!customOpen);
        }}
      />
      <Button onClick={range.refresh}>Refresh</Button>
      {customOpen && (
        <CustomRangeDialog
          range={range.range}
          timeZone={range.timeZone}
          rules={TRACE_RANGE_RULES}
          onApply={(next) => {
            setCustomOpen(false);
            range.selectRange(next);
          }}
          onCancel={() => {
            setCustomOpen(false);
          }}
        />
      )}
    </div>
  );
}
