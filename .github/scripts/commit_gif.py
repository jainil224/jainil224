#!/usr/bin/env python3
"""3D isometric GitHub commit-bars GIF (matches your GitHub contribution calendar).

Usage:
  python3 commit_gif.py                         # placeholder sample data
  python3 commit_gif.py --user jainil224         # real data; needs GITHUB_TOKEN
  python3 commit_gif.py --json days.json         # [{"date":"2026-03-07","count":128}, ...]

Requires: Pillow, ffmpeg. GitHub API access requires GITHUB_TOKEN.
"""

import argparse
import datetime as dt
import json
import math
import os
import random
import shutil
import subprocess
import urllib.request

from PIL import Image, ImageDraw, ImageFont

K = 1.6
W, H, SS = int(1000 * K), int(480 * K), 2
FPS = 20
BG = (250, 250, 250)
LEVELS = [(166, 239, 174), (82, 211, 110), (46, 176, 78), (28, 125, 58)]
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def graphql(query, variables, token):
    """Send one authenticated GitHub GraphQL request."""
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "github-activity-chart",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if payload.get("errors"):
        messages = "; ".join(error.get("message", "Unknown GraphQL error") for error in payload["errors"])
        raise RuntimeError("GitHub GraphQL API error: " + messages)

    return payload["data"]


