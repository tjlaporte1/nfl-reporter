import marimo

__generated_with = "0.25.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import nflreadpy as nfl
    import polars as pl
    import plotly.express as px
    import plotly.graph_objects as go
    from polars import col as c

    import functions.rank_functions as rk_fn

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
    return c, go, mo, pl, rk_fn, schedules_lf, team_stats_lf, teams_lf


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
def _(records_lf):
    records_lf
    return


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
    # ---- cell 3: axes, wedges and radar builder ----
    # --- detailed view: label on chart -> rank column (spokes go clockwise from just right of the top)
    DETAILED_AXES = {
        "Passing": "passing_rank",
        "Rushing": "rushing_rank",
        "TDs": "td_rank",
        "FG value": "fg_rank",
        "Punting": "punting_rank",
        "SOS": "sos_rank",
        "Disruption": "disruption_rank",
        "Rush defense": "rush_defense_rank",
        "Pass defense": "pass_defense_rank",
    }
    # background wedges in the same clockwise order: (name, color, number of spokes it covers)
    DETAILED_UNITS = [
        ("Offense", "rgba(44,160,44,0.07)", 3),
        ("Special teams", "rgba(31,119,180,0.07)", 2),  # FG value
        ("Strength of schedule", "rgba(128,128,128,0.10)", 1),  # SOS
        ("Defense", "rgba(214,39,40,0.07)", 3),
    ]

    # --- overview view: the four high-level ranks, one per quadrant
    OVERVIEW_AXES = {
        "Offense": "offense_rank",
        "Special teams": "special_teams_rank",
        "SOS": "sos_rank",
        "Defense": "defense_rank",
    }
    OVERVIEW_UNITS = [
        ("Offense", "rgba(44,160,44,0.07)", 1),
        ("Special teams", "rgba(31,119,180,0.07)", 1),
        ("Strength of schedule", "rgba(128,128,128,0.10)", 1),
        ("Defense", "rgba(214,39,40,0.07)", 1),
    ]

    # toggle label -> (axes, wedges). Wedge counts must add up to the number of axes.
    VIEWS = {
        "Overview": (OVERVIEW_AXES, OVERVIEW_UNITS),
        "Detailed": (DETAILED_AXES, DETAILED_UNITS),
    }


    def build_radar(row, axes, units):
        """row = one team's graded row for one week (a dict); axes/units = one entry of VIEWS."""
        step = 360 / len(axes)  # degrees per spoke
        angles = [(i + 0.5) * step for i in range(len(axes))]  # half-step offset keeps spokes off the top/bottom lines
        ranks = [row[col] for col in axes.values()]  # can contain None if a stat is missing
        color = row["team_color"]

        fig = go.Figure()

        # 1) background wedges: centre -> arc along the outer edge -> back to centre
        first, seen = 0, set()
        for name, wedge_color, n in units:
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

        # 3) the rank dots: a separate trace so they stay fully solid
        fig.add_trace(go.Scatterpolar(
            r=ranks, theta=angles, text=list(axes),
            mode="markers", showlegend=False,
            marker=dict(size=14, color=color, line=dict(color="white", width=3)),
            hovertemplate="%{text}: #%{r}<extra></extra>",
        ))

        fig.update_layout(
            title=f"{row['team_name']}: Week {row['week']}",
            polar=dict(
                # reversed: rank 1 on the outer edge; hide the rank numbers and axis line
                radialaxis=dict(range=[32, 1], showticklabels=False, showline=False),
                angularaxis=dict(
                    rotation=90, direction="clockwise",
                    tickmode="array", tickvals=angles, ticktext=list(axes),
                ),
            ),
            height=600,
        )
        return fig

    return VIEWS, build_radar


@app.cell
def _(c, mo, team_weekly_lf):
    # ---- cell 4: season + team dropdowns and the view toggle (create only, don't read .value here) ----
    # Keep only weeks that have been graded. The table also has rows for unplayed
    # future games, and those have empty ranks.
    played_lf = team_weekly_lf.filter(c.offense_rank.is_not_null())

    season_options = played_lf.select(c.season).unique().sort(c.season).collect().to_series().to_list()
    team_options = played_lf.select(c.team).unique().sort(c.team).collect().to_series().to_list()

    season_dd = mo.ui.dropdown(
        options=[str(s) for s in season_options], value=str(season_options[-1]), label="Season"
    )
    team_dd = mo.ui.dropdown(options=team_options, value=team_options[0], label="Team")
    view_radio = mo.ui.radio(options=["Overview", "Detailed"], value="Overview", inline=True, label="View")
    latest_week = played_lf.filter(c.season == season_options[-1]).select(c.week.max()).collect().item()
    week_slider = mo.ui.slider(start=1, stop=18, value=latest_week, label="Week", show_value=True)
    return played_lf, season_dd, team_dd, view_radio, week_slider


@app.cell
def _(c, played_lf, season_dd, team_dd):
    # ---- cell 5: that team's season + the week slider (create the slider here, don't read its .value) ----
    team_df = (
        played_lf.filter(c.season == int(season_dd.value), c.team == team_dd.value)
        .sort("week")
        .collect()
    )
    return (team_df,)


@app.cell
def _(
    VIEWS,
    build_radar,
    c,
    mo,
    season_dd,
    team_dd,
    team_df,
    view_radio,
    week_slider,
):
    # ---- cell 6: display ----
    weeks = team_df["week"].to_list()  # graded weeks this team played
    week = max((w for w in weeks if w <= week_slider.value), default=weeks[0])  # closest earlier week
    selected_row = team_df.filter(c.week == week).row(0, named=True)
    axes, units = VIEWS[view_radio.value]

    mo.vstack([
        mo.hstack([season_dd, team_dd, week_slider, view_radio], justify="start"),
        build_radar(selected_row, axes, units),
    ])
    return


if __name__ == "__main__":
    app.run()
