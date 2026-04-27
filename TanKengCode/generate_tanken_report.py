from __future__ import annotations

from project.scenario_executor import generate_execution_report


def main() -> int:
    report_path = generate_execution_report()
    print(str(report_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
