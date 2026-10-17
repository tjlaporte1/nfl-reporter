"""My Team page: a radar chart of one team's weekly grades.

Five functions are meant to be called from dashboard.py:

    build_data(team_weekly_lf)
        Collects the graded weeks into a DataFrame. Call this ONCE.

    make_view_selector()
    make_season_selector(graded_df)
    make_week_slider(graded_df, season)
        Create this page's three widgets. Call each in a cell of its own, so
        a widget is created once and keeps its state while other things change.
        (The week slider is created from the chosen season, so it is rebuilt,
        and jumps to that season's latest week, when the season changes.)

    render(graded_df, team_abbr, season_selector, week_slider, view_selector)
        Filters to one team, season and week and returns the finished page.
        Cheap, so it can re-run every time a widget or the team changes.

Everything this file needs is passed in as an argument. A separate .py file
cannot see variables defined in dashboard.py, so the dashboard hands them over.
"""

import marimo as mo
import plotly.graph_objects as go
from polars import col as c

# ─────────────────────────────────────────────────────────────────────────────
# Radar chart settings
# ─────────────────────────────────────────────────────────────────────────────

# Detailed view: label on chart -> rank column (spokes go clockwise from just
# right of the top)
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
# Background wedges in the same clockwise order:
# (name, color, number of spokes it covers)
DETAILED_UNITS = [
    ("Offense", "rgba(44,160,44,0.07)", 3),
    ("Special teams", "rgba(31,119,180,0.07)", 2),  # FG value, punting
    ("Strength of schedule", "rgba(128,128,128,0.10)", 1),  # SOS
    ("Defense", "rgba(214,39,40,0.07)", 3),
]

# Overview view: the four high-level ranks, one per quadrant
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

# Toggle label -> (axes, wedges). Wedge counts must add up to the number of axes.
VIEWS = {
    "Overview": (OVERVIEW_AXES, OVERVIEW_UNITS),
    "Detailed": (DETAILED_AXES, DETAILED_UNITS),
}

# Options for the rank-over-time chart: which other teams to draw
COMPARE_SCOPES = ["Team only", "Division", "Conference"]

# ─────────────────────────────────────────────────────────────────────────────
# Chart builders
# ─────────────────────────────────────────────────────────────────────────────


def _build_rank_line(season_df, team_abbr, scope, through_week):
    """Line chart of overall rank by week, drawn up to `through_week`.

    season_df    -- graded rows for ONE season (all teams)
    team_abbr    -- the selected team, e.g. "PHI"
    scope        -- one of COMPARE_SCOPES
    through_week -- last week to draw (from the week slider)
    """
    last_week = season_df["week"].max()  # latest graded week, used to fix the x axis
    visible = season_df.filter(c.week <= through_week)  # only the weeks to draw

    me = visible.filter(c.team == team_abbr).sort("week")
    first = me.row(0, named=True)

    # Decide which teams to draw. Every row carries team_division and team_conf,
    # so a filter on the selected team's value finds its division or conference.
    if scope == "Division":
        shown = visible.filter(c.team_division == first["team_division"])
    elif scope == "Conference":
        shown = visible.filter(c.team_conf == first["team_conf"])
    else:
        shown = me

    others = shown.filter(c.team != team_abbr)
    hover = "%{fullData.name}, Week %{x}: #%{y}<extra></extra>"
    ranks = me["rank"].to_list()

    fig = go.Figure()

    # 1) Other teams first, so the selected team is drawn on top of them.
    # partition_by("team") splits the table into a list of small tables,
    # one per team, which is what we need to draw one line per team.
    for group in others.sort("week").partition_by("team", maintain_order=True):
        row = group.row(0, named=True)
        fig.add_trace(
            go.Scatter(
                x=group["week"].to_list(),
                y=group["rank"].to_list(),
                mode="lines",
                name=row["team"],
                line={"color": row["team_color"], "width": 1.5},
                opacity=0.5,
                hovertemplate=hover,
            )
        )

    # 2) The selected team last: thicker, solid, with dots
    fig.add_trace(
        go.Scatter(
            x=me["week"].to_list(),
            y=ranks,
            mode="lines+markers+text",  # "+text" turns the labels on
            text=[f"#{r}" for r in ranks],  # "#3", "#7", ... same order as x and y
            textposition="top center",
            textfont={"size": 12, "color": first["team_color"]},
            cliponaxis=False,  # let a label near the plot edge draw outside the axes
            name=team_abbr,
            line={"color": first["team_color"], "width": 4},
            marker={"size": 8},
            hovertemplate=hover,
        )
    )

    fig.update_layout(
        title=f"Overall rank by week: {first['team_name']}",
        height=450,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=scope != "Team only",
        xaxis={
            "title": "Week",
            "dtick": 1,
            "range": [0.5, last_week + 0.5],
            "showgrid": True,
            "gridcolor": "rgba(0,0,0,0.08)",  # very light gray
            "ticks": "outside",  # small hash marks on the axis
        },
        yaxis={
            "title": "Overall rank",
            "range": [32.5, 0.5],
            "tickmode": "array",
            "tickvals": [1, 4, 8, 12, 16, 20, 24, 28, 32],
            "showgrid": True,
            "gridcolor": "rgba(0,0,0,0.08)",
            "ticks": "outside",
        },
    )
    return fig


