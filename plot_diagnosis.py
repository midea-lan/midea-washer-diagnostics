"""Render valid recorded raw wash-level samples as a dependency-free SVG."""

import csv
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

BASE = Path(__file__).resolve().parent
CSV_PATHS = (BASE / "diagnosis.csv", BASE / "diagnosis_round3.csv", BASE / "live_diagnosis.csv")
SVG_PATH = BASE / "water_level_trend.svg"
WIDTH, HEIGHT = 1100, 620
LEFT, RIGHT, TOP, BOTTOM = 110, 1050, 75, 500


def load_samples() -> list[tuple[datetime, int, dict[str, str | None]]]:
    samples: list[tuple[datetime, int, dict[str, str | None]]] = []
    for csv_path in CSV_PATHS:
        if not csv_path.exists():
            continue
        with csv_path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                try:
                    raw_level = row.get("raw_wash_level")
                    timestamp = row.get("timestamp_utc")
                    if not raw_level or not timestamp:
                        continue
                    samples.append((datetime.fromisoformat(timestamp), int(raw_level), row))
                except (TypeError, ValueError):
                    continue
    return sorted(samples, key=lambda sample: sample[0])


def render(samples: list[tuple[datetime, int, dict[str, str | None]]]) -> str:
    times = [sample[0] for sample in samples]
    start, end = min(times), max(times)
    if start == end:
        end = start + timedelta(seconds=1)

    def xcoord(value: datetime) -> float:
        return LEFT + (value - start).total_seconds() / (end - start).total_seconds() * (RIGHT - LEFT)

    def ycoord(value: int) -> float:
        return BOTTOM - value / 15.5 * (BOTTOM - TOP)

    progress_values = sorted({row["progress"] for _, _, row in samples if row.get("progress")})
    progress_label = ", ".join(progress_values) if progress_values else "not recorded"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222}.grid{stroke:#d9dee5;stroke-width:1}.axis{stroke:#333;stroke-width:1.3}.small{font-size:12px}.label{font-size:14px}.title{font-size:21px;font-weight:600}</style>',
        f'<text x="110" y="35" class="title">DA washer replies — reported progress: {escape(progress_label)}</text>',
    ]

    for level in list(range(0, 9)) + [15]:
        y = ycoord(level)
        parts.append(f'<line x1="{LEFT}" y1="{y:.1f}" x2="{RIGHT}" y2="{y:.1f}" class="grid"/>')
        tick = "15 (unmapped)" if level == 15 else str(level)
        parts.append(f'<text x="{LEFT-14}" y="{y+4:.1f}" text-anchor="end" class="small">{tick}</text>')
    parts.extend([
        f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{BOTTOM}" class="axis"/>',
        f'<line x1="{LEFT}" y1="{BOTTOM}" x2="{RIGHT}" y2="{BOTTOM}" class="axis"/>',
        '<text x="28" y="290" transform="rotate(-90 28 290)" text-anchor="middle" class="label">raw wash_level nibble (not measured water volume)</text>',
    ])

    for index in range(6):
        moment = start + (end - start) * index / 5
        x = xcoord(moment)
        parts.append(f'<line x1="{x:.1f}" y1="{BOTTOM}" x2="{x:.1f}" y2="{BOTTOM+5}" class="axis"/>')
        local = moment.astimezone(timezone(timedelta(hours=8)))
        parts.append(f'<text x="{x:.1f}" y="{BOTTOM+23}" text-anchor="middle" class="small">{local:%H:%M:%S}</text>')

    groups: dict[bool, list[tuple[datetime, int, dict[str, str | None]]]] = {False: [], True: []}
    for sample in samples:
        groups[bool(sample[2].get("operator_note"))].append(sample)
    colors = {False: "#315c9b", True: "#167d5a"}
    for noted, points in groups.items():
        color = colors[noted]
        segment: list[tuple[datetime, int, dict[str, str | None]]] = []
        previous_time: datetime | None = None
        for sample in points:
            moment, level, _row = sample
            if previous_time is not None and (moment - previous_time).total_seconds() > 30:
                if len(segment) > 1:
                    coords = " ".join(f"{xcoord(t):.1f},{ycoord(value):.1f}" for t, value, _ in segment)
                    parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"/>')
                segment = []
            segment.append(sample)
            previous_time = moment
        if len(segment) > 1:
            coords = " ".join(f"{xcoord(t):.1f},{ycoord(value):.1f}" for t, value, _ in segment)
            parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"/>')

        for moment, level, row in points:
            x, y = xcoord(moment), ycoord(level)
            body_type = row.get("raw_body_type") or ((row.get("raw_body_hex") or "")[:2])
            if body_type in ("3", "03"):
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.8" fill="{color}"/>')
            else:
                parts.append(f'<path d="M{x:.1f},{y-5:.1f} l5,5 l-5,5 l-5,-5 z" fill="{color}"/>')
            if level == 15:
                parts.append(f'<text x="{x+7:.1f}" y="{y-7:.1f}" class="small">15 sentinel</text>')

    labels = {False: "no operator note", True: "operator note present"}
    for noted, color in colors.items():
        parts.append(f'<circle cx="{790 if not noted else 970}" cy="555" r="5" fill="{color}"/>')
        parts.append(f'<text x="{802 if not noted else 982}" y="559" class="small">{labels[noted]}</text>')
    parts.extend([
        f'<text x="110" y="590" class="small">{len(samples)} valid samples; progress is shown only when recorded. User notes are not independently verified.</text>',
        "</svg>",
    ])
    return "\n".join(parts)


def main() -> None:
    samples = load_samples()
    if not samples:
        raise SystemExit("No valid raw_wash_level samples found in the configured CSV files")
    SVG_PATH.write_text(render(samples), encoding="utf-8")
    print(SVG_PATH)


if __name__ == "__main__":
    main()
