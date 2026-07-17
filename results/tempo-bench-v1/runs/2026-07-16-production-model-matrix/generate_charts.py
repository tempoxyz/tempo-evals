#!/usr/bin/env python3
# ruff: noqa: E501
"""Render Tempo Bench comparison charts from an aggregate CSV export.

The input is intentionally a plain CSV so a Harbor job export can be inspected,
versioned, and re-rendered without a charting dependency.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

WIDTH = 980
HEIGHT = 700
PLOT_LEFT = 90
PLOT_RIGHT = 900
PLOT_TOP = 80
PLOT_BOTTOM = 610


@dataclass(frozen=True)
class Result:
    model: str
    family: str
    access: str
    trials: int
    correctness: float
    cost_usd: float
    total_tokens: int
    total_turns: int


@dataclass(frozen=True)
class LabelAnchor:
    results: tuple[Result, ...]
    x: float
    y: float
    label: str


def parse_results(path: Path) -> list[Result]:
    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        required = {
            "model",
            "family",
            "access",
            "trials",
            "correctness",
            "cost_usd",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "total_turns",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path} is missing one or more required columns")

        results: list[Result] = []
        seen: set[tuple[str, str]] = set()
        for row in reader:
            key = (row["model"], row["access"])
            if key in seen:
                raise ValueError(f"duplicate model/access row: {key}")
            seen.add(key)
            if row["access"] not in {"docs", "mcp"}:
                raise ValueError(f"unsupported access mode: {row['access']}")
            total_tokens = int(row["total_tokens"])
            if total_tokens != int(row["input_tokens"]) + int(row["output_tokens"]):
                raise ValueError(
                    f"token total does not match inputs and outputs for {key}"
                )
            results.append(
                Result(
                    model=row["model"],
                    family=row["family"],
                    access=row["access"],
                    trials=int(row["trials"]),
                    correctness=float(row["correctness"]),
                    cost_usd=float(row["cost_usd"]),
                    total_tokens=total_tokens,
                    total_turns=int(row["total_turns"]),
                )
            )
    if not results:
        raise ValueError(f"{path} has no data rows")
    return results


def scale(
    value: float, minimum: float, maximum: float, start: float, end: float
) -> float:
    return start + (value - minimum) / (maximum - minimum) * (end - start)


def px(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def smooth_path(points: list[tuple[float, float]]) -> str:
    """Return a smooth cubic path without overshooting the adjacent points."""
    if len(points) == 1:
        x, y = points[0]
        return f"M{px(x)} {px(y)}"
    parts = [f"M{px(points[0][0])} {px(points[0][1])}"]
    for index in range(len(points) - 1):
        current = points[index]
        following = points[index + 1]
        control_one = (
            current[0] + (following[0] - current[0]) / 3,
            current[1],
        )
        control_two = (
            following[0] - (following[0] - current[0]) / 3,
            following[1],
        )
        parts.append(
            f"C{px(control_one[0])} {px(control_one[1])} {px(control_two[0])} {px(control_two[1])} {px(following[0])} {px(following[1])}"
        )
    return " ".join(parts)


def line_groups(
    results: Iterable[Result], metric: str
) -> Iterable[tuple[str, str, list[Result]]]:
    for family in ("Claude", "GPT"):
        for access in ("docs", "mcp"):
            group = sorted(
                (
                    result
                    for result in results
                    if result.family == family and result.access == access
                ),
                key=lambda result: (metric_value(result, metric), result.model),
            )
            if group:
                yield family.lower(), access, group


def metric_value(result: Result, metric: str) -> float:
    if metric == "cost_usd":
        return result.cost_usd
    if metric == "total_tokens":
        return float(result.total_tokens)
    if metric == "total_turns":
        return float(result.total_turns)
    raise ValueError(f"unsupported x_metric: {metric}")


def label_width(label: str) -> int:
    return max(32, len(label) * 7)


def place_label_anchors(
    anchors: list[LabelAnchor],
    obstacles: list[tuple[int, int, int, int]],
) -> list[tuple[LabelAnchor, int, int, int, int]]:
    """Greedily assign clear label positions inside the plot."""
    label_gap = 5
    placed = list(obstacles)
    labels: list[tuple[LabelAnchor, int, int, int, int]] = []
    for anchor in sorted(anchors, key=lambda item: (item.x, item.y, item.label)):
        width = label_width(anchor.label)
        point_x, point_y = anchor.x, anchor.y
        right_first = point_x < PLOT_RIGHT - width - 20
        horizontal = ("right", "left") if right_first else ("left", "right")
        candidates = [
            (side, vertical, offset)
            for offset in (18, 36, 54, 72, 90, 108, 126)
            for vertical in ("top", "bottom")
            for side in horizontal
        ]
        for side, vertical, offset in candidates:
            text_x = int(point_x + 10) if side == "right" else int(point_x - width - 10)
            text_y = (
                int(point_y - offset)
                if vertical == "top"
                else int(point_y + offset + 8)
            )
            box = (text_x, text_y - 11, text_x + width, text_y + 2)
            if (
                box[0] < PLOT_LEFT
                or box[2] > PLOT_RIGHT
                or box[1] < PLOT_TOP - 10
                or box[3] > PLOT_BOTTOM - 28
            ):
                continue
            padded_box = (
                box[0] - label_gap,
                box[1] - label_gap,
                box[2] + label_gap,
                box[3] + label_gap,
            )
            if any(
                not (
                    padded_box[2] < other[0]
                    or padded_box[0] > other[2]
                    or padded_box[3] < other[1]
                    or padded_box[1] > other[3]
                )
                for other in placed
            ):
                continue
            leader_x = text_x - 4 if side == "right" else text_x + width + 4
            leader_y = text_y - 4 if vertical == "top" else text_y - 10
            placed.append(padded_box)
            labels.append((anchor, leader_x, leader_y, text_x, text_y))
            break
        else:
            raise ValueError(f"could not place label for {anchor.label}")
    return labels


def place_labels(
    results: list[Result],
    x: Any,
    y: Any,
    model_labels: dict[str, str],
    obstacles: Optional[list[tuple[int, int, int, int]]] = None,
) -> list[tuple[LabelAnchor, int, int, int, int]]:
    return place_label_anchors(
        [
            LabelAnchor(
                results=(result,),
                x=x(result),
                y=y(result),
                label=model_labels.get(result.model, result.model),
            )
            for result in results
        ],
        obstacles or point_boxes(results, x, y),
    )


def place_model_pair_labels(
    results: list[Result], x: Any, y: Any, model_labels: dict[str, str]
) -> list[tuple[LabelAnchor, int, int, int, int]]:
    grouped: dict[str, list[Result]] = {}
    for result in results:
        grouped.setdefault(result.model, []).append(result)
    anchors = []
    for model, pair in grouped.items():
        if len(pair) != 2:
            raise ValueError(f"expected Docs and MCP results for {model}")
        anchors.append(
            LabelAnchor(
                results=tuple(pair),
                x=sum(x(result) for result in pair) / len(pair),
                y=sum(y(result) for result in pair) / len(pair),
                label=model_labels.get(model, model),
            )
        )
    return place_label_anchors(anchors, point_boxes(results, x, y))


def point_boxes(
    results: list[Result], x: Any, y: Any
) -> list[tuple[int, int, int, int]]:
    """Reserve enough room that labels do not cover chart markers."""
    return [
        (int(x(result) - 9), int(y(result) - 9), int(x(result) + 9), int(y(result) + 9))
        for result in results
    ]


def chart_svg(
    results: list[Result],
    config: dict[str, Any],
    model_labels: dict[str, str],
) -> str:
    metric = config["x_metric"]
    mark = config.get("mark", "line")
    if mark not in {"line", "dot"}:
        raise ValueError(f"unsupported mark: {mark}")
    x_axis = config["x_axis"]
    y_axis = config["y_axis"]
    x_min, x_max = float(x_axis["min"]), float(x_axis["max"])
    y_min, y_max = float(y_axis["min"]), float(y_axis["max"])

    def x(result: Result) -> float:
        return scale(metric_value(result, metric), x_min, x_max, PLOT_LEFT, PLOT_RIGHT)

    def y(result: Result) -> float:
        return scale(result.correctness, y_min, y_max, PLOT_BOTTOM, PLOT_TOP)

    subtitle = config.get("subtitle")
    subtitle_svg = (
        f'\n  <text x="90" y="54" class="subtitle muted">{html.escape(subtitle)}</text>'
        if isinstance(subtitle, str) and subtitle
        else ""
    )

    groups = []
    if mark == "line":
        for family, access, group in line_groups(results, metric):
            points = [(x(result), y(result)) for result in group]
            groups.append(
                f'<path d="{smooth_path(points)}" class="{family} {access}"/>'
            )

    points = []
    if mark == "dot":
        for result in results:
            color = "#000" if result.family == "Claude" else "#4d4d4d"
            fill = color if result.access == "docs" else "#f3f3f3"
            stroke = "#f3f3f3" if result.access == "docs" else color
            points.append(
                f'<circle class="point dot dot-access-{result.access}" cx="{px(x(result))}" cy="{px(y(result))}" r="5.5" fill="{fill}" stroke="{stroke}"/>'
            )
    else:
        for family in ("Claude", "GPT"):
            family_results = [result for result in results if result.family == family]
            circles = "".join(
                f'<circle cx="{px(x(result))}" cy="{px(y(result))}" r="5.5"/>'
                for result in family_results
            )
            points.append(f'<g class="{family.lower()} line-point">{circles}</g>')

    annotations = ""
    label_access = config.get("label_access")
    label_mode = config.get("label_mode")
    if label_mode == "model-pairs":
        label_placements = place_model_pair_labels(results, x, y, model_labels)
    elif label_access:
        label_results = (
            results
            if label_access == "all"
            else [result for result in results if result.access == label_access]
        )
        label_placements = place_labels(
            label_results,
            x,
            y,
            model_labels,
            point_boxes(results, x, y),
        )
    else:
        label_placements = []
    if label_placements:
        leaders: list[str] = []
        backgrounds: list[str] = []
        text: list[str] = []
        for anchor, leader_x, leader_y, label_x, label_y in label_placements:
            if label_mode != "model-pairs":
                leaders.extend(
                    f'<line x1="{px(x(result))}" y1="{px(y(result))}" x2="{leader_x}" y2="{leader_y}"/>'
                    for result in anchor.results
                )
            backgrounds.append(
                f'<rect x="{label_x - 3}" y="{label_y - 13}" width="{label_width(anchor.label) + 6}" height="17" rx="2"/>'
            )
            text.append(
                f'<text x="{label_x}" y="{label_y}">{html.escape(anchor.label)}</text>'
            )
        annotations = (
            f'<g class="leader">{"".join(leaders)}</g>'
            f'<g class="label-background">{"".join(backgrounds)}</g>'
            f'<g class="point-label ink">{"".join(text)}</g>'
        )

    grid = "".join(
        f'<line x1="{PLOT_LEFT}" y1="{px(scale(float(tick["value"]), y_min, y_max, PLOT_BOTTOM, PLOT_TOP))}" '
        f'x2="{PLOT_RIGHT}" y2="{px(scale(float(tick["value"]), y_min, y_max, PLOT_BOTTOM, PLOT_TOP))}"/>'
        for tick in y_axis["ticks"]
    )
    y_tick_text = "".join(
        f'<text x="55" y="{px(scale(float(tick["value"]), y_min, y_max, PLOT_BOTTOM, PLOT_TOP) + 4)}">{html.escape(tick["label"])}</text>'
        for tick in y_axis["ticks"]
    )
    x_tick_text = "".join(
        f'<text x="{px(scale(float(tick["value"]), x_min, x_max, PLOT_LEFT, PLOT_RIGHT) - 4)}" y="632">{html.escape(tick["label"])}</text>'
        for tick in x_axis["ticks"]
    )
    mark_description = (
        "Solid lines are Docs; dotted lines are MCP."
        if mark == "line"
        else "Filled dots are Docs; hollow dots are MCP."
    )
    legend = (
        '<line x1="650" y1="578" x2="680" y2="578" class="axis docs"/><text x="688" y="582" class="ink">Docs</text><line x1="762" y1="578" x2="792" y2="578" class="axis mcp"/><text x="800" y="582" class="ink">MCP</text>'
        if mark == "line"
        else '<circle cx="665" cy="578" r="5" fill="#000" stroke="#000"/><text x="676" y="582" class="ink">Docs</text><circle cx="777" cy="578" r="5" fill="#f3f3f3" stroke="#000" stroke-width="2"/><text x="788" y="582" class="ink">MCP</text>'
    )
    marks = "\n".join((*groups, *points))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">{html.escape(config["title"])}</title>
  <desc id="desc">{html.escape(config["description"])} {mark_description} Claude points are black and GPT points are warm gray.</desc>
  <style>
    .page {{ fill: #f3f3f3; }} .ink {{ fill: #000; }} .muted {{ fill: #808080; }}
    .subtitle, .axis-label, .tick, .key {{ font: 400 12px 'Pilat', Arial, Helvetica, sans-serif; }}
    .point-label {{ font: 400 12px 'Pilat', Arial, Helvetica, sans-serif; }}
    .axis {{ stroke: #000; stroke-width: 1; }} .grid {{ stroke: #d9d9d9; stroke-width: 1; }}
    .leader {{ stroke: #b2b2b2; stroke-width: 1; }} .claude {{ stroke: #000; fill: #000; }}
    .label-background {{ fill: #f3f3f3; }}
    .gpt {{ stroke: #4d4d4d; fill: #4d4d4d; }} .docs {{ fill: none; stroke-width: 2.25; }}
    .mcp {{ fill: none; stroke-width: 2.25; stroke-dasharray: 1 6; stroke-linecap: round; }}
    .line-point {{ stroke: #f3f3f3; stroke-width: 2; }} .dot {{ stroke-width: 2; }}
  </style>
  <rect class="page" width="{WIDTH}" height="{HEIGHT}"/>
{subtitle_svg}
  <line x1="{PLOT_LEFT}" y1="{PLOT_BOTTOM}" x2="{PLOT_RIGHT}" y2="{PLOT_BOTTOM}" class="axis"/>
  <line x1="{PLOT_LEFT}" y1="{PLOT_TOP}" x2="{PLOT_LEFT}" y2="{PLOT_BOTTOM}" class="axis"/>
  <g class="grid">{grid}</g>
  <g class="tick muted">{y_tick_text}{x_tick_text}</g>
  <text x="495" y="670" text-anchor="middle" class="axis-label ink">{html.escape(x_axis["label"])}</text>
  <text transform="translate(23 385) rotate(-90)" text-anchor="middle" class="axis-label ink">{html.escape(y_axis["label"])}</text>
{marks}
{annotations}
  <g class="key">{legend}</g>
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path("summary.csv"), help="aggregate CSV input"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("chart_config.json"),
        help="chart configuration JSON",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("."), help="directory for SVG outputs"
    )
    args = parser.parse_args()

    results = parse_results(args.input)
    config = json.loads(args.config.read_text())
    if not isinstance(config.get("model_labels"), dict) or not config.get("charts"):
        raise ValueError("chart config requires model_labels and at least one chart")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for chart in config["charts"]:
        required = {"output", "title", "description", "x_metric", "x_axis", "y_axis"}
        if not required.issubset(chart):
            raise ValueError(
                f"chart config is missing fields: {required - chart.keys()}"
            )
        output = args.out_dir / chart["output"]
        output.write_text(chart_svg(results, chart, config["model_labels"]))
        print(output)


if __name__ == "__main__":
    main()
