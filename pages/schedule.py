"""Schedule page.

Two functions are meant to be called from dashboard.py:

    build_data(schedules_lf, team_weekly_lf, season)
        Does the heavy work (joins, ranks, records, labels) and returns a
        collected Polars DataFrame. Call this ONCE.

    render(schedule_df, season, week_num=None, team_abbr=None)
        Applies the filters and returns the finished marimo page.
        Cheap, so it can re-run every time a filter changes.

Everything this file needs is passed in as an argument. A separate .py file
cannot see variables defined in dashboard.py (like max_season or
schedules_lf), so the dashboard hands them over when it calls the functions.
"""

import marimo as mo
import polars as pl
from polars import col as c

# ─────────────────────────────────────────────────────────────────────────────
# Constants (a leading underscore means "private to this file")
# ─────────────────────────────────────────────────────────────────────────────

_GAME_TYPE_NAMES = {
    "REG": "Regular Season",
    "WC": "Wild Card",
    "DIV": "Divisional",
    "CON": "Conference Championship",
    "SB": "Super Bowl",
}

# Keys = columns to show (in this order). Values = the names shown in the table.
_COLUMN_NAMES = {
    "week": "Week",
    "matchup": "Matchup",
    "result": "Result",
    "date_display": "Date",
    "weekday": "Weekday",
    "time_display": "Time",
    "stadium": "Stadium",
}


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers that build Polars expressions
# An expression is a *description* of a calculation; Polars runs it later,
# once for every row.
# ─────────────────────────────────────────────────────────────────────────────


def _record_label(side):
    """Build "2-1" or "2-1-1" text for one side ("away" or "home")."""
    w = pl.col(f"{side}_w").fill_null(0).cast(pl.Int64)
    l = pl.col(f"{side}_l").fill_null(0).cast(pl.Int64)
    t = pl.col(f"{side}_t").fill_null(0).cast(pl.Int64)
    base = w.cast(pl.Utf8) + "-" + l.cast(pl.Utf8)
    return pl.when(t > 0).then(base + "-" + t.cast(pl.Utf8)).otherwise(base)


def _team_label(side):
    """Build "#3 PHI (2-1)" for one side. The rank is left out if unranked."""
    rank = pl.col(f"{side}_rank")
    rank_text = (
        pl.when(rank.is_not_null())
        .then(pl.lit("#") + rank.cast(pl.Utf8) + pl.lit(" "))
        .otherwise(pl.lit(""))
    )
    return rank_text + pl.col(f"{side}_team") + " (" + pl.col(f"{side}_record") + ")"


# Winner of a finished game: team abbreviation, or "Tie"
_WINNER = (
    pl.when(c.away_score > c.home_score)
    .then(c.away_team)
    .when(c.home_score > c.away_score)
    .then(c.home_team)
    .otherwise(pl.lit("Tie"))
)


# ─────────────────────────────────────────────────────────────────────────────
# Function 1: build the data (heavy, call once)
# ─────────────────────────────────────────────────────────────────────────────


