from src.social_media.render_cross_country_rankings import (
    load_entries,
    render,
    render_gif,
    render_gif_fixed_slots,
    render_mp4,
    render_mp4_fixed_slots,
)


def run_cross_country_ranking_export(
    *,
    output_path: str,
    metric: str = "pp",
    theme: str = "light",
    animated: bool = False,
    animation_style: str = "standard",
) -> None:
    entries = load_entries(metric)
    if animated:
        is_mp4 = output_path.lower().endswith(".mp4")
        if animation_style == "fixed-slots":
            if is_mp4:
                render_mp4_fixed_slots(entries, output_path, metric, theme)
                return
            render_gif_fixed_slots(entries, output_path, metric, theme)
            return
        if is_mp4:
            render_mp4(entries, output_path, metric, theme)
            return
        render_gif(entries, output_path, metric, theme)
        return
    render(entries, output_path, metric, theme)
