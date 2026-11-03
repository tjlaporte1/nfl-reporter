"""Matchups section (shown under the schedule).

Three functions are called from dashboard.py:

    make_game_selector(schedule_df, week_num, team_abbr)
        Dropdown of games, narrowed by the sidebar Week / Team filters.
        Rebuilt whenever a filter changes (so it resets to the first game).

    render(graded_df, season, game_selector, view_selector)
        Draws the overlay radar (left) and the rank table with bars (right).

The Overview/Detailed toggle is created in dashboard.py with
nflr_my_team.make_view_selector(), so it keeps its state between games.
"""

from itertools import groupby

import marimo as mo
import plotly.graph_objects as go
from polars import col as c

import nflr_my_team  # reuse VIEWS (the radar axes and background wedges)

NUM_TEAMS = 32
SUB_BAR_SCALE = 0.75  # sub-grade bars max out at 75% of the length of main-grade bars

# Table rows: (label, rank column, level, counts toward "who wins"?, group)
# level: 0 = main grade, 1 = sub-grade. group: which panel the row sits in
# (None = no panel). Rows of the same group must be next to each other.
TABLE_ROWS = [
    ("Overall", "rank", 0, True, None),
    ("Offense", "offense_rank", 0, True, "Offense"),
    ("Passing", "passing_rank", 1, True, "Offense"),
    ("Rushing", "rushing_rank", 1, True, "Offense"),
    ("TDs", "td_rank", 1, True, "Offense"),
    ("Defense", "defense_rank", 0, True, "Defense"),
    ("Pass defense", "pass_defense_rank", 1, True, "Defense"),
    ("Rush defense", "rush_defense_rank", 1, True, "Defense"),
    ("Disruption", "disruption_rank", 1, True, "Defense"),
    ("Special teams", "special_teams_rank", 0, True, "Special teams"),
    ("FG value", "fg_rank", 1, True, "Special teams"),
    ("Punting", "punting_rank", 1, True, "Special teams"),
    ("SOS*", "sos_rank", 0, False, "Strength of schedule"),
]

# Same colors as the radar's background wedges (as "r,g,b" for CSS rgba())
GROUP_RGB = {
    "Offense": "44,160,44",
    "Defense": "214,39,40",
    "Special teams": "31,119,180",
    "Strength of schedule": "128,128,128",
}

# Panel backgrounds: the radar's own wedge colors, so the two always match.
# DETAILED_UNITS is a list of (name, color, spoke_count); we keep name -> color.
GROUP_BG = {name: color for name, color, _ in nflr_my_team.DETAILED_UNITS}

# ─────────────────────────────────────────────────────────────────────────────
# Widget: the game dropdown
# ─────────────────────────────────────────────────────────────────────────────


