# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "marimo",
#   "polars",
#   "pyarrow",
#   "plotly",
#    "nflreadpy",
# ]
# ///

# ─────────────────────────────────────────────────────────────────────────────
# HOW MARIMO WORKS — read this before looking at the code
#
# Marimo is a "reactive" notebook. Instead of running cells top-to-bottom
# like Jupyter, marimo watches which variables each cell uses and defines.
# When a variable changes, every cell that depends on it re-runs automatically.
#
# Think of it like a spreadsheet: change one cell, and everything that
# references it updates instantly.
#
# Each cell in this file is separated by the `@app.cell` decorator.
# The function name inside doesn't matter — marimo uses the return value
# and the function's arguments to figure out the dependency graph.
#
# Example:
#   @app.cell
#   def __(mo):           ← this cell USES `mo` (declared in another cell)
#       x = mo.md("hi")  ← defines `x`
#       return (x,)       ← makes `x` available to other cells
# ─────────────────────────────────────────────────────────────────────────────

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="NFL Reporter")

with app.setup:
    # Initialization code that runs before all other cells

    import marimo as mo
    import nflreadpy as nfl
    import polars as pl
    from polars import col as c
    import nflr_my_team
    import nflr_schedule
    import rank_functions as rk_fn
    import nflr_matchups
    import nflr_power_rankings

    max_season = nfl.load_schedules().select(pl.col("season").max()).item()
    stats_max_season = (
        nfl.load_team_stats(summary_level="reg").select(pl.col("season").max()).item()
    )

    # Fetch last 4 seasons of stats
    stats_seasons = list(range(stats_max_season - 3, stats_max_season + 1))

    # LazyFrames
    rosters_lf = nfl.load_rosters().lazy()
    injuries_lf = nfl.load_injuries().lazy()
    teams_lf = nfl.load_teams().lazy()
    schedules_lf = nfl.load_schedules(seasons=stats_seasons).lazy()
    team_stats_lf = nfl.load_team_stats(seasons=stats_seasons).lazy()
    player_stats_lf = nfl.load_player_stats(seasons=stats_seasons).lazy()

    # Old abbreviation -> current abbreviation (relocated franchises)
    ABBR_FIX = {"OAK": "LV", "SD": "LAC", "STL": "LAR", "LA": "LAR"}
    DEFUNCT = ["OAK", "SD", "STL"]  # old franchise rows to drop from the teams table

    # Fix the frames we already loaded: take each one, change it, assign it back
    teams_lf = (
        teams_lf.filter(~c.team_abbr.is_in(DEFUNCT))
        .with_columns(c.team_abbr.replace(ABBR_FIX))
        .unique(subset="team_abbr", maintain_order=True)
    )

    schedules_lf = schedules_lf.with_columns(
        c.home_team.replace(ABBR_FIX), c.away_team.replace(ABBR_FIX)
    )

    team_stats_lf = team_stats_lf.with_columns(
        c.team.replace(ABBR_FIX), c.opponent_team.replace(ABBR_FIX)
    )

    max_week = (
        schedules_lf.filter((c.season == max_season) & c.home_score.is_null())
        .select(c.week.min())
        .collect()
        .item()
    )

    if max_week is None:
        max_week = (
            schedules_lf.filter(c.season == max_season)
            .select(c.week.max())
            .collect()
            .item()
        )

    max_week = int(max_week) if max_week is not None else 0


@app.cell
def _():
    rank_lf = rk_fn.build_ranked_grades(schedules_lf, team_stats_lf)
    records_lf = rk_fn.get_weekly_records(schedules_lf)

    full_lf = (
        records_lf.join(
            rank_lf, on=("season", "week", "team"), how="full", coalesce=True
        )
        .sort("season", "team", "week")
        .with_columns(
            # bye rows have no record: copy the previous week's down
            pl.col(
                "cumulative_wins", "cumulative_losses", "cumulative_ties", "record"
            )
            .fill_null(strategy="forward")
            .over("season", "team")
        )
        .join(teams_lf, left_on="team", right_on="team_abbr", how="left")
    )

    team_weekly_lf = full_lf.select(
        # who/when
        "season",
        "week",
        "team",
        "opponent_team",
        "team_score",
        "opp_score",
        "win",
        "loss",
        "tie",
        "cumulative_wins",
        "cumulative_losses",
        "cumulative_ties",
        "record",
        # team info (names, conference, colors, logos)
        "team_name",
        "team_nick",
        "team_conf",
        "team_division",
        "team_color",
        "team_color2",
        "team_color3",
        "team_color4",
        "team_logo_wikipedia",
        "team_logo_espn",
        "team_wordmark",
        "team_conference_logo",
        "team_league_logo",
        "team_logo_squared",
        # final ranking
        "played",
        "rank",
        # every sub-ranking
        pl.selectors.ends_with("_rank"),
    )
    return (team_weekly_lf,)


