#!/usr/bin/env python3
"""3D isometric commit-bars GIF (like the reference recording).

Usage:
  python3 commit_gif.py                       # placeholder sample data
  python3 commit_gif.py --user jainil224      # real data (needs GITHUB_TOKEN env)
  python3 commit_gif.py --json days.json      # [{"date":"2026-03-07","count":128}, ...]
Requires: Pillow, ffmpeg (for the optimised palette GIF).
"""
import argparse, datetime as dt, json, math, os, random, subprocess, shutil, sys
from PIL import Image, ImageDraw, ImageFont

K = 1.6                           # resolution multiplier (sharper text)
W, H, SS = int(1000 * K), int(440 * K), 2           # output size, supersample
FPS = 20
BG = (250, 250, 250)
LEVELS = [(166, 239, 174), (82, 211, 110), (46, 176, 78), (28, 125, 58)]
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def fetch(user):
    import urllib.request
    q = '{user(login:"%s"){contributionsCollection{contributionCalendar{weeks{contributionDays{date contributionCount weekday}}}}}}' % user
    req = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": q}).encode(),
                                 {"Authorization": "bearer " + os.environ["GITHUB_TOKEN"]})
    d = json.load(urllib.request.urlopen(req))
    wk = d["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [{"date": x["date"], "count": x["contributionCount"]} for w in wk for x in w["contributionDays"]]


def sample():
    rnd = random.Random(7)
    start = dt.date(2025, 10, 26)
    days, base = [], 0
    for i in range(371):
        d = start + dt.timedelta(i)
        base = base * 0.9 + rnd.random() * 8 * (1.4 if 40 < i // 7 < 53 or i // 7 < 22 else 0.8)
        c = int(base * (0.35 if d.weekday() >= 5 else 1) * rnd.random() * 1.6)
        days.append({"date": d.isoformat(), "count": min(c, 70)})
    days[134]["count"] = 128
    return days


def grid(days):
    # columns = weeks (Sun-start), rows = weekday 0..6
    days = sorted(days, key=lambda x: x["date"])
    first = dt.date.fromisoformat(days[0]["date"])
    off = (first.weekday() + 1) % 7
    cells = {}
    for i, x in enumerate(days):
        k = i + off
        cells[(k // 7, k % 7)] = x
    return cells, max(c for c, _ in cells) + 1


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--best-count", type=int); ap.add_argument("--best-date", help="YYYY-MM-DD"); ap.add_argument("--dark", action="store_true"); ap.add_argument("--user"); ap.add_argument("--json"); ap.add_argument("--out", default="commits.gif")
    a = ap.parse_args()
    days = fetch(a.user) if a.user else json.load(open(a.json)) if a.json else sample()
    global BG
    FLOOR, LINE, TXT, SUB = (236,236,236), (90,90,90), (25,25,25), (140,140,140)
    if a.dark:
        BG, FLOOR, LINE, TXT, SUB = (13,17,23), (33,38,45), (139,148,158), (240,246,252), (139,148,158)
    cells, ncols = grid(days)
    mx = max(x["count"] for x in cells.values()) or 1
    best = max(cells.items(), key=lambda kv: kv[1]["count"])
    (bc, br), bd = best
    bd = dict(bd)
    if a.best_count: bd['count'] = a.best_count
    if a.best_date: bd['date'] = a.best_date

    COL, BW, OX, OY = 17.0 * K, 12.0 * K, 4.0 * K, 7.0 * K
    HS = 250.0 * K / mx                # auto-scale: tallest bar always fills the frame
    X0, Y0 = 40.0 * K, 385.0 * K
    f_serif = ImageFont.truetype(SERIF, int(30 * K * SS))
    f_mono = ImageFont.truetype(MONO, int(11 * K * SS))

    def pos(c, r):
        d = 6 - r  # row 0 (Sun) is back, row 6 is front
        return (X0 + c * COL + d * OX) * SS, (Y0 - d * OY) * SS

    # --- label placement: find clear space above every bar under the text ---
    _tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    d0 = dt.date.fromisoformat(bd["date"])
    lab0 = f'{d0.day} {d0.strftime("%b").upper()} {d0.year}, BEST DAY'
    tw = max(_tmp.textlength(f'{bd["count"]} commits', font=f_serif), _tmp.textlength(lab0, font=f_mono)) / SS + 14 * K
    bpx, bpy = pos(bc, br)
    LX = bpx / SS + BW / 2 + OX / 2
    best_top = bpy / SS - (max(best[1]["count"], 1) * HS + 3 * K) - OY * 0.8
    span_top = best_top
    for (c_, r_), x_ in cells.items():
        px_, py_ = pos(c_, r_); px_ /= SS; py_ /= SS
        if px_ + BW + OX >= LX - 4 * K and px_ <= LX + tw:
            span_top = min(span_top, py_ - (max(x_["count"], 1) * HS + 3 * K) - OY * 0.8)
    YTOP = max(span_top - 44 * K - 12 * K, 12 * K)

    T_RISE, T_LINE, T_TEXT, T_HOLD = 4.0, 1.4, 1.0, 4.0
    total = T_RISE + T_LINE + T_TEXT + T_HOLD
    n = int(total * FPS)
    tmp = "_frames"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)

    for fi in range(n):
        t = fi / FPS
        im = Image.new("RGB", (W * SS, H * SS), BG)
        dr = ImageDraw.Draw(im)
        # floor slab
        fx0, fy0 = pos(0, 6); fx1, _ = pos(ncols, 6); bx, by = pos(ncols, 0)
        dr.polygon([(fx0, fy0), (fx1, fy0), (bx, by), (pos(0, 0)[0], by)], fill=FLOOR)
        for r in range(7):                       # back -> front
            for c in range(ncols):
                x = cells.get((c, r))
                if not x:
                    continue
                n_ = x["count"]
                lvl = 0 if n_ == 0 else min(3, int(math.ceil(n_ / mx * 4)) - 1)
                col = LEVELS[lvl]
                grow = ease((t - (c / ncols) * 2.4) / 1.6)
                h = (max(n_, 1) * HS + 3 * K) * SS * grow
                if h < 1: continue
                px, py = pos(c, r); w = BW * SS; ox, oy = OX * SS, OY * SS * 0.8
                dr.polygon([(px + w, py - h), (px + w + ox, py - h - oy), (px + w + ox, py - oy), (px + w, py)], fill=shade(col, 0.78))
                dr.rectangle([px, py - h, px + w, py], fill=col)
                dr.polygon([(px, py - h), (px + w, py - h), (px + w + ox, py - h - oy), (px + ox, py - h - oy)], fill=shade(col, 1.12))
        # callout
        tl = (t - T_RISE) / T_LINE
        if tl > 0:
            px, py = pos(bc, br)
            top = py - (max(best[1]["count"], 1) * HS + 3 * K) * SS - OY * SS * 0.8
            lx = px + BW * SS / 2 + OX * SS / 2
            ytop = top - (top - YTOP * SS) * ease(tl)
            dr.line([(lx, top), (lx, ytop)], fill=LINE, width=int(1.5 * K * SS))
            ta = ease((t - T_RISE - T_LINE) / T_TEXT)
            if ta > 0:
                mix = lambda c: tuple(int(BG[i] + (c[i] - BG[i]) * ta) for i in range(3))
                d = dt.date.fromisoformat(bd["date"])
                lab = f'{d.day} {d.strftime("%b").upper()} {d.year}, BEST DAY'
                dr.text((lx + 6 * K * SS, ytop - 8 * K * SS), f'{bd["count"]} commits', font=f_serif, fill=mix(TXT))
                dr.text((lx + 6 * K * SS, ytop + 30 * K * SS), lab, font=f_mono, fill=mix(SUB))
        im.resize((W, H), Image.LANCZOS).save(f"{tmp}/{fi:03d}.png")

    # optimised GIF; last-frame hold + loop
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{tmp}/%03d.png",
                    "-vf", "split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];[b][p]paletteuse=dither=none",
                    "-loop", "0", a.out], check=True)
    shutil.rmtree(tmp)
    print(a.out, os.path.getsize(a.out) // 1024, "KB", n, "frames")


main()
