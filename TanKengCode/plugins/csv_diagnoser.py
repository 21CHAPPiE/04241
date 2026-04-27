from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

EXPECTED_HEADER = ("time", "prcp", "level", "inflow", "outflow")
SUPPORTED_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk")
TIME_FORMAT = "%Y/%m/%d %H:%M"


@dataclass(slots=True)
class ValidationMessage:
    level: str
    message: str


@dataclass(slots=True)
class FileReport:
    path: Path
    encoding: str | None
    blank_lines_removed: int = 0
    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(message.level == "error" for message in self.messages)

    @property
    def has_warnings(self) -> bool:
        return any(message.level == "warning" for message in self.messages)

    def add_warning(self, message: str) -> None:
        self.messages.append(ValidationMessage(level="warning", message=message))

    def add_error(self, message: str) -> None:
        self.messages.append(ValidationMessage(level="error", message=message))


def _normalize_cell(value: str) -> str:
    return value.replace("\u3000", " ").strip()


def _detect_newline(raw_bytes: bytes) -> str:
    if b"\r\n" in raw_bytes:
        return "\r\n"
    if b"\r" in raw_bytes:
        return "\r"
    return "\n"


def _decode_text(raw_bytes: bytes) -> tuple[str | None, str | None]:
    for encoding in SUPPORTED_ENCODINGS:
        try:
            return encoding, raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None, None


def _collect_non_blank_lines(text: str) -> tuple[list[tuple[int, str]], int, bool]:
    entries: list[tuple[int, str]] = []
    blank_lines = 0
    lines = text.splitlines()
    had_terminal_newline = text.endswith(("\n", "\r"))

    for line_number, line in enumerate(lines, start=1):
        candidate = line.lstrip("\ufeff")
        if _normalize_cell(candidate) == "":
            blank_lines += 1
            continue
        parsed_row = next(csv.reader([candidate]))
        if parsed_row and all(_normalize_cell(cell) == "" for cell in parsed_row):
            blank_lines += 1
            continue
        entries.append((line_number, line))

    return entries, blank_lines, had_terminal_newline


def _rewrite_without_blank_lines(
    path: Path,
    entries: Iterable[tuple[int, str]],
    *,
    encoding: str,
    newline: str,
    had_terminal_newline: bool,
) -> None:
    lines = [line for _, line in entries]
    content = newline.join(lines)
    if content and had_terminal_newline:
        content = f"{content}{newline}"
    path.write_text(content, encoding=encoding, newline="")


def inspect_csv_file(path: Path, *, clean_blank_lines: bool = True) -> FileReport:
    raw_bytes = path.read_bytes()
    encoding, text = _decode_text(raw_bytes)
    report = FileReport(path=path, encoding=encoding)

    if encoding is None or text is None:
        report.add_error("file cannot be decoded with supported encodings")
        return report

    if encoding != SUPPORTED_ENCODINGS[0]:
        report.add_warning(f"decoded with fallback encoding: {encoding}")

    newline = _detect_newline(raw_bytes)
    entries, blank_lines, had_terminal_newline = _collect_non_blank_lines(text)
    report.blank_lines_removed = blank_lines

    if clean_blank_lines and blank_lines:
        _rewrite_without_blank_lines(
            path,
            entries,
            encoding=encoding,
            newline=newline,
            had_terminal_newline=had_terminal_newline,
        )

    if not entries:
        report.add_error("file is empty after removing blank lines")
        return report

    header_line_number, header_line = entries[0]
    header = next(csv.reader([header_line.lstrip("\ufeff")]))
    normalized_header = tuple(_normalize_cell(cell).lower() for cell in header)
    normalized_prefix = normalized_header[: len(EXPECTED_HEADER)]
    if normalized_prefix != EXPECTED_HEADER:
        report.add_error(
            f"line {header_line_number}: unexpected header {ascii(normalized_header)},"
            f" expected {ascii(EXPECTED_HEADER)}"
        )
        return report

    for line_number, raw_line in entries[1:]:
        row = next(csv.reader([raw_line]))
        if len(row) != len(header):
            report.add_error(
                f"line {line_number}: expected {len(header)} columns, got {len(row)}"
            )
            continue

        normalized_row = [_normalize_cell(cell) for cell in row]
        timestamp = normalized_row[0]
        try:
            datetime.strptime(timestamp, TIME_FORMAT)
        except ValueError:
            report.add_error(
                f"line {line_number}: invalid time value in column 'time': {ascii(timestamp)}"
            )

        for column_name, value in zip(EXPECTED_HEADER[1:], normalized_row[1:]):
            if value == "":
                continue
            try:
                float(value)
            except ValueError:
                report.add_error(
                    f"line {line_number}: invalid numeric value in column"
                    f" '{column_name}': {ascii(value)}"
                )

    return report


def inspect_directory(directory: Path, *, clean_blank_lines: bool = True) -> list[FileReport]:
    return [
        inspect_csv_file(path, clean_blank_lines=clean_blank_lines)
        for path in sorted(directory.glob("*.csv"))
    ]


def _print_report(directory: Path, reports: list[FileReport], *, clean_blank_lines: bool) -> None:
    total_blank_lines = sum(report.blank_lines_removed for report in reports)
    cleaned_files = [report for report in reports if report.blank_lines_removed]
    warning_files = [report for report in reports if report.has_warnings]
    error_files = [report for report in reports if report.has_errors]

    print(f"Scanned {len(reports)} CSV files under {directory}")
    if clean_blank_lines:
        print(f"Removed {total_blank_lines} blank lines from {len(cleaned_files)} files")
    else:
        print(f"Found {total_blank_lines} removable blank lines in {len(cleaned_files)} files")
    print(f"Files with warnings: {len(warning_files)}")
    print(f"Files with errors: {len(error_files)}")

    if cleaned_files:
        print("\nBlank-line cleanup:")
        for report in cleaned_files:
            print(f"- {report.path.name}: removed {report.blank_lines_removed} blank lines")

    noteworthy_reports = [report for report in reports if report.messages]
    if noteworthy_reports:
        print("\nDiagnostics:")
        for report in noteworthy_reports:
            print(f"- {report.path.name}")
            for message in report.messages:
                safe_message = message.message.encode(
                    sys.stdout.encoding or "utf-8",
                    errors="backslashreplace",
                ).decode(sys.stdout.encoding or "utf-8")
                print(f"  [{message.level}] {safe_message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose flood_event CSV files and remove fully blank lines."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default="data/flood_event",
        help="Directory containing the flood_event CSV files.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report issues without rewriting files.",
    )
    args = parser.parse_args(argv)

    directory = Path(args.directory).resolve()
    if not directory.exists():
        print(f"Directory does not exist: {directory}")
        return 2
    if not directory.is_dir():
        print(f"Path is not a directory: {directory}")
        return 2

    reports = inspect_directory(directory, clean_blank_lines=not args.check_only)
    _print_report(directory, reports, clean_blank_lines=not args.check_only)
    return 1 if any(report.has_errors for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