@app.cell
def _(team_weekly_lf):
    # Heavy work lives in pages/schedule.py. Called once; does not depend on filters.
    schedules_display = nflr_schedule.build_data(schedules_lf, team_weekly_lf, max_season)
    return (schedules_display,)


@app.cell
def _(team_weekly_lf):
    # My Team page data: every graded team-week, collected once.
    graded_df = nflr_my_team.build_data(team_weekly_lf)
    return (graded_df,)


@app.cell
def _(graded_df):
    # My Team page widgets. Each gets its own cell so it is created once and
    # keeps its state when other things change.
    team_view = nflr_my_team.make_view_selector()
    team_season = nflr_my_team.make_season_selector(graded_df)
    team_compare = nflr_my_team.make_compare_selector()
    return team_compare, team_season, team_view


@app.cell
def _(graded_df, team_season):
    # Built from the chosen season, so it is rebuilt (and jumps to that
    # season's latest week) whenever the season changes.
    team_week_slider = nflr_my_team.make_week_slider(graded_df, team_season.value)
    return (team_week_slider,)


@app.cell
def _():
    league_logo_src = teams_lf.select(c.team_league_logo).unique().collect().head(1).item()
    leage_logo = mo.image(src=league_logo_src, width=50, alt="")

    mo.hstack(
        [
            mo.hstack(
                [
                    mo.image(src=league_logo_src, width=50, alt=""),
                    mo.md(f"**NFL Reporter - {max_season}**"),
                    mo.md("_v0.4_"),
                ],
                justify="start",
                align="center",
                gap=1,
            ),
            mo.md(f"_Week {max_week}_"),
        ],
        justify="space-between",
        align="center",
    )
    return


@app.cell
def _(graded_df, selected_team_abbr):
    def _text_color(hex_color):
            """White text on dark backgrounds, near-black on light ones."""
            r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
            brightness = 0.299 * r + 0.587 * g + 0.114 * b  # how light the color looks
            return "#111111" if brightness > 160 else "#ffffff"

    if selected_team_abbr is None:
        _banner = mo.md("")
    else:
        # Identity (always available): name, colors, logo, division
        _team = (
            teams_lf.filter(c.team_abbr == selected_team_abbr)
            .select("team_name", "team_division", "team_color", "team_color2", "team_logo_espn")
            .collect()
            .row(0, named=True)
        )

        # Latest graded record and rank (may not exist yet early in the season)
        _latest = graded_df.filter(
            (c.season == max_season) & (c.team == selected_team_abbr)
        ).sort("week")

        _details = [_team["team_division"]]
        if not _latest.is_empty():
            _row = _latest.tail(1).row(0, named=True)
            _details += [_row["record"], f"Overall rank #{_row['rank']} (Week {_row['week']})"]

        _bg = _team["team_color"] or "#333333"
        _accent = _team["team_color2"] or _bg
        _fg = _text_color(_bg)
        _logo = (
            f'<img src="{_team["team_logo_espn"]}" alt="" '
            'style="height:56px;width:56px;object-fit:contain;">'
            if _team["team_logo_espn"]
            else ""
        )

        _banner = mo.Html(
            f"""
            <div style="display:flex;align-items:center;gap:14px;
                        background:{_bg};color:{_fg};
                        border-bottom:6px solid {_accent};
                        border-radius:10px;padding:12px 16px;">
                {_logo}
                <div>
                    <div style="font-size:1.3em;font-weight:700;">{_team["team_name"]}</div>
                    <div style="font-size:0.9em;opacity:0.9;">{" · ".join(_details)}</div>
                </div>
            </div>
            """
        )

    _banner
    return


@app.cell
def _():
    team_map = {
        row[1]: row[0]
        for row in teams_lf.select(["team_abbr", "team_name"])
        .sort("team_name")
        .collect()
        .rows()
    }
    return (team_map,)