def fetch(user):
    """Get the contribution calendar and add authored issue/PR conversation comments."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is missing. Add a token to your environment or GitHub Actions secrets.")

    calendar_query = """
    query ($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    calendar_data = graphql(calendar_query, {"login": user}, token)
    user_data = calendar_data.get("user")
    if not user_data:
        raise RuntimeError(f"GitHub user '{user}' was not found or is not accessible.")

    calendar_weeks = user_data["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [
        {"date": day["date"], "count": int(day["contributionCount"])}
        for week in calendar_weeks
        for day in week["contributionDays"]
    ]
    if not days:
        raise RuntimeError("GitHub returned an empty contribution calendar.")

    # Contribution calendar only, so the numbers match your GitHub profile.
    return sorted(days, key=lambda day: day["date"])


def sample():
    rnd = random.Random(7)
    start = dt.date.today() - dt.timedelta(days=370)
    days, base = [], 0
    for i in range(371):
        date = start + dt.timedelta(days=i)
        base = base * 0.9 + rnd.random() * 8 * (1.4 if 40 < i // 7 < 53 or i // 7 < 22 else 0.8)
        count = int(base * (0.35 if date.weekday() >= 5 else 1) * rnd.random() * 1.6)
        days.append({"date": date.isoformat(), "count": min(count, 70)})
    days[134]["count"] = 128
    return days


def grid(days):
    # Columns = weeks (Sunday-start), rows = weekday 0..6.
    days = sorted(days, key=lambda item: item["date"])
    first = dt.date.fromisoformat(days[0]["date"])
    offset = (first.weekday() + 1) % 7
    cells = {}
    for index, item in enumerate(days):
        key = (index + offset) // 7, (index + offset) % 7
        cells[key] = item
    return cells, max(column for column, _ in cells) + 1


def write_stats(days, path):
    today = dt.date.today()
    data = sorted((dt.date.fromisoformat(item["date"]), item["count"]) for item in days)
    year_total = sum(count for date, count in data if date.year == today.year)
    last12 = sum(count for _, count in data)
    best_date, best_count = max(data, key=lambda value: value[1])
    active_days = sum(1 for date, count in data if date.year == today.year and count > 0)

    by_date = dict(data)
    streak = 0
    date = today if by_date.get(today, 0) > 0 else today - dt.timedelta(days=1)
    while by_date.get(date, 0) > 0:
        streak += 1
        date -= dt.timedelta(days=1)

    rows = [
        (f"Commits in {today.year}", f"{year_total:,}"),
        ("Last 12 months", f"{last12:,}"),
        (f"Active days ({today.year})", str(active_days)),
        ("Best day", f"{best_count} on {best_date.day} {best_date.strftime('%b %Y')}"),
        ("Current streak", f"{streak} day{'s' if streak != 1 else ''}"),
    ]
    width = max(len(label) for label, _ in rows)
    body = "\n".join(f"{label.ljust(width)} : {value}" for label, value in rows)
    with open(path, "w", encoding="utf-8") as file:
        file.write(f"<!--STATS_START-->\n```text\n{body}\n```\n<!--STATS_END-->\n")


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def shade(color, factor):
    return tuple(max(0, min(255, int(value * factor))) for value in color)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--best-count", type=int)
    parser.add_argument("--best-date", help="YYYY-MM-DD")
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--stats-md")
    parser.add_argument("--user")
    parser.add_argument("--json")
    parser.add_argument("--out", default="commits.gif")
    args = parser.parse_args()

    if args.user:
        days = fetch(args.user)
    elif args.json:
        with open(args.json, encoding="utf-8") as file:
            days = json.load(file)
    else:
        days = sample()

    if args.stats_md:
        write_stats(days, args.stats_md)

    global BG
    FLOOR, LINE, TXT, SUB = (236, 236, 236), (90, 90, 90), (25, 25, 25), (140, 140, 140)
    if args.dark:
        BG, FLOOR, LINE, TXT, SUB = (13, 17, 23), (33, 38, 45), (139, 148, 158), (240, 246, 252), (139, 148, 158)

    cells, ncols = grid(days)
    today = dt.date.today()
    date_counts = [(dt.date.fromisoformat(item["date"]), item["count"]) for item in days]
    year_total = sum(count for date, count in date_counts if date.year == today.year)
    last12 = sum(count for _, count in date_counts)
    active_days = sum(1 for date, count in date_counts if date.year == today.year and count > 0)

    by_date = dict(date_counts)
    current_streak = 0
    date = today if by_date.get(today, 0) > 0 else today - dt.timedelta(days=1)
    while by_date.get(date, 0) > 0:
        current_streak += 1
        date -= dt.timedelta(days=1)

    longest_streak = run = 0
    for date, count in sorted(date_counts):
        run = run + 1 if count > 0 else 0
        longest_streak = max(longest_streak, run)

    max_count = max((item["count"] for item in cells.values()), default=1) or 1
    best = max(cells.items(), key=lambda pair: pair[1]["count"])
    (best_col, best_row), best_item = best
    best_item = dict(best_item)
    if args.best_count is not None:
        best_item["count"] = args.best_count
    if args.best_date:
        best_item["date"] = args.best_date

    COL, BW, OX, OY = 17.0 * K, 12.0 * K, 4.0 * K, 7.0 * K
    height_scale = 250.0 * K / max_count
    X0, Y0 = 40.0 * K, 385.0 * K
    font_serif = ImageFont.truetype(SERIF, int(30 * K * SS))
    font_mono = ImageFont.truetype(MONO, int(11 * K * SS))
    font_big = ImageFont.truetype(SERIF, int(26 * K * SS))
    font_mid = ImageFont.truetype(MONO, int(12 * K * SS))

    def pos(column, row):
        depth = 6 - row  # row 0 is back; row 6 is front.
        return (X0 + column * COL + depth * OX) * SS, (Y0 - depth * OY) * SS

    temp_draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    best_date_obj = dt.date.fromisoformat(best_item["date"])
    callout_label = f'{best_date_obj.day} {best_date_obj.strftime("%b").upper()} {best_date_obj.year}, BEST DAY'
    text_width = max(
        temp_draw.textlength(f'{best_item["count"]} commits', font=font_serif),
        temp_draw.textlength(callout_label, font=font_mono),
    ) / SS + 14 * K
    best_x, best_y = pos(best_col, best_row)
    label_x = best_x / SS + BW / 2 + OX / 2
    best_top = best_y / SS - (max(best[1]["count"], 1) * height_scale + 3 * K) - OY * 0.8
    span_top = best_top
    for (column, row), item in cells.items():
        px, py = pos(column, row)
        px, py = px / SS, py / SS
        if px + BW + OX >= label_x - 4 * K and px <= label_x + text_width:
            span_top = min(span_top, py - (max(item["count"], 1) * height_scale + 3 * K) - OY * 0.8)
    label_top = max(span_top - 44 * K - 12 * K, 12 * K)

    T_RISE, T_LINE, T_TEXT, T_HOLD = 4.0, 1.4, 1.0, 4.0
    total_time = T_RISE + T_LINE + T_TEXT + T_HOLD
    frame_count = int(total_time * FPS)
    temp_dir = "_frames"
    shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(temp_dir, exist_ok=True)

    for frame_index in range(frame_count):
        time = frame_index / FPS
        image = Image.new("RGB", (W * SS, H * SS), BG)
        draw = ImageDraw.Draw(image)

        # Floor slab.
        floor_x0, floor_y0 = pos(0, 6)
        floor_x1, _ = pos(ncols, 6)
        back_x, back_y = pos(ncols, 0)
        draw.polygon(
            [(floor_x0, floor_y0), (floor_x1, floor_y0), (back_x, back_y), (pos(0, 0)[0], back_y)],
            fill=FLOOR,
        )

        for row in range(7):
            for column in range(ncols):
                item = cells.get((column, row))
                if not item:
                    continue
                count = item["count"]
                level = 0 if count == 0 else min(3, int(math.ceil(count / max_count * 4)) - 1)
                color = LEVELS[level]
                growth = ease((time - (column / ncols) * 2.4) / 1.6)
                bar_height = (max(count, 1) * height_scale + 3 * K) * SS * growth
                if bar_height < 1:
                    continue

                px, py = pos(column, row)
                width = BW * SS
                offset_x, offset_y = OX * SS, OY * SS * 0.8
                draw.polygon(
                    [(px + width, py - bar_height), (px + width + offset_x, py - bar_height - offset_y),
                     (px + width + offset_x, py - offset_y), (px + width, py)],
                    fill=shade(color, 0.78),
                )
                draw.rectangle([px, py - bar_height, px + width, py], fill=color)
                draw.polygon(
                    [(px, py - bar_height), (px + width, py - bar_height),
                     (px + width + offset_x, py - bar_height - offset_y), (px + offset_x, py - bar_height - offset_y)],
                    fill=shade(color, 1.12),
                )

        # Activity count animates while the bars rise.
        count_up = ease(time / T_RISE)
        stat_x, stat_y = X0 * SS, (Y0 + 22 * K) * SS
        draw.text((stat_x, stat_y), f"{int(year_total * count_up):,} commits in {today.year}", font=font_big, fill=TXT)
        draw.text(
            (stat_x, stat_y + 38 * K * SS),
            f"LAST 12 MONTHS: {last12:,}   ACTIVE DAYS: {active_days}   CURRENT STREAK: {current_streak} DAY{'S' if current_streak != 1 else ''}   LONGEST STREAK: {longest_streak} DAYS",
            font=font_mid,
            fill=SUB,
        )

        # Best-day callout.
        line_progress = (time - T_RISE) / T_LINE
        if line_progress > 0:
            px, py = pos(best_col, best_row)
            top = py - (max(best[1]["count"], 1) * height_scale + 3 * K) * SS - OY * SS * 0.8
            line_x = px + BW * SS / 2 + OX * SS / 2
            label_y = top - (top - label_top * SS) * ease(line_progress)
            draw.line([(line_x, top), (line_x, label_y)], fill=LINE, width=int(1.5 * K * SS))
            text_alpha = ease((time - T_RISE - T_LINE) / T_TEXT)
            if text_alpha > 0:
                mixed_color = lambda color: tuple(int(BG[i] + (color[i] - BG[i]) * text_alpha) for i in range(3))
                label_date = dt.date.fromisoformat(best_item["date"])
                label = f'{label_date.day} {label_date.strftime("%b").upper()} {label_date.year}, BEST DAY'
                draw.text((line_x + 6 * K * SS, label_y - 8 * K * SS), f'{best_item["count"]} commits', font=font_serif, fill=mixed_color(TXT))
                draw.text((line_x + 6 * K * SS, label_y + 30 * K * SS), label, font=font_mono, fill=mixed_color(SUB))

        image.resize((W, H), Image.Resampling.LANCZOS).save(f"{temp_dir}/{frame_index:03d}.png")

    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{temp_dir}/%03d.png",
            "-vf", "split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];[b][p]paletteuse=dither=none",
            "-loop", "0", args.out,
        ],
        check=True,
    )
    shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"{args.out} {os.path.getsize(args.out) // 1024} KB {frame_count} frames")


if __name__ == "__main__":
    main()