def make_game_selector(schedule_df, week_num=None, team_abbr=None):
    """Dropdown of games. Applies the same filters the schedule table uses."""
    games = schedule_df

    if week_num is not None:
        games = games.filter(c.week == week_num)

    if team_abbr is not None:
        games = games.filter((c.away_team == team_abbr) | (c.home_team == team_abbr))

    # label shown in the dropdown -> value we get back: (week, away, home)
    # schedule_df is already sorted by week/date/time, so this order is chronological.
    options = {}
    for row in games.select("week", "away_team", "home_team").iter_rows(named=True):
        label = f"Week {row['week']}: {row['away_team']} @ {row['home_team']}"
        options[label] = (int(row["week"]), row["away_team"], row["home_team"])

    if not options:
        options = {"No games": None}

    return mo.ui.dropdown(
        options=options,
        value=list(options.keys())[0],  # start on the first game in the list
        label="Game",
        searchable=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _going_in_row(graded_df, season, team, game_week):
    """The team's latest graded row from BEFORE game_week, or None.

    Taking "the latest earlier week" (not "week - 1") handles bye weeks.
    """
    earlier = graded_df.filter(
        (c.season == season) & (c.team == team) & (c.week < game_week)
    ).sort("week")

    if earlier.is_empty():
        return None
    return earlier.tail(1).row(0, named=True)


def _pick_colors(away_row, home_row):
    """Team colors, with a fallback if both teams share the same primary color."""
    away = away_row["team_color"] or "#1f77b4"
    home = home_row["team_color"] or "#d62728"
    if home.lower() == away.lower():
        home = home_row["team_color2"] or "#555555"
    return away, home


def _edge(away_rank, home_rank):
    """Return "away", "home" or None. A smaller rank number is better."""
    if away_rank is None or home_rank is None or away_rank == home_rank:
        return None
    return "away" if away_rank < home_rank else "home"


# ─────────────────────────────────────────────────────────────────────────────
# Overlay radar
# ─────────────────────────────────────────────────────────────────────────────


def _build_overlay_radar(away_row, home_row, axes, units, away_color, home_color):
    step = 360 / len(axes)
    angles = [(i + 0.5) * step for i in range(len(axes))]

    fig = go.Figure()

    # 1) Background wedges (same idea as the My Team radar)
    first = 0
    for name, wedge_color, n in units:
        start, end = first * step, (first + n) * step
        arc = [(start + i * (end - start) / 20) % 360 for i in range(21)]
        fig.add_trace(
            go.Scatterpolar(
                r=[32] + [1] * 21 + [32],
                theta=[arc[0]] + arc + [arc[-1]],
                mode="lines",
                fill="toself",
                fillcolor=wedge_color,
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
            )
        )
        first += n

    # 2) One team at a time: a soft fill, then an outline with dots
    for row, color, dash in [
        (away_row, away_color, "solid"),
        (home_row, home_color, "dash"),
    ]:
        ranks = [row[col] for col in axes.values()]

        fig.add_trace(  # fill only (no legend entry, no hover)
            go.Scatterpolar(
                r=ranks + ranks[:1],
                theta=angles + angles[:1],
                mode="lines",
                fill="toself",
                connectgaps=True,
                fillcolor=color,
                opacity=0.2,
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
            )
        )
        fig.add_trace(  # outline + dots (this one shows in the legend)
            go.Scatterpolar(
                r=ranks + ranks[:1],
                theta=angles + angles[:1],
                text=list(axes) + [list(axes)[0]],
                mode="lines+markers",
                connectgaps=True,
                name=row["team"],
                line={"color": color, "width": 3, "dash": dash},
                marker={"size": 9, "color": color, "line": {"color": "white", "width": 2}},
                hovertemplate=row["team"] + " %{text}: #%{r}<extra></extra>",
            )
        )

    fig.update_layout(
        showlegend=True,
        legend={"orientation": "h", "x": 0.5, "xanchor": "center", "y": -0.05},
        polar={
            "radialaxis": {"range": [32, 1], "showticklabels": False, "showline": False},
            "angularaxis": {
                "rotation": 90,
                "direction": "clockwise",
                "tickmode": "array",
                "tickvals": angles,
                "ticktext": list(axes),
            },
        },
        margin={"l": 60, "r": 60, "t": 30, "b": 40},
        height=600,
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Rank table with bars (plain HTML + CSS grid)
# ─────────────────────────────────────────────────────────────────────────────

# 5 columns: away rank | away bar | label | home bar | home rank
_GRID = "display:grid;grid-template-columns:40px 1fr 110px 1fr 40px;align-items:center;gap:6px;"


def _bar_html(rank, color, side, is_winner, counts, level):
    """One bar. Longer = better rank (#1 = full length). Sub-grades are thinner."""
    if rank is None:
        return "<div></div>"
    width = (NUM_TEAMS + 1 - rank) / NUM_TEAMS * 100
    height = 16 if level == 0 else 9  # thickness shows main vs sub-grade
    opacity = (1.0 if is_winner else 0.3) if counts else 0.6
    justify = "flex-end" if side == "away" else "flex-start"
    radius = "4px 0 0 4px" if side == "away" else "0 4px 4px 0"
    return (
        f'<div style="display:flex;justify-content:{justify};">'
        f'<div style="width:{width:.0f}%;height:{height}px;background:{color};'
        f'opacity:{opacity};border-radius:{radius};"></div></div>'
    )


def _rank_text(rank, is_winner, side, level):
    """The rank number at either end of a row. Sub-grades are slightly smaller."""
    text = "–" if rank is None else f"#{rank}"
    weight = 700 if is_winner else 400
    size = "1em" if level == 0 else "0.9em"
    align = "left" if side == "away" else "right"
    return (
        f'<div style="text-align:{align};font-weight:{weight};'
        f'font-size:{size};">{text}</div>'
    )


def _row_html(away_row, home_row, away_color, home_color, label, col, level, counts):
    """One table row. Returns (html, edge) so the caller can tally the wins."""
    a, h = away_row[col], home_row[col]
    edge = _edge(a, h) if counts else None
    weight = 600 if level == 0 else 400
    size = "1em" if level == 0 else "0.9em"

    html = (
        f'<div style="{_GRID}padding:2px 0;">'
        + _rank_text(a, edge == "away", "away", level)
        + _bar_html(a, away_color, "away", edge == "away", counts, level)
        + f'<div style="text-align:center;white-space:nowrap;'
        f'font-weight:{weight};font-size:{size};">{label}</div>'
        + _bar_html(h, home_color, "home", edge == "home", counts, level)
        + _rank_text(h, edge == "home", "home", level)
        + "</div>"
    )
    return html, edge

def _header_cell(row, color, side):
    """Team logo stacked above the team abbreviation, for the table header."""
    logo = row["team_logo_espn"]  # may be None
    img = (
        f'<img src="{logo}" alt="" '
        'style="height:30px;width:30px;object-fit:contain;">'
        if logo
        else ""  # no logo: just show the name
    )
    # away sits at the right end of its column (next to the label), home at the left
    align = "flex-end" if side == "away" else "flex-start"
    return (
        f'<div style="display:flex;flex-direction:column;align-items:{align};'
        f'gap:2px;color:{color};">{img}<span>{row["team"]}</span></div>'
    )

def _build_table(away_row, home_row, away_color, home_color):
    away, home = away_row["team"], home_row["team"]

    # Panels have a 4px left border + 6px left padding (and 8px right padding).
    # Rows outside a panel get the same inset so every column lines up.
    outside_pad = "padding:0 8px;"

    header = (
        f'<div style="{outside_pad}{_GRID}font-weight:700;margin-bottom:6px;">'
        f'<div></div>{_header_cell(away_row, away_color, "away")}'
        f'<div style="text-align:center;font-weight:400;opacity:0.6;">rank going in</div>'
        f'{_header_cell(home_row, home_color, "home")}<div></div></div>'
    )

    body = []
    away_wins = home_wins = 0

    # groupby walks the list and bundles CONSECUTIVE rows with the same group
    # (index 4 of each tuple). That's why same-group rows must sit together.
    for group, rows in groupby(TABLE_ROWS, key=lambda r: r[4]):
        row_html = []
        for label, col, level, counts, _group in rows:
            html, edge = _row_html(
                away_row, home_row, away_color, home_color, label, col, level, counts
            )
            away_wins += edge == "away"  # True counts as 1
            home_wins += edge == "home"
            row_html.append(html)

        if group is None:
            # no panel: just the rows, inset to line up with the panels
            body.append(f'<div style="{outside_pad}">{"".join(row_html)}</div>')
        else:
            body.append(
                f'<div style="background:{GROUP_BG[group]};border-radius:6px;'
                f'padding:6px 8px;margin:8px 0;">{"".join(row_html)}</div>'
            )

    footnote = (
        '<div style="font-size:12px;opacity:0.6;margin-top:6px;">'
        "*SOS: #1 = toughest schedule (not counted in the tally)</div>"
    )

    html = f'<div style="width:100%;">{header}{"".join(body)}{footnote}</div>'
    return mo.Html(html), away_wins, home_wins


# ─────────────────────────────────────────────────────────────────────────────
# Render
# ─────────────────────────────────────────────────────────────────────────────


def render(graded_df, season, game_selector, view_selector):
    """Return the whole Matchups section."""
    controls = mo.hstack([game_selector, view_selector], justify="start", gap=2)
    header = mo.md("### Matchups")
    game = game_selector.value

    if game is None:
        return mo.vstack([header, controls, mo.md("_No games match the filters._")])

    week, away, home = game
    away_row = _going_in_row(graded_df, season, away, week)
    home_row = _going_in_row(graded_df, season, home, week)

    if away_row is None or home_row is None:
        return mo.vstack(
            [
                header,
                controls,
                mo.md(
                    f"_No graded ranks before Week {week} yet, so there is nothing "
                    "to compare. (Week 1 games have no 'going in' ranks.)_"
                ),
            ]
        )

    away_color, home_color = _pick_colors(away_row, home_row)
    axes, units = nflr_my_team.VIEWS[view_selector.value]

    radar = _build_overlay_radar(away_row, home_row, axes, units, away_color, home_color)
    table, away_wins, home_wins = _build_table(away_row, home_row, away_color, home_color)

    summary = mo.md(
        f"**{away} @ {home}, Week {week}** · ranks through Week "
        f"{away_row['week']} ({away}) / {home_row['week']} ({home}) · "
        f"{away} leads {away_wins} categories, {home} leads {home_wins} "
        "(SOS not counted)"
    )

    return mo.vstack([header, controls, summary, radar, table])