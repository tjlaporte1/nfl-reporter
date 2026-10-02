import polars as pl
from polars import col as c


def get_complete_weeks(schedules_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Return the latest completed regular-season week for each season.

    This inspects all regular-season games and identifies the final week
    where every game in that season has been played.
    """
    complete_weeks_lf = (
        schedules_lf.filter(c.game_type == "REG")
        .group_by("season", "week")
        .agg(c.home_score.is_null().any().alias("unplayed_game"))
        .filter(~c.unplayed_game)
        .group_by(c.season)
        .agg(c.week.max().alias("complete_through_week"))
    )

    return complete_weeks_lf


def filter_to_complete_weeks(
    team_stats_lf: pl.LazyFrame, complete_weeks_lf: pl.LazyFrame
) -> pl.LazyFrame:
    """Filter team stats down to completed regular-season weeks only.

    A join on season is used to keep only rows whose week is less than or
    equal to the latest completed week for that season.
    """
    return (
        team_stats_lf.filter(c.season_type == "REG")
        .join(complete_weeks_lf, on="season")
        .filter(c.week <= c.complete_through_week)
    )


def join_opponent_stats(filtered_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Join each team’s opponent's passing and rushing volume onto the row.

    This adds defensive usage context for the opponent so that team-level
    efficiency and pressure metrics can be evaluated against the proper matchup.
    """
    opponent_lf = filtered_lf.select(
        "season",
        "week",
        "team",
        c.passing_yards.alias("passing_yards_allowed"),
        c.attempts.alias("attempts_allowed"),
        c.rushing_yards.alias("rushing_yards_allowed"),
        c.carries.alias("carries_allowed"),
    )
    return filtered_lf.join(
        opponent_lf,
        left_on=["season", "week", "opponent_team"],
        right_on=["season", "week", "team"],
    )


def compute_cumulative_totals(joined_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Compute season-to-date totals for offense, defense, and special teams stats.

    The result is used to derive weekly rate-based metrics from cumulative
    totals rather than single-week snapshots.
    """
    return joined_lf.sort("season", "team", "week").with_columns(
        c.passing_yards.cum_sum().over("season", "team").alias("passing_yards_ytd"),
        c.attempts.cum_sum().over("season", "team").alias("attempts_ytd"),
        c.rushing_yards.cum_sum().over("season", "team").alias("rushing_yards_ytd"),
        c.carries.cum_sum().over("season", "team").alias("carries_ytd"),
        c.passing_tds.cum_sum().over("season", "team").alias("passing_tds_ytd"),
        c.rushing_tds.cum_sum().over("season", "team").alias("rushing_tds_ytd"),
        c.passing_yards_allowed.cum_sum()
        .over("season", "team")
        .alias("passing_yards_allowed_ytd"),
        c.attempts_allowed.cum_sum()
        .over("season", "team")
        .alias("attempts_allowed_ytd"),
        c.rushing_yards_allowed.cum_sum()
        .over("season", "team")
        .alias("rushing_yards_allowed_ytd"),
        c.carries_allowed.cum_sum().over("season", "team").alias("carries_allowed_ytd"),
        c.def_sacks.cum_sum().over("season", "team").alias("def_sacks_ytd"),
        c.def_qb_hits.cum_sum().over("season", "team").alias("def_qb_hits_ytd"),
        c.def_fumbles_forced.cum_sum()
        .over("season", "team")
        .alias("def_fumbles_forced_ytd"),
        c.def_interceptions.cum_sum()
        .over("season", "team")
        .alias("def_interceptions_ytd"),
        c.pt_att.cum_sum().over("season", "team").alias("pt_att_ytd"),
        c.pt_net_yards.cum_sum().over("season", "team").alias("pt_net_yards_ytd"),
        c.pt_inside_20.cum_sum().over("season", "team").alias("pt_inside_20_ytd"),
        c.week.cum_count().over("season", "team").alias("games_played_ytd"),
    )


def compute_fg_cumulative_totals(joined_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Compute season-to-date field goal makeup by distance bucket.

    This tracks made and missed attempts for each field goal range to support
    league-adjusted field goal value calculations.
    """
    return (
        joined_lf.sort("season", "team", "week")
        .with_columns(
            c.fg_att.cum_sum().over("season", "team").alias("fg_att_ytd"),
            c.fg_made_0_19.cum_sum().over("season", "team").alias("fg_made_0_19_ytd"),
            c.fg_missed_0_19.cum_sum()
            .over("season", "team")
            .alias("fg_missed_0_19_ytd"),
            c.fg_made_20_29.cum_sum().over("season", "team").alias("fg_made_20_29_ytd"),
            c.fg_missed_20_29.cum_sum()
            .over("season", "team")
            .alias("fg_missed_20_29_ytd"),
            c.fg_made_30_39.cum_sum().over("season", "team").alias("fg_made_30_39_ytd"),
            c.fg_missed_30_39.cum_sum()
            .over("season", "team")
            .alias("fg_missed_30_39_ytd"),
            c.fg_made_40_49.cum_sum().over("season", "team").alias("fg_made_40_49_ytd"),
            c.fg_missed_40_49.cum_sum()
            .over("season", "team")
            .alias("fg_missed_40_49_ytd"),
            c.fg_made_50_59.cum_sum().over("season", "team").alias("fg_made_50_59_ytd"),
            c.fg_missed_50_59.cum_sum()
            .over("season", "team")
            .alias("fg_missed_50_59_ytd"),
            c.fg_made_60_.cum_sum().over("season", "team").alias("fg_made_60_ytd"),
            c.fg_missed_60_.cum_sum().over("season", "team").alias("fg_missed_60_ytd"),
        )
        .with_columns(
            (c.fg_made_0_19_ytd + c.fg_missed_0_19_ytd).alias("fg_att_0_19_ytd"),
            (c.fg_made_20_29_ytd + c.fg_missed_20_29_ytd).alias("fg_att_20_29_ytd"),
            (c.fg_made_30_39_ytd + c.fg_missed_30_39_ytd).alias("fg_att_30_39_ytd"),
            (c.fg_made_40_49_ytd + c.fg_missed_40_49_ytd).alias("fg_att_40_49_ytd"),
            (c.fg_made_50_59_ytd + c.fg_missed_50_59_ytd).alias("fg_att_50_59_ytd"),
            (c.fg_made_60_ytd + c.fg_missed_60_ytd).alias("fg_att_60_ytd"),
        )
    )


def compute_rate_stats(cumulative_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Compute season-to-date efficiency and rate metrics from cumulative totals.

    Metrics include per-attempt passing and rushing rates, touchdown rate,
    pressure rate, turnover rate, net punting average, and inside-20 rate.
    """
    return cumulative_lf.with_columns(
        pl.when(c.attempts_ytd > 0)
        .then(c.passing_yards_ytd / c.attempts_ytd)
        .otherwise(None)
        .alias("pass_ypa"),
        pl.when(c.carries_ytd > 0)
        .then(c.rushing_yards_ytd / c.carries_ytd)
        .otherwise(None)
        .alias("rush_ypc"),
        pl.when(c.games_played_ytd > 0)
        .then((c.passing_tds_ytd + c.rushing_tds_ytd) / c.games_played_ytd)
        .otherwise(None)
        .alias("td_rate"),
        pl.when(c.attempts_allowed_ytd > 0)
        .then(c.passing_yards_allowed_ytd / c.attempts_allowed_ytd)
        .otherwise(None)
        .alias("pass_ypa_allowed"),
        pl.when(c.carries_allowed_ytd > 0)
        .then(c.rushing_yards_allowed_ytd / c.carries_allowed_ytd)
        .otherwise(None)
        .alias("rush_ypc_allowed"),
        pl.when(c.attempts_allowed_ytd > 0)
        .then((c.def_sacks_ytd + c.def_qb_hits_ytd) / c.attempts_allowed_ytd)
        .otherwise(None)
        .alias("pressure_rate"),
        pl.when((c.attempts_allowed_ytd + c.carries_allowed_ytd) > 0)
        .then(
            (c.def_interceptions_ytd + c.def_fumbles_forced_ytd)
            / (c.attempts_allowed_ytd + c.carries_allowed_ytd)
        )
        .otherwise(None)
        .alias("turnover_rate"),
        pl.when(c.pt_att_ytd > 0)
        .then(c.pt_net_yards_ytd / c.pt_att_ytd)
        .otherwise(None)
        .alias("net_ypp"),
        pl.when(c.pt_att_ytd > 0)
        .then(c.pt_inside_20_ytd / c.pt_att_ytd)
        .otherwise(None)
        .alias("inside_20_rate"),
    )


def compute_fg_value(fg_cumulative_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Compute a league-adjusted field goal value metric by bucket.

    The function compares each team’s field-goal efficiency by distance to the
    league average and then aggregates the deltas into a single fg_value score.
    """
    bucket_suffixes = [
        "0_19_ytd",
        "20_29_ytd",
        "30_39_ytd",
        "40_49_ytd",
        "50_59_ytd",
        "60_ytd",
    ]

    league_avg_lf = fg_cumulative_lf.group_by("season", "week").agg(
        [
            (pl.col(f"fg_made_{s}").sum() / pl.col(f"fg_att_{s}").sum())
            .fill_null(0)
            .fill_nan(0)
            .alias(f"league_pct_{s}")
            for s in bucket_suffixes
        ]
    )

    value_lf = fg_cumulative_lf.join(league_avg_lf, on=["season", "week"]).with_columns(
        [
            (
                pl.col(f"fg_made_{s}")
                - pl.col(f"league_pct_{s}") * pl.col(f"fg_att_{s}")
            ).alias(f"fg_value_{s}")
            for s in bucket_suffixes
        ]
    )

    return value_lf.with_columns(
        pl.sum_horizontal([f"fg_value_{s}" for s in bucket_suffixes]).alias(
            "fg_value_total"
        )
    ).with_columns(
        pl.when(pl.col("fg_att_ytd") > 0)
        .then(pl.col("fg_value_total") / pl.col("fg_att_ytd"))
        .otherwise(None)
        .alias("fg_value")
    )


def zscore_columns(
    lf: pl.LazyFrame,
    stat_cols: list[str],
    invert_cols: list[str] | None = None,
) -> pl.LazyFrame:
    """Add z-scores for a list of columns, optionally inverting selected metrics.

    `invert_cols` is used for metrics where a lower value is better, such as
    defensive yards allowed.
    """
    invert_cols = invert_cols or []
    z_exprs = []
    for col_name in stat_cols:
        sign = -1 if col_name in invert_cols else 1
        z_expr = (
            sign
            * (pl.col(col_name) - pl.col(col_name).mean().over("season", "week"))
            / pl.col(col_name).std().over("season", "week")
        ).alias(f"z_{col_name}")
        z_exprs.append(z_expr)
    return lf.with_columns(z_exprs)


def compute_component_scores(zscored_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Combine z-scored components into offense, defense, and special teams scores.

    This calculates the weighted aggregate metrics used to rank team strength
    by phase of play.
    """
    return zscored_lf.with_columns(
        (c.z_pass_ypa * 0.40 + c.z_rush_ypc * 0.40 + c.z_td_rate * 0.20).alias(
            "offense_score"
        ),
        (c.z_pressure_rate * 0.50 + c.z_turnover_rate * 0.50).alias("disruption_blend"),
        (c.z_net_ypp * 0.70 + c.z_inside_20_rate * 0.30).alias("punting_score_z"),
    ).with_columns(
        (
            c.z_pass_ypa_allowed * 0.40
            + c.z_rush_ypc_allowed * 0.40
            + c.disruption_blend * 0.20
        ).alias("defense_score"),
        (c.z_fg_value * 0.70 + c.punting_score_z * 0.30).alias("special_teams_score"),
    )


def compute_overall_partial(component_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Compute the weighted partial overall rating before strength-of-schedule adjustment."""
    return component_lf.with_columns(
        (
            c.offense_score * 0.35
            + c.defense_score * 0.35
            + c.special_teams_score * 0.05
        ).alias("overall_partial")
    )


def compute_sos(overall_partial_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate season-to-date strength of schedule from opponent grades.

    The first week is locked to zero so the schedule metric initializes cleanly
    and does not penalize Week 1 matchups.
    """
    grade_lookup_lf = overall_partial_lf.select(
        "season", "week", "team", "overall_partial"
    )

    matchups_lf = overall_partial_lf.select("season", "week", "team", "opponent_team")

    joined_lf = matchups_lf.join(
        grade_lookup_lf.rename(
            {"team": "opponent_team", "overall_partial": "opponent_grade"}
        ),
        on=["season", "week", "opponent_team"],
        how="left",
    )

    locked_lf = joined_lf.with_columns(
        pl.when(c.week == 1)
        .then(0.0)
        .otherwise(c.opponent_grade)
        .alias("opponent_grade_locked")
    )

    return (
        locked_lf.sort("season", "team", "week")
        .with_columns(
            c.opponent_grade_locked.cum_sum()
            .over("season", "team")
            .alias("opponent_grade_sum_ytd"),
            c.week.cum_count().over("season", "team").alias("weeks_played_ytd"),
        )
        .with_columns(
            (c.opponent_grade_sum_ytd / c.weeks_played_ytd).alias("sos_score")
        )
        .select("season", "week", "team", "sos_score")
    )


def build_weekly_grades(
    schedules_lf: pl.LazyFrame, team_stats_lf: pl.LazyFrame
) -> pl.LazyFrame:
    """Build a weekly team-grade frame with rates, z-scores, component scores, and final grades.

    The pipeline loads completed weeks, joins opponent data, computes
    cumulative and rate stats, creates z-scored inputs, and produces the
    final weekly team ratings.
    """
    complete_weeks_lf = get_complete_weeks(schedules_lf)
    filtered_lf = filter_to_complete_weeks(team_stats_lf, complete_weeks_lf)
    joined_lf = join_opponent_stats(filtered_lf)

    cumulative_lf = compute_cumulative_totals(joined_lf)
    fg_cumulative_lf = compute_fg_cumulative_totals(joined_lf)
    fg_value_lf = compute_fg_value(fg_cumulative_lf)

    merged_cumulative_lf = cumulative_lf.join(
        fg_value_lf.select("season", "team", "week", "fg_value"),
        on=["season", "team", "week"],
    )

    rates_lf = compute_rate_stats(merged_cumulative_lf)

    zscored_lf = zscore_columns(
        rates_lf,
        stat_cols=[
            "pass_ypa",
            "rush_ypc",
            "td_rate",
            "pass_ypa_allowed",
            "rush_ypc_allowed",
            "pressure_rate",
            "turnover_rate",
            "net_ypp",
            "inside_20_rate",
            "fg_value",
        ],
        invert_cols=["pass_ypa_allowed", "rush_ypc_allowed"],
    )

    component_lf = compute_component_scores(zscored_lf)
    overall_partial_lf = compute_overall_partial(component_lf)

    sos_lf = compute_sos(overall_partial_lf)

    final_lf = overall_partial_lf.join(
        sos_lf.select("season", "week", "team", "sos_score"),
        on=["season", "week", "team"],
    ).with_columns((c.overall_partial + c.sos_score * 0.25).alias("overall_score"))

    return final_lf.select(
        # identity
        "season",
        "week",
        "team",
        "opponent_team",
        # rate stats (pre-z-score, useful for sanity-checking real-world numbers)
        "pass_ypa",
        "rush_ypc",
        "td_rate",
        "pass_ypa_allowed",
        "rush_ypc_allowed",
        "pressure_rate",
        "turnover_rate",
        "net_ypp",
        "inside_20_rate",
        "fg_value",
        # z-scored stats
        "z_pass_ypa",
        "z_rush_ypc",
        "z_td_rate",
        "z_pass_ypa_allowed",
        "z_rush_ypc_allowed",
        "z_pressure_rate",
        "z_turnover_rate",
        "z_net_ypp",
        "z_inside_20_rate",
        "z_fg_value",
        "disruption_blend",
        "punting_score_z",
        # component + final scores
        "offense_score",
        "defense_score",
        "special_teams_score",
        "overall_partial",
        "sos_score",
        "overall_score",
    )


def compute_rank(final_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Add ordinal rankings for overall, component, and sub-component grades.

    Rankings are computed within each season/week cohort, with higher values
    receiving the better rank.
    """
    return final_lf.with_columns(
        # overall + 4 main components
        c.overall_score.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("rank"),
        c.offense_score.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("offense_rank"),
        c.defense_score.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("defense_rank"),
        c.special_teams_score.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("special_teams_rank"),
        c.sos_score.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("sos_rank"),
        # offense sub-components
        c.z_pass_ypa.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("passing_rank"),
        c.z_rush_ypc.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("rushing_rank"),
        c.z_td_rate.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("td_rank"),
        # defense sub-components
        c.z_pass_ypa_allowed.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("pass_defense_rank"),
        c.z_rush_ypc_allowed.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("rush_defense_rank"),
        c.disruption_blend.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("disruption_rank"),
        # special teams sub-components
        c.z_fg_value.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("fg_rank"),
        c.punting_score_z.rank(method="ordinal", descending=True)
        .over("season", "week")
        .alias("punting_rank"),
    )


def build_ranked_grades(
    schedules_lf: pl.LazyFrame, team_stats_lf: pl.LazyFrame
) -> pl.LazyFrame:
    """Build weekly team grades and add rankings, from raw schedules and team stats."""
    weekly_grades_lf = build_weekly_grades(schedules_lf, team_stats_lf)
    return compute_rank(weekly_grades_lf)


def get_weekly_records(schedules_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Compute weekly win/loss/tie records and cumulative totals for each team.

    This function transforms the schedule data into a team-centric view, where each
    row represents a single team's performance in a given week. It calculates wins,
    losses, and ties based on the scores, and then computes cumulative totals for each
    team across the season.

    Args:
        schedules_lf (pl.LazyFrame): A lazy frame containing the schedule data with
            columns for season, week, home_team, away_team, home_score, and away_score.

    Returns:
        pl.LazyFrame: A lazy frame with columns for season, week, team, team_score,
            opp_score, win, loss, tie, cumulative_wins, cumulative_losses,
            and cumulative_ties, sorted by team and week.
    """

    home_lf = schedules_lf.select(
        [
            c.season,
            c.week,
            c.home_team.alias("team"),
            c.home_score.alias("team_score"),
            c.away_score.alias("opp_score"),
        ]
    )

    away_lf = schedules_lf.select(
        [
            c.season,
            c.week,
            c.away_team.alias("team"),
            c.away_score.alias("team_score"),
            c.home_score.alias("opp_score"),
        ]
    )

    combined_lf = pl.concat([home_lf, away_lf])

    result_lf = combined_lf.with_columns(
        [
            # Win
            pl.when(c.team_score > c.opp_score).then(1).otherwise(0).alias("win"),
            # Loss
            pl.when(c.team_score < c.opp_score).then(1).otherwise(0).alias("loss"),
            # Tie
            pl.when(c.team_score == c.opp_score).then(1).otherwise(0).alias("tie"),
        ]
    )

    records_lf = result_lf.with_columns(
        [
            c.win.cum_sum()
            .over(["season", "team"], order_by="week")
            .alias("cumulative_wins"),
            c.loss.cum_sum()
            .over(["season", "team"], order_by="week")
            .alias("cumulative_losses"),
            c.tie.cum_sum()
            .over(["season", "team"], order_by="week")
            .alias("cumulative_ties"),
        ]
    )

    return records_lf.sort(["team", "week"])
