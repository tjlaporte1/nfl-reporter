"""Power Rankings page: every team ranked for one week, with change from last week.

Four functions are meant to be called from dashboard.py:

    build_data(graded_df)
        Gives every team a row in every graded week (bye teams carry their last
        grades forward), re-ranks all 32 teams, and adds a "change from last
        week" column for every rank column. Call this ONCE.

    make_season_selector(power_df)
    make_week_selector(power_df, season)
    make_group_selector()
        Create this page's widgets. Call each in a cell of its own so a widget
        keeps its state while other things change. The week selector is built
        from the chosen season, so it is rebuilt when the season changes.

    render(power_df, season_selector, week_selector, group_selector)
        Filters to one season and week and returns the finished page.
        Cheap, so it can re-run every time a widget changes.
"""

import marimo as mo
import polars as pl
from polars import col as c

# ─────────────────────────────────────────────────────────────────────────────
# Table settings
# ─────────────────────────────────────────────────────────────────────────────

# Table name -> list of (label shown, rank column in the data).
# The FIRST entry is the table's headline rank: the table is sorted by it.
GROUPS = {
    "Overall": [
        ("Overall", "rank"),
        ("Offense", "offense_rank"),
        ("Defense", "defense_rank"),
        ("Special teams", "special_teams_rank"),
        ("SOS", "sos_rank"),
    ],
    "Offense": [
        ("Offense", "offense_rank"),
        ("Passing", "passing_rank"),
        ("Rushing", "rushing_rank"),
        ("TDs", "td_rank"),
    ],
    "Defense": [
        ("Defense", "defense_rank"),
        ("Pass defense", "pass_defense_rank"),
        ("Rush defense", "rush_defense_rank"),
        ("Disruption", "disruption_rank"),
    ],
    "Special teams": [
        ("Special teams", "special_teams_rank"),
        ("FG value", "fg_rank"),
        ("Punting", "punting_rank"),
    ],
}

# Every distinct rank column used above (a set removes duplicates like sos_rank)
_ALL_RANK_COLS = sorted({col for pairs in GROUPS.values() for _, col in pairs})

# The columns that identify one row
_KEY_COLS = ["season", "week", "team"]


def _chg_name(rank_col):
    """Name of the numeric change column for a rank column, e.g. "rank_chg"."""
    return f"{rank_col}_chg"


# ─────────────────────────────────────────────────────────────────────────────
# Function 1: build the data (call once)
# ─────────────────────────────────────────────────────────────────────────────


def build_data(graded_df):
    """Return graded_df plus one "<rank column>_chg" column per rank column.

    chg = last week's rank - this week's rank
    so a POSITIVE number means the team moved UP (rank 10 -> 7 gives +3).
    The first week of a season has no "last week", so its change is null.
    """
    return graded_df.with_columns(
        [
            (
                # Cast to Int64 first: Polars ranks are unsigned and cannot
                # go negative.
                c(col).cast(pl.Int64).shift(1).over("season", "team", order_by="week")
                - c(col).cast(pl.Int64)
            ).alias(_chg_name(col))
            for col in _ALL_RANK_COLS
        ]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Function 2: this page's widgets (each in its own cell)
# ─────────────────────────────────────────────────────────────────────────────


def make_season_selector(power_df):
    """Season dropdown. Lists every graded season and starts on the latest."""
    seasons = sorted(power_df["season"].unique().to_list())
    options = {str(s): s for s in seasons} or {"No data": None}
    return mo.ui.dropdown(
        options=options,
        value=list(options.keys())[-1],
        label="Season",
    )


def make_week_selector(power_df, season):
    """Week dropdown for one season. Lists graded weeks and starts on the latest."""
    weeks = []
    if season is not None:
        weeks = sorted(power_df.filter(c.season == season)["week"].unique().to_list())
    options = {f"Week {w}": w for w in weeks} or {"No data": None}
    return mo.ui.dropdown(
        options=options,
        value=list(options.keys())[-1],
        label="Week",
    )


def make_group_selector():
    """Which table to show: Overall, Offense, Defense or Special teams."""
    return mo.ui.radio(
        options=list(GROUPS.keys()),
        value="Overall",
        inline=True,
        label="Table",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for rendering
# ─────────────────────────────────────────────────────────────────────────────


def _change_text(rank_col):
    """Turn the numeric change into text: "▲ 3", "▼ 2", "–" (no change) or "".

    A null change (week 1, so no last week) fails every comparison below,
    so it falls through to otherwise() and shows blank.
    """
    chg = c(_chg_name(rank_col))
    return (
        pl.when(chg > 0)
        .then(pl.lit("▲ ") + chg.cast(pl.Utf8))
        .when(chg < 0)
        .then(pl.lit("▼ ") + chg.abs().cast(pl.Utf8))  # abs: show 2, not -2
        .when(chg == 0)
        .then(pl.lit("–"))
        .otherwise(pl.lit(""))
    )


def _make_style_cell(bye_teams):
    """Build the styling function. It is created inside render() so it can
    'remember' which teams are on bye this week (a closure)."""

    def style_cell(_row_id, column_name, value):
        # Italic team name for a team on bye
        if column_name == "Team" and value in bye_teams:
            return {"fontStyle": "italic"}
        # Green for risers, red for fallers, only in the change columns
        if "Δ" in column_name and isinstance(value, str):
            if value.startswith("▲"):
                return {"color": "#1a7f37", "fontWeight": "bold"}
            if value.startswith("▼"):
                return {"color": "#cf222e", "fontWeight": "bold"}
        return {}

    return style_cell


# ─────────────────────────────────────────────────────────────────────────────
# Function 3: render the page (cheap, re-runs when a widget changes)
# ─────────────────────────────────────────────────────────────────────────────


def render(power_df, season_selector, week_selector, group_selector):
    """Return the finished page."""
    season = season_selector.value
    week = week_selector.value

    if season is None or week is None:
        return mo.md("_No graded weeks yet._")

    pairs = GROUPS[group_selector.value]
    head_label, head_col = pairs[0]

    week_df = power_df.filter((c.season == season) & (c.week == week)).sort(head_col)

    if week_df.is_empty():
        return mo.md(f"_No graded teams for {season}, week {week}._")

    # Each (label, rank column) becomes TWO table columns: the rank itself,
    # and its change text. Column names must be unique, so the change column
    # is named "<label> Δ".
    def pair_exprs(label, col):
        return [c(col).alias(label), _change_text(col).alias(f"{label} Δ")]

    head = pair_exprs(head_label, head_col)
    rest = [e for label, col in pairs[1:] for e in pair_exprs(label, col)]

    table_df = week_df.select(
        c.team_name.alias("Team"),  # team first, on the left
        c.record.alias("Record"),
        *head,  # then the headline rank and its change
        *rest,  # then the other ranks
    )

    # Team names to italicize: rows where the team did not play this week
    bye_teams = set(week_df.filter(~c.played)["team_name"].to_list())

    return mo.vstack(
        [
            mo.md(f"### Power Rankings: {season}, Week {week}"),
            mo.hstack([season_selector, week_selector], justify="start", gap=2),
            group_selector,
            mo.md(
                f"Sorted by **{head_label}** rank. ▲ / ▼ = spots moved since last week. "
                "_Italic team = on bye (last grades carried forward)._"
            ),
            mo.ui.table(
                table_df.to_dicts(),
                pagination=False,
                show_column_summaries=False,
                show_data_types=False,
                selection=None,
                style_cell=_make_style_cell(bye_teams),
            ),
        ]
    )
