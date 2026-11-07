import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import plot_diagnosis


class PlotDiagnosisTests(unittest.TestCase):
    def test_load_samples_skips_missing_or_truncated_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "samples.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=("timestamp_utc", "raw_wash_level", "progress"),
                )
                writer.writeheader()
                writer.writerow({
                    "timestamp_utc": "2026-11-08T00:00:00+00:00",
                    "raw_wash_level": "7",
                    "progress": "wash",
                })
                writer.writerow({
                    "timestamp_utc": "2026-11-08T00:00:01+00:00",
                    "raw_wash_level": "",
                    "progress": "wash",
                })
                stream.write("truncated-row\n")

            with patch.object(plot_diagnosis, "CSV_PATHS", (csv_path,)):
                samples = plot_diagnosis.load_samples()

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0][1], 7)
        self.assertEqual(samples[0][2]["progress"], "wash")

    def test_render_uses_recorded_progress_without_idle_claim(self) -> None:
        rows = [
            ("wash", ""),
            ("rinse", "cover_reinstalled_user_report"),
        ]
        samples = [
            (
                datetime(2026, 11, 8, 0, index, tzinfo=timezone.utc),
                level,
                {"progress": progress, "operator_note": note},
            )
            for index, (progress, note), level in ((0, rows[0], 7), (1, rows[1], 8))
        ]

        svg = plot_diagnosis.render(samples)

        self.assertIn("reported progress: rinse, wash", svg)
        self.assertIn("2 valid samples", svg)
        self.assertIn("operator note present", svg)
        self.assertNotIn("every recorded sample reported progress=idle", svg)
        self.assertNotIn("TB80-6288WCLS", svg)


if __name__ == "__main__":
    unittest.main()
