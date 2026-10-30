"""Log lines as file rows: CSV for spreadsheets, NDJSON (one JSON object per line) for tools.

Times are ISO 8601 UTC. CSV cells that a spreadsheet would run as a formula get a leading quote.
"""

import csv
import io

from spanport_server.core.constants import (
    CSV_COLUMNS,
    CSV_FORMULA_GUARD,
    CSV_FORMULA_PREFIXES,
    LOG_FIELD_ALIASES,
)
from spanport_server.schemas.log_search import ExportFormat, LogItem

CLIENT_IP_ATTRIBUTE = LOG_FIELD_ALIASES["ip"]
USER_ID_ATTRIBUTE = LOG_FIELD_ALIASES["user"]


def safe_cell(value: str) -> str:
    """A CSV cell that Excel or Sheets won't run as a formula (e.g. "=HYPERLINK(...)")."""
    return CSV_FORMULA_GUARD + value if value.startswith(CSV_FORMULA_PREFIXES) else value


def csv_line(cells: list[str]) -> str:
    """One CSV line with the csv module's quoting (commas, quotes, line breaks)."""
    buffer = io.StringIO()
    csv.writer(buffer).writerow(cells)
    return buffer.getvalue()


def csv_header() -> str:
    """The CSV header row."""
    return csv_line(list(CSV_COLUMNS))


def csv_row(item: LogItem) -> str:
    """One log line as a CSV row, in CSV_COLUMNS order."""
    cells = [
        item.ts.isoformat(),
        item.level,
        item.service,
        item.message,
        item.trace_id,
        item.span_id,
        item.attributes.get(CLIENT_IP_ATTRIBUTE, ""),
        item.attributes.get(USER_ID_ATTRIBUTE, ""),
    ]
    return csv_line([safe_cell(cell) for cell in cells])


def ndjson_row(item: LogItem) -> str:
    """One log line as a JSON object with every field, then a newline."""
    return item.model_dump_json() + "\n"


def file_header(export_format: ExportFormat) -> str:
    """What the file starts with: the CSV header row, or nothing for NDJSON."""
    return csv_header() if export_format is ExportFormat.CSV else ""


def file_row(export_format: ExportFormat, item: LogItem) -> str:
    """One log line in the export's format."""
    return csv_row(item) if export_format is ExportFormat.CSV else ndjson_row(item)