def _build_radar(row, axes, units):
    """row = one team's graded row for one week (a dict); axes/units = one entry of VIEWS."""
    step = 360 / len(axes)  # degrees per spoke
    # half-step offset keeps spokes off the top/bottom lines
    angles = [(i + 0.5) * step for i in range(len(axes))]
    ranks = [row[col] for col in axes.values()]  # can contain None if a stat is missing
    color = row["team_color"]

    fig = go.Figure()

    # 1) background wedges: centre -> arc along the outer edge -> back to centre
    first, seen = 0, set()
    for name, wedge_color, n in units:
        start, end = (
            first * step,
            (first + n) * step,
        )  # edges sit halfway between spokes
        arc = [(start + i * (end - start) / 20) % 360 for i in range(21)]
        fig.add_trace(
            go.Scatterpolar(
                r=[32] + [1] * 21 + [32],
                theta=[arc[0]] + arc + [arc[-1]],
                mode="lines",
                fill="toself",
                fillcolor=wedge_color,
                line={"width": 0},
                name=name,
                hoverinfo="skip",
            )
        )
        seen.add(name)
        first += n

    # 2) the team's shape: see-through fill + outline (first point repeated to close it)
    fig.add_trace(
        go.Scatterpolar(
            r=ranks + ranks[:1],
            theta=angles + angles[:1],
            mode="lines",
            fill="toself",
            connectgaps=True,
            opacity=0.7,
            showlegend=False,
            line={"color": color, "width": 2},
            fillcolor=color,
            hoverinfo="skip",
        )
    )

    # 3) the rank dots: a separate trace so they stay fully solid
    fig.add_trace(
        go.Scatterpolar(
            r=ranks,
            theta=angles,
            text=list(axes),
            mode="markers",
            showlegend=False,
            marker={"size": 14, "color": color, "line": {"color": "white", "width": 3}},
            hovertemplate="%{text}: #%{r}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"{row['team_name']}: Week {row['week']}",
        showlegend=False,
        polar={
            # reversed: rank 1 on the outer edge; hide the rank numbers and axis line
            "radialaxis": {
                "range": [32, 1],
                "showticklabels": False,
                "showline": False,
            },
            "angularaxis": {
                "rotation": 90,
                "direction": "clockwise",
                "tickmode": "array",
                "tickvals": angles,
                "ticktext": list(axes),
            },
        },
        height=600,
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Function 1: the page's own widget (call in its own cell)
# ─────────────────────────────────────────────────────────────────────────────


def make_view_selector():
    """The Overview / Detailed toggle that belongs to this page."""
    return mo.ui.radio(
        options=list(VIEWS.keys()),
        value="Overview",
        inline=True,
        label="View",
    )


def make_season_selector(graded_df):
    """The season dropdown that belongs to this page.

    Lists every season that has graded weeks and starts on the latest one.
    The dictionary maps the label shown ("2026") to the value we get back (2026).
    """
    seasons = sorted(graded_df["season"].unique().to_list())
    options = {str(s): s for s in seasons} or {"No data": None}
    return mo.ui.dropdown(
        options=options,
        value=list(options.keys())[-1],  # the latest season
        label="Season",
    )


def make_week_slider(graded_df, season):
    """The week slider that belongs to this page.

    It runs from week 1 to the latest graded week of the season, and starts
    on that latest week.
    """
    latest = None
    if season is not None:
        latest = graded_df.filter(c.season == season).select(c.week.max()).item()
    latest = int(latest) if latest is not None else 1
    return mo.ui.slider(
        start=1,
        stop=max(latest, 2),  # a slider needs room to move
        value=min(latest, max(latest, 2)),
        label="Week",
        show_value=True,
    )


def make_compare_selector():
    """The 'Compare with' toggle for the rank-over-time chart."""
    return mo.ui.radio(
        options=COMPARE_SCOPES,
        value="Team only",
        inline=False,
        label="Compare with",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Function 2: build the data (call once)
# ─────────────────────────────────────────────────────────────────────────────


def build_data(team_weekly_lf):
    """Return a DataFrame of every graded team-week.

    team_weekly_lf also has rows for unplayed future games, and those have
    empty ranks, so we keep only rows that have been graded.
    """
    return team_weekly_lf.filter(c.offense_rank.is_not_null()).collect()


# ─────────────────────────────────────────────────────────────────────────────
# Function 3: render the page (cheap, re-runs when a filter changes)
# ─────────────────────────────────────────────────────────────────────────────


def render(
    graded_df, team_abbr, season_selector, week_slider, view_selector, compare_selector
):
    """Return the finished page.

    team_abbr       -- an abbreviation like "PHI", or None (no team picked yet)
    season_selector -- the dropdown created by make_season_selector()
    week_slider     -- the slider created by make_week_slider()
    view_selector   -- the toggle created by make_view_selector()
    compare_selector -- the toggle created by make_compare_selector()
    """
    season = season_selector.value  # e.g. 2026

    if team_abbr is None:
        return mo.md("_Pick a team in the sidebar filters to see its report card._")

    if season is None:
        return mo.md("_No graded weeks yet._")

    team_df = graded_df.filter((c.season == season) & (c.team == team_abbr)).sort(
        "week"
    )

    if team_df.is_empty():
        return mo.md(f"_No graded weeks for {team_abbr} in {season}._")

    weeks = team_df["week"].to_list()  # graded weeks this team played
    # closest graded week at or before the slider (handles bye weeks)
    week = max((w for w in weeks if w <= week_slider.value), default=weeks[0])

    selected_row = team_df.filter(c.week == week).row(0, named=True)
    axes, units = VIEWS[view_selector.value]

    season_df = graded_df.filter(c.season == season)

    return mo.vstack(
        [
            mo.md(f"**My Team - {season} Season**"),
            mo.vstack([season_selector, compare_selector], align="start", gap=1),
            _build_rank_line(season_df, team_abbr, compare_selector.value, week),
            mo.vstack([week_slider, view_selector], align="start", gap=1),
            _build_radar(selected_row, axes, units),
        ]
    )