@app.cell
def _(schedules_display, team_map):
    _weeks = sorted(schedules_display["week"].unique().to_list())
    _week_options = ["All Weeks"] + [f"Week {w}" for w in _weeks]
    _default_week = f"Week {max_week}"

    _type_order = [
        "Regular Season",
        "Wild Card",
        "Divisional",
        "Conference Championship",
        "Super Bowl",
    ]
    _types_in_data = schedules_display["game_type"].unique().to_list()
    _game_types = [t for t in _type_order if t in _types_in_data]

    page_nav = mo.ui.radio(
        options=[
            "Schedules & Matchups",
            "My Team",
            "Power Rankings",
            "Players",
        ],
        value="Schedules & Matchups",
    )

    week_dropdown = mo.ui.dropdown(
        options=_week_options,
        value=_default_week if _default_week in _week_options else "All Weeks",
        label="Week",
    )
    # game_type_dropdown = mo.ui.dropdown(
    #     options=["All"] + _game_types,
    #     value="All",
    #     label="Game type",
    # )
    team_dropdown = mo.ui.dropdown(
        options=["All Teams"] + sorted(team_map.keys()),
        value="All Teams",
        label="Team",
    )

    mo.sidebar(
        [
            mo.md("## Navigation"),
            page_nav,
            mo.md("---"),
            mo.md("### Filters"),
            week_dropdown,
            # game_type_dropdown,
            team_dropdown,
        ]
    )
    return page_nav, team_dropdown, week_dropdown


@app.cell
def _(team_dropdown, team_map, week_dropdown):
    selected_week_num = (
        None
        if week_dropdown.value == "All Weeks"
        else int(week_dropdown.value.split(" ")[1])  # "Week 3" -> 3
    )

    # selected_game_type = (
    #     None if game_type_dropdown.value == "All" else game_type_dropdown.value
    # )

    selected_team_abbr = (
        None if team_dropdown.value == "All Teams" else team_map[team_dropdown.value]
    )  # "Philadelphia Eagles" -> "PHI"
    return selected_team_abbr, selected_week_num


@app.cell
def _(schedules_display, selected_team_abbr, selected_week_num):
    # Re-runs whenever a filter changes. Cheap: it only filters and draws.
    schedule_content = nflr_schedule.render(
        schedules_display, max_season, selected_week_num, selected_team_abbr
    )
    return (schedule_content,)


@app.cell
def _(schedules_display, selected_team_abbr, selected_week_num):
    matchup_view = nflr_my_team.make_view_selector()
    matchup_game = nflr_matchups.make_game_selector(
        schedules_display, selected_week_num, selected_team_abbr
    )
    return matchup_game, matchup_view


@app.cell
def _(graded_df, matchup_game, matchup_view):
    matchup_content = nflr_matchups.render(
        graded_df, max_season, matchup_game, matchup_view
    )
    return (matchup_content,)


@app.cell
def _(
    graded_df,
    selected_team_abbr,
    team_compare,
    team_season,
    team_view,
    team_week_slider,
):
    # Re-runs when the team (sidebar), season, week slider or view toggle changes.
    my_team_content = nflr_my_team.render(
        graded_df,
        selected_team_abbr,
        team_season,
        team_week_slider,
        team_view,
        team_compare,
    )
    return (my_team_content,)


@app.cell
def _(graded_df):
    power_df = nflr_power_rankings.build_data(graded_df)
    power_season = nflr_power_rankings.make_season_selector(power_df)
    power_group = nflr_power_rankings.make_group_selector()

    return power_df, power_group, power_season


@app.cell
def _(power_df, power_season):
    power_week = nflr_power_rankings.make_week_selector(power_df, power_season.value)
    return (power_week,)


@app.cell
def _(power_df, power_group, power_season, power_week):
    power_content = nflr_power_rankings.render(
            power_df, power_season, power_week, power_group
        )
    return (power_content,)


@app.cell
def _(
    matchup_content,
    my_team_content,
    page_nav,
    power_content,
    schedule_content,
):
    if page_nav.value == "Schedules & Matchups":
        out = mo.vstack([schedule_content, mo.md("---"), matchup_content])
    elif page_nav.value == "My Team":
        out = my_team_content
    elif page_nav.value == "Power Rankings":
        out = power_content
    elif page_nav.value == "Players":
        out = mo.md("_Player stats coming soon_")
    else:
        out = mo.md("_Injury report coming soon_")

    out
    return


if __name__ == "__main__":
    app.run()
