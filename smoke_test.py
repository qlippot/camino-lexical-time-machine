"""Headless smoke tests for the Camino Real Lexical Time Machine.

Runs the Streamlit app in-process with Streamlit's AppTest harness, so every
widget, chart and dataframe is exercised without a browser.

    python smoke_test.py

Exit code 0 means the app renders and the headline numbers agree with the
deposited dataset.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"

EXPECTED_RECORDS = 138
EXPECTED_WORKS = 17
EXPECTED_TERMS = 117
EXPECTED_TRANSITO = 81
EXPECTED_HIGH = 50
EXPECTED_PIANO_HITS = 4


def metric_value(at: AppTest, label: str) -> str:
    for metric in at.metric:
        if metric.label == label:
            return str(metric.value)
    raise AssertionError(f"Metric {label!r} not found; got {[m.label for m in at.metric]}")


def fresh() -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    return at


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_dataset_counts() -> None:
    with (ROOT / "03_evidencia_material.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    check(len(rows) == EXPECTED_RECORDS, f"expected {EXPECTED_RECORDS} evidence rows, got {len(rows)}")
    check(
        len({row["termino_normalizado_glosario"] for row in rows}) == EXPECTED_TERMS,
        "unexpected number of unique glossary terms",
    )


def test_default_render() -> None:
    at = fresh()
    check(not at.exception, f"app raised: {at.exception}")
    check(at.title[0].value == "Camino Real Lexical Time Machine", "title mismatch")
    check(metric_value(at, "Material records") == f"{EXPECTED_RECORDS}", "record metric")
    check(metric_value(at, "Travelogues represented") == "17 of 17", "travelogue metric")
    check(metric_value(at, "Unique glossary terms") == f"{EXPECTED_TERMS}", "term metric")
    check(len(at.dataframe) == 1, "evidence table missing")
    check(len(at.dataframe[0].value) == EXPECTED_RECORDS, "evidence table row count")


def test_publication_axis() -> None:
    at = fresh()
    at.sidebar.radio[0].set_value("Publication year").run()
    check(not at.exception, f"publication axis raised: {at.exception}")
    check(metric_value(at, "Material records") == f"{EXPECTED_RECORDS}", "axis switch changed record count")
    check(len(at.sidebar.slider) == 1, "year slider missing after axis switch")
    check(at.sidebar.slider[0].label == "Publication year range", "slider label")


def test_category_and_preservation_filters() -> None:
    at = fresh()
    at.sidebar.multiselect[0].set_value(["Tránsito"]).run()
    check(not at.exception, f"category filter raised: {at.exception}")
    check(metric_value(at, "Material records") == f"{EXPECTED_TRANSITO}", "transit filter count")

    at = fresh()
    # Sidebar multiselect order: 0 analytical, 1 preservation, 2 descriptive,
    # 3 material family, 4 language, 5 corpus role.
    at.sidebar.multiselect[1].set_value(["High"]).run()
    check(not at.exception, f"preservation filter raised: {at.exception}")
    check(metric_value(at, "Material records") == f"{EXPECTED_HIGH}", "high-preservation count")


def test_year_slider() -> None:
    at = fresh()
    at.sidebar.slider[0].set_value((1830, 1860)).run()
    check(not at.exception, f"year slider raised: {at.exception}")
    check(len(at.dataframe[0].value) < EXPECTED_RECORDS, "year filter did not reduce rows")


def test_timeline_resolution() -> None:
    at = fresh()
    resolution = [radio for radio in at.radio if radio.label == "Resolution"]
    check(len(resolution) == 1, "resolution radio missing")
    resolution[0].set_value("Decade").run()
    check(not at.exception, f"decade resolution raised: {at.exception}")
    check(metric_value(at, "Material records") == f"{EXPECTED_RECORDS}", "decade view changed counts")


def test_evidence_search() -> None:
    at = fresh()
    at.text_input[0].set_value("piano").run()
    check(not at.exception, f"search raised: {at.exception}")
    shown = len(at.dataframe[0].value)
    check(shown == EXPECTED_PIANO_HITS, f"piano search returned {shown} rows")
    check(len(at.download_button) >= 1, "download button missing")


def test_empty_state() -> None:
    at = fresh()
    at.sidebar.multiselect[0].set_value([]).run()
    check(not at.exception, f"empty state raised: {at.exception}")
    check(any("No records match" in str(info.value) for info in at.info), "empty-state message missing")


def test_reset_filters() -> None:
    at = fresh()
    at.sidebar.multiselect[0].set_value(["Maneras de habitar"]).run()
    reset = [button for button in at.sidebar.button if button.label == "Reset filters"]
    check(len(reset) == 1, "reset button missing")
    reset[0].click().run()
    check(not at.exception, f"reset raised: {at.exception}")
    check(metric_value(at, "Material records") == f"{EXPECTED_RECORDS}", "reset did not restore records")


def main() -> int:
    tests = [
        test_dataset_counts,
        test_default_render,
        test_publication_axis,
        test_category_and_preservation_filters,
        test_year_slider,
        test_timeline_resolution,
        test_evidence_search,
        test_empty_state,
        test_reset_filters,
    ]
    failures = 0
    for test in tests:
        name = test.__name__
        try:
            test()
        except AssertionError as error:
            failures += 1
            print(f"FAIL  {name}: {error}")
        except Exception as error:  # noqa: BLE001 - report, do not abort the suite
            failures += 1
            print(f"ERROR {name}: {type(error).__name__}: {error}")
        else:
            print(f"ok    {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
