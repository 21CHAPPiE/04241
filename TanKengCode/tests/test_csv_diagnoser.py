from __future__ import annotations

from pathlib import Path

from project.plugins.csv_diagnoser import EXPECTED_HEADER, inspect_csv_file


def test_inspect_csv_file_removes_blank_lines_and_allows_missing_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "\n".join(
            [
                ",".join(EXPECTED_HEADER),
                "",
                ",,,,",
                "2019/4/29 20:00,\u3000,152,\u3000,\u3000",
                "2019/4/29 23:00,0.26,151.99,126.5,183.7",
                "",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )

    report = inspect_csv_file(csv_path)

    assert report.blank_lines_removed == 3
    assert not report.has_errors
    assert csv_path.read_text(encoding="utf-8-sig").splitlines() == [
        ",".join(EXPECTED_HEADER),
        "2019/4/29 20:00,\u3000,152,\u3000,\u3000",
        "2019/4/29 23:00,0.26,151.99,126.5,183.7",
    ]


def test_inspect_csv_file_reports_invalid_numeric_value(tmp_path: Path) -> None:
    csv_path = tmp_path / "broken.csv"
    csv_path.write_text(
        "\n".join(
            [
                ",".join(EXPECTED_HEADER),
                "2019/7/7 23:00,not-a-number,154.82,355.1,533.8",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )

    report = inspect_csv_file(csv_path, clean_blank_lines=False)

    assert report.has_errors
    assert any("invalid numeric value in column 'prcp'" in msg.message for msg in report.messages)


def test_inspect_csv_file_uses_fallback_encoding_and_preserves_it_on_rewrite(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "legacy.csv"
    csv_path.write_bytes(
        (
            ",".join(EXPECTED_HEADER)
            + "\r\n"
            + "\r\n"
            + "2019/4/29 20:00,\u3000,152,\u3000,\u3000\r\n"
        ).encode("gb18030")
    )

    report = inspect_csv_file(csv_path)

    assert report.blank_lines_removed == 1
    assert report.encoding == "gb18030"
    assert report.has_warnings
    assert not report.has_errors
    assert csv_path.read_bytes().startswith(",".join(EXPECTED_HEADER).encode("gb18030"))
