from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median

TIME_FORMAT = "%Y/%m/%d %H:%M"
SUPPORTED_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk")


@dataclass(slots=True)
class EventRow:
    timestamp: datetime
    prcp: float | None
    level: float | None
    inflow: float | None
    outflow: float | None


def _read_text(path: Path) -> tuple[str, str]:
    raw_bytes = path.read_bytes()
    for encoding in SUPPORTED_ENCODINGS:
        try:
            return encoding, raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, "unsupported encoding")


def _normalize(value: str | None) -> str:
    return "" if value is None else value.replace("\u3000", " ").strip()


def _parse_optional_float(value: str | None) -> float | None:
    normalized = _normalize(value)
    if normalized == "":
        return None
    return float(normalized)


def load_event_rows(path: str | Path) -> tuple[list[EventRow], list[str]]:
    csv_path = Path(path)
    _encoding, text = _read_text(csv_path)
    rows: list[EventRow] = []
    warnings: list[str] = []

    reader = csv.DictReader(text.splitlines())
    for line_number, raw in enumerate(reader, start=2):
        if raw is None:
            continue
        timestamp_text = _normalize(raw.get("time"))
        if timestamp_text == "":
            warnings.append(f"line {line_number}: missing time value")
            continue
        try:
            timestamp = datetime.strptime(timestamp_text, TIME_FORMAT)
        except ValueError:
            warnings.append(f"line {line_number}: invalid time value {timestamp_text!r}")
            continue

        try:
            rows.append(
                EventRow(
                    timestamp=timestamp,
                    prcp=_parse_optional_float(raw.get("prcp")),
                    level=_parse_optional_float(raw.get("level")),
                    inflow=_parse_optional_float(raw.get("inflow")),
                    outflow=_parse_optional_float(raw.get("outflow")),
                )
            )
        except ValueError as exc:
            warnings.append(f"line {line_number}: {exc}")

    return rows, warnings


def compute_step_hours(rows: list[EventRow]) -> float | None:
    if len(rows) < 2:
        return None
    diffs = [
        (current.timestamp - previous.timestamp).total_seconds() / 3600.0
        for previous, current in zip(rows, rows[1:])
        if current.timestamp > previous.timestamp
    ]
    if not diffs:
        return None
    return float(median(diffs))


def summarize_event(path: str | Path, peak_ratio: float = 0.5) -> tuple[dict[str, str | int | float], list[str]]:
    rows, warnings = load_event_rows(path)
    if not rows:
        return (
            {
                "start_time": "",
                "end_time": "",
                "record_count": 0,
                "time_step_hours_median": "0.00",
                "peak_ratio": float(peak_ratio),
            },
            warnings,
        )

    step_hours = compute_step_hours(rows) or 0.0
    inflows = [float(row.inflow) for row in rows if row.inflow is not None]
    outflows = [float(row.outflow) for row in rows if row.outflow is not None]
    levels = [float(row.level) for row in rows if row.level is not None]
    summary = {
        "start_time": rows[0].timestamp.isoformat(sep=" "),
        "end_time": rows[-1].timestamp.isoformat(sep=" "),
        "record_count": len(rows),
        "time_step_hours_median": f"{step_hours:.2f}",
        "peak_ratio": float(peak_ratio),
        "peak_inflow_m3s": round(max(inflows), 3) if inflows else 0.0,
        "peak_outflow_m3s": round(max(outflows), 3) if outflows else 0.0,
        "peak_level_m": round(max(levels), 3) if levels else 0.0,
    }
    return summary, warnings
