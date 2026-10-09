import marimo

__generated_with = "0.24.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import nflreadpy as nfl
    import polars as pl
    import plotly.express as px
    import plotly.graph_objects as go
    from polars import col as c

    import rank_functions as rk_fn

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

    max_week = (
        schedules_lf.filter(c.home_score.is_not_null())
        .select(c.week.max())
        .collect()
        .item()
    )

    max_week = int(max_week) if max_week is not None else 0
    return (
        c,
        go,
        max_week,
        mo,
        pl,
        rk_fn,
        schedules_lf,
        team_stats_lf,
        teams_lf,
    )


@app.cell
def _(rk_fn, schedules_lf, team_stats_lf):
    rank_lf = rk_fn.build_ranked_grades(schedules_lf, team_stats_lf)
    return (rank_lf,)


@app.cell
def _(c, rank_lf):
    rank_lf.filter((c.season == 2026) & (c.week == 3))
    return


@app.cell
def _(rk_fn, schedules_lf):
    records_lf = rk_fn.get_weekly_records(schedules_lf)
    return (records_lf,)


@app.cell
def _(rank_lf, records_lf, teams_lf):
    full_lf = records_lf.join(rank_lf, on=("season", "week", "team"), how="left").join(
        teams_lf, left_on="team", right_on="team_abbr", how="left")
    return (full_lf,)


@app.cell
def _(full_lf):
    full_lf
    return


@app.cell
def _(full_lf, pl):
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
        "rank",
        # every sub-ranking
        pl.selectors.ends_with("_rank"),
    )
    return (team_weekly_lf,)


@app.cell
def _(team_weekly_lf):
    team_weekly_lf.collect_schema().names()
    return


@app.cell
def _(go):
    # ---- cell 3: axes + radar builder ----
    # label on chart -> rank column. Spokes go clockwise from just right of the top:
    # offense (top right), FG / SOS / Punting (bottom), defense (top left).
    AXES = {
        "Passing": "passing_rank",
        "Rushing": "rushing_rank",
        "TDs": "td_rank",
        "FG Unit": "fg_rank",
        "SOS": "sos_rank",
        "Punting Unit": "punting_rank",
        "Disruption": "disruption_rank",
        "Rush defense": "rush_defense_rank",
        "Pass defense": "pass_defense_rank",
    }

    # Background wedges in the same clockwise order: (name, color, number of spokes it covers).
    # Counts must add up to len(AXES). The last number in each rgba(...) is the opacity.
    UNITS = [
        ("Offense", "rgba(44,160,44,0.07)", 3),
        ("Special teams", "rgba(31,119,180,0.07)", 1),  # FG value
        ("Strength of schedule", "rgba(128,128,128,0.10)", 1),  # SOS
        ("Special teams", "rgba(31,119,180,0.07)", 1),  # Punting
        ("Defense", "rgba(214,39,40,0.07)", 3),
    ]


    def build_radar(row):
        """row = one team's graded row for one week (a dict)."""
        step = 360 / len(AXES)  # degrees per spoke (40 for 9 spokes)
        angles = [(i + 0.5) * step for i in range(len(AXES))]  # half-step offset puts SOS at the bottom
        ranks = [row[col] for col in AXES.values()]  # can contain None if a stat is missing
        color = row["team_color"]

        fig = go.Figure()

        # 1) background wedges: centre -> arc along the outer edge -> back to centre
        first, seen = 0, set()
        for name, wedge_color, n in UNITS:
            start, end = first * step, (first + n) * step  # wedge edges sit halfway between spokes
            arc = [(start + i * (end - start) / 20) % 360 for i in range(21)]
            fig.add_trace(go.Scatterpolar(
                r=[32] + [1] * 21 + [32], theta=[arc[0]] + arc + [arc[-1]],
                mode="lines", fill="toself", fillcolor=wedge_color, line=dict(width=0),
                name=name, legendgroup=name, showlegend=name not in seen, hoverinfo="skip",
            ))
            seen.add(name)
            first += n

        # 2) the team's shape: see-through fill + outline (first point repeated to close it)
        fig.add_trace(go.Scatterpolar(
            r=ranks + ranks[:1], theta=angles + angles[:1],
            mode="lines", fill="toself", connectgaps=True, opacity=0.7, showlegend=False,
            line=dict(color=color, width=2), fillcolor=color, hoverinfo="skip",
        ))

        # 3) the rank dots: a separate trace so they stay fully solid (not see-through like the fill)
        fig.add_trace(go.Scatterpolar(
            r=ranks, theta=angles, text=list(AXES),
            mode="markers", showlegend=False,
            marker=dict(size=9, color=color, line=dict(color="white", width=2)),
            hovertemplate="%{text}: #%{r}<extra></extra>",
        ))

        fig.update_layout(
            title=f"{row['team_name']}: Week {row['week']}",
            polar=dict(
                # reversed: rank 1 on the outer edge; hide the rank numbers and axis line
                radialaxis=dict(range=[32, 1], showticklabels=False, showline=False),
                angularaxis=dict(
                    rotation=90, direction="clockwise",
                    tickmode="array", tickvals=angles, ticktext=list(AXES),
                ),
            ),
            height=600,
        )
        return fig

    return (build_radar,)


@app.cell
def _(c, mo, team_weekly_lf):
    # ---- cell 4: season + team dropdowns (create only, don't read .value here) ----
    # Keep only weeks that have been graded. The table also has rows for unplayed
    # future games, and those have empty ranks.
    played_lf = team_weekly_lf.filter(c.offense_rank.is_not_null())

    season_options = played_lf.select(c.season).unique().sort(c.season).collect().to_series().to_list()
    team_options = played_lf.select(c.team).unique().sort(c.team).collect().to_series().to_list()

    season_dd = mo.ui.dropdown(
        options=[str(s) for s in season_options], value=str(season_options[-1]), label="Season"
    )
    team_dd = mo.ui.dropdown(options=team_options, value=team_options[0], label="Team")
    return played_lf, season_dd, team_dd


@app.cell
def _(c, max_week, mo, played_lf, season_dd, team_dd):
    # ---- cell 5: that team's season + the week slider (create the slider here, don't read its .value) ----
    team_df = (
        played_lf.filter(c.season == int(season_dd.value), c.team == team_dd.value)
        .sort("week")
        .collect()
    )
    weeks = team_df["week"].to_list()  # only graded weeks the team played

    # default to max_week, or the closest earlier week this team played (e.g. if they had a bye)
    default_week = max((w for w in weeks if w <= max_week), default=weeks[0])

    week_slider = mo.ui.slider(steps=weeks, value=default_week, label="Week", show_value=True)
    return team_df, week_slider


@app.cell
def _(build_radar, c, mo, season_dd, team_dd, team_df, week_slider):
    # ---- cell 6: display (reads week_slider.value, so it must be its own cell) ----
    selected_row = team_df.filter(c.week == week_slider.value).row(0, named=True)

    mo.vstack([
        mo.hstack([season_dd, team_dd, week_slider], justify="start"),
        build_radar(selected_row),
    ])
    return


if __name__ == "__main__":
    app.run()
