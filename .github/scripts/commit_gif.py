    best_date_obj = dt.date.fromisoformat(best_item["date"])
    callout_label = f'{best_date_obj.day} {best_date_obj.strftime("%b").upper()} {best_date_obj.year}, BEST DAY'
    text_width = max(
        temp_draw.textlength(f'{best_item["count"]} activities', font=font_serif),
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
        draw.text((stat_x, stat_y), f"{int(year_total * count_up):,} activities in {today.year}", font=font_big, fill=TXT)
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
                draw.text((line_x + 6 * K * SS, label_y - 8 * K * SS), f'{best_item["count"]} activities', font=font_serif, fill=mixed_color(TXT))
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