def build_data(schedules_lf, team_weekly_lf, season):
    """Return a collected DataFrame with one row per game, ready to display."""

    # Each team's most recent overall rank this season (stays lazy)
    # pl.col("rank") is used because "rank" is also a Polars method name.
    ranks_lf = (
        team_weekly_lf.filter((c.season == season) & pl.col("rank").is_not_null())
        .sort("week")
        .group_by("team")
        .agg(pl.col("rank").last().cast(pl.Int64).alias("rank"))
    )

    # Each team's running record after every week it played
    records_lf = (
        team_weekly_lf.filter(c.season == season)
        .select(
            "team",
            c.week.cast(pl.Int64),
            "cumulative_wins",
            "cumulative_losses",
            "cumulative_ties",
        )
        .sort("week")  # join_asof needs this sorted by week
    )

    lf = (
        schedules_lf.filter(c.season == season)
        .select(
            [
                c.week.cast(pl.Int64),
                "game_type",
                "away_team",
                "home_team",
                "gameday",
                "weekday",
                "gametime",
                "away_score",
                "home_score",
                "stadium",
            ]
        )
        .sort("week")  # join_asof needs the left side sorted by week too
        # Records going INTO the game: latest row from an earlier week
        # (allow_exact_matches=False excludes the game's own week)
        .join_asof(
            records_lf.rename(
                {
                    "team": "away_team",
                    "cumulative_wins": "away_w",
                    "cumulative_losses": "away_l",
                    "cumulative_ties": "away_t",
                }
            ),
            on="week",
            by="away_team",
            strategy="backward",
            allow_exact_matches=False,
        )
        .join_asof(
            records_lf.rename(
                {
                    "team": "home_team",
                    "cumulative_wins": "home_w",
                    "cumulative_losses": "home_l",
                    "cumulative_ties": "home_t",
                }
            ),
            on="week",
            by="home_team",
            strategy="backward",
            allow_exact_matches=False,
        )
        # Ranks (regular joins; the sort below restores the order)
        .join(
            ranks_lf.rename({"team": "away_team", "rank": "away_rank"}),
            on="away_team",
            how="left",
        )
        .join(
            ranks_lf.rename({"team": "home_team", "rank": "home_rank"}),
            on="home_team",
            how="left",
        )
        .sort(["week", "gameday", "gametime"])
        # Step A: simple new columns that Step B will use
        .with_columns(
            _record_label("away").alias("away_record"),
            _record_label("home").alias("home_record"),
            # True when both teams are ranked in the top 10 (nulls become False)
            ((c.away_rank <= 10) & (c.home_rank <= 10)).fill_null(False).alias("top_10"),
            pl.col("game_type").replace(_GAME_TYPE_NAMES).alias("game_type"),
        )
        # Step B: display columns built from Step A's columns
        .with_columns(
            # Matchup: "★ " in front for top-10 vs top-10 games
            (
                pl.when(c.top_10).then(pl.lit("★ ")).otherwise(pl.lit(""))
                + _team_label("away")
                + " @ "
                + _team_label("home")
            ).alias("matchup"),
            # Result: "24 - 20 (PHI)" (away - home, winner) or "Upcoming"
            pl.when(c.away_score.is_not_null())
            .then(
                c.away_score.cast(pl.Int64).cast(pl.Utf8)
                + " - "
                + c.home_score.cast(pl.Int64).cast(pl.Utf8)
                + " ("
                + _WINNER
                + ")"
            )
            .otherwise(pl.lit("Upcoming"))
            .alias("result"),
            pl.col("gameday")
            .str.strptime(pl.Date, "%Y-%m-%d")  # "2025-09-07" -> Date
            .dt.strftime("%b %-d, %Y")  # -> "Sep 7, 2025"
            .alias("date_display"),
            pl.when(pl.col("gametime").is_not_null())
            .then(
                pl.col("gametime")
                .str.strptime(pl.Time, "%H:%M")  # "13:00" -> Time
                .dt.strftime("%-I:%M %p")  # -> "1:00 PM"
                + " ET"
            )
            .otherwise(pl.lit("TBD"))
            .alias("time_display"),
        )
    )

    # Collect once, at the very end.
    # game_type, away_team, home_team and top_10 stay in the data for
    # filtering and counting, but the table doesn't display them.
    return lf.select(
        [
            "week",
            "game_type",
            "away_team",
            "home_team",
            "matchup",
            "result",
            "top_10",
            "date_display",
            "weekday",
            "time_display",
            "stadium",
        ]
    ).collect()


# ─────────────────────────────────────────────────────────────────────────────
# Function 2: render the page (cheap, re-runs when a filter changes)
# ─────────────────────────────────────────────────────────────────────────────


def _style_cell(_row_id, column_name, value):
    # column_name is the NEW name ("Matchup") because we rename before display
    if column_name == "Matchup" and value.startswith("★"):
        return {"backgroundColor": "rgba(255, 193, 7, 0.4)", "fontWeight": "bold"}
    return {}


def render(schedule_df, season, week_num=None, team_abbr=None):
    """Filter the schedule and return the finished page.

    week_num  -- an int like 3, or None for all weeks
    team_abbr -- an abbreviation like "PHI", or None for all teams
    """
    filtered = schedule_df

    if week_num is not None:
        filtered = filtered.filter(pl.col("week") == week_num)

    if team_abbr is not None:
        filtered = filtered.filter(
            (pl.col("away_team") == team_abbr) | (pl.col("home_team") == team_abbr)
        )

    top_10_games = int(filtered["matchup"].str.starts_with("★").sum())

    # Pick the columns, then rename them for display
    table_df = filtered.select(list(_COLUMN_NAMES.keys())).rename(_COLUMN_NAMES)

    return mo.vstack(
        [
            mo.md(f"### {season} Season Schedule"),
            mo.md("Game times shown in Eastern Time."),
            mo.md(f"**{len(filtered)} games** · ★ {top_10_games} top-10 matchups"),
            mo.md("---"),
            mo.ui.table(
                table_df.to_dicts(),  # drop .to_dicts() if the normal viewer works for you
                pagination=True,
                show_column_summaries=False,
                show_data_types=False,
                selection=None,
                style_cell=_style_cell,
            ),
        ]
    )
