from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

from fetch_google_sheet_range import (
    ROSTER_RANGE,
    ROSTER_SHEET_ID,
    ROSTER_TAB_NAME,
    fetch_range_csv_text,
)
from scrape_foxsports_ufl_pbp import (
    AMBIGUITY_REPORT_HEADERS,
    DEFAULT_ROSTER,
    DEFAULT_TEMPLATE,
    csv_text,
    default_output_path,
    extract_rows,
    normalize_team_abbrev,
    short_name_from_full_name,
)

ENTRY_PLAYER_COLUMNS = ["qb", "skill_1", "skill_2", "skill_3", "skill_4", "skill_5"]
ENTRY_ROLE_COLUMNS = [f"{column}_role" for column in ENTRY_PLAYER_COLUMNS]
ENTRY_SLOT_LABELS = {
    "qb": "QB",
    "skill_1": "Skill 1",
    "skill_2": "Skill 2",
    "skill_3": "Skill 3",
    "skill_4": "Skill 4",
    "skill_5": "Skill 5",
}
ROLE_OPTIONS = ["", "route"]
HISTORICAL_PLAYER_DB = Path("historical_player_database.csv")
TEAM_MATCH_EQUIVALENTS = {
    "ARL": {"ARL", "DAL"},
    "DAL": {"DAL", "ARL"},
}


st.set_page_config(page_title="UFL Fox Sports PBP Exporter", page_icon="football", layout="wide")


def app_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(158, 201, 88, 0.14), transparent 26%),
                radial-gradient(circle at top left, rgba(233, 96, 83, 0.10), transparent 24%),
                linear-gradient(180deg, #0d1117 0%, #111722 45%, #151d2b 100%);
            color: #e8edf5;
        }
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .hero {
            padding: 1.2rem 1.4rem;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 18px;
            background: rgba(20, 27, 39, 0.86);
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
            margin-bottom: 1rem;
        }
        .hero h1 {
            font-size: 2rem;
            margin: 0 0 0.3rem 0;
            color: #f7f9fc;
        }
        .hero p {
            margin: 0;
            color: #b4c0d1;
            font-size: 1rem;
        }
        [data-testid="stSidebar"] {
            background: #11161f;
        }
        [data-testid="stSidebar"] * {
            color: #f4f2ed !important;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] .stSubheader,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {
            color: #f4f2ed !important;
        }
        [data-testid="stSidebar"] .note-card {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: #fffaf2 !important;
        }
        h1, h2, h3, h4, h5, h6,
        p, li, label, span, div {
            color: inherit;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stCaptionContainer"] p,
        [data-testid="stTextInputRootElement"] + div,
        [data-baseweb="select"] *,
        .stTextInput label p,
        .stSelectbox label p,
        .stSubheader,
        .stAlert,
        .stException,
        [data-testid="stMetricLabel"] p {
            color: #d5deea !important;
        }
        [data-testid="stMetric"] {
            background: rgba(20, 27, 39, 0.72);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 0.9rem 1rem;
        }
        [data-testid="stMetricValue"] {
            color: #f7f9fc !important;
        }
        [data-testid="stMetricLabel"] {
            color: #a9b8cb !important;
        }
        [data-testid="stTextInputRootElement"],
        [data-baseweb="select"] > div,
        [data-baseweb="select"] input,
        [data-baseweb="select"] {
            color: #f4f7fb !important;
        }
        [data-testid="stTextInputRootElement"] > div,
        [data-baseweb="select"] > div {
            background: rgba(11, 16, 24, 0.84) !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 12px !important;
        }
        [data-testid="stTextInputRootElement"] input {
            color: #f8f8f6;
        }
        [data-testid="stTextInputRootElement"] label,
        [data-testid="stTextInputRootElement"] p,
        .stSelectbox label,
        .stSelectbox p {
            color: #d5deea !important;
        }
        [data-testid="stDownloadButton"] button {
            border-radius: 14px;
            background: #1c2433 !important;
            color: #fffaf2 !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            font-weight: 600;
        }
        [data-testid="stDownloadButton"] button p,
        [data-testid="stDownloadButton"] button span,
        [data-testid="stDownloadButton"] button div {
            color: #fffaf2 !important;
        }
        [data-testid="stDownloadButton"] button:hover {
            background: #283246 !important;
            color: #ffffff !important;
        }
        .stButton button {
            border-radius: 14px;
            background: #dd5b52 !important;
            color: #fff9f7 !important;
            border: 0 !important;
            font-weight: 600;
        }
        .stButton button:hover {
            background: #ea6d63 !important;
        }
        .stDataFrame,
        [data-testid="stDataFrame"] {
            background: rgba(18, 24, 34, 0.82);
            border-radius: 16px;
        }
        [data-testid="stDataFrame"] div {
            color: #e8edf5 !important;
        }
        [data-baseweb="tab-list"] {
            gap: 0.35rem;
        }
        button[data-baseweb="tab"] {
            background: rgba(20, 27, 39, 0.76) !important;
            border-radius: 12px !important;
            color: #bfd0e5 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: rgba(221, 91, 82, 0.18) !important;
            color: #fff4f1 !important;
            border-color: rgba(221, 91, 82, 0.55) !important;
        }
        [data-testid="stAlert"] {
            background: rgba(20, 27, 39, 0.8) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            color: #e8edf5 !important;
        }
        .note-card {
            padding: 0.9rem 1rem;
            border-radius: 14px;
            background: rgba(20, 27, 39, 0.72);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #e8edf5 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def validate_inputs() -> list[str]:
    issues: list[str] = []
    if not DEFAULT_TEMPLATE.exists():
        issues.append(f"Missing template file: {DEFAULT_TEMPLATE}")
    return issues


def google_service_account_info() -> dict[str, str] | None:
    if "google_service_account" in st.secrets:
        return dict(st.secrets["google_service_account"])
    required_keys = {
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
    }
    if required_keys.issubset(set(st.secrets.keys())):
        return {key: st.secrets[key] for key in required_keys}
    if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    return None


def write_temp_roster(credentials_info: dict[str, str] | None) -> Path:
    roster_csv = fetch_range_csv_text(
        ROSTER_SHEET_ID,
        ROSTER_TAB_NAME,
        ROSTER_RANGE,
        credentials_info=credentials_info,
    )
    handle = tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", suffix=".csv", delete=False)
    with handle:
        handle.write(roster_csv)
    return Path(handle.name)


def int_value(value: str) -> int:
    if value in ("", "#N/A", None):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def aggregate_player_stats(rows: list[dict[str, str]]) -> tuple[list[dict[str, int | str]], list[dict[str, int | str]], list[dict[str, int | str]]]:
    passing: dict[str, dict[str, int | str]] = {}
    rushing: dict[str, dict[str, int | str]] = {}
    receiving: dict[str, dict[str, int | str]] = {}

    for row in rows:
        if row.get("play_number") == "0" or row.get("no_play") == "1":
            continue

        passer = row.get("passer_name") or row.get("passer")
        if passer and row.get("pass_play") == "1":
            passing.setdefault(
                passer,
                {"player": passer, "att": 0, "cmp": 0, "yds": 0, "td": 0, "int": 0, "sacks": 0},
            )
            if row.get("sack") == "1":
                passing[passer]["sacks"] += 1
            else:
                passing[passer]["att"] += 1
                if row.get("complete") == "1":
                    passing[passer]["cmp"] += 1
                passing[passer]["yds"] += int_value(row.get("passing_yards"))
                if row.get("passing_touchdown") == "1":
                    passing[passer]["td"] += 1
                if row.get("intercepted") == "1":
                    passing[passer]["int"] += 1

        rusher = row.get("runner_name") or row.get("rusher")
        if rusher and row.get("rush_attempt") == "1":
            rushing.setdefault(
                rusher,
                {"player": rusher, "att": 0, "yds": 0, "td": 0},
            )
            rushing[rusher]["att"] += 1
            rushing[rusher]["yds"] += int_value(row.get("rushing_yards"))
            if row.get("rushing_touchdown") == "1":
                rushing[rusher]["td"] += 1

        receiver = row.get("receiver_name") or row.get("receiver")
        if receiver and row.get("target") == "1":
            receiving.setdefault(
                receiver,
                {"player": receiver, "targets": 0, "rec": 0, "yds": 0, "td": 0},
            )
            receiving[receiver]["targets"] += 1
            if row.get("reception") == "1":
                receiving[receiver]["rec"] += 1
                receiving[receiver]["yds"] += int_value(row.get("passing_yards"))
                if row.get("passing_touchdown") == "1":
                    receiving[receiver]["td"] += 1

    passing_rows = sorted(passing.values(), key=lambda item: (-int(item["yds"]), str(item["player"])))
    rushing_rows = sorted(rushing.values(), key=lambda item: (-int(item["yds"]), str(item["player"])))
    receiving_rows = sorted(receiving.values(), key=lambda item: (-int(item["yds"]), str(item["player"])))
    return passing_rows, rushing_rows, receiving_rows


def player_label(name: str, team_abbrev: str) -> str:
    return f"{name} ({team_abbrev})" if team_abbrev else name


def team_match_options(team_abbrev: str) -> set[str]:
    normalized = normalize_team_abbrev(team_abbrev)
    if not normalized:
        return set()
    return TEAM_MATCH_EQUIVALENTS.get(normalized, {normalized})


def team_from_player_label(label: str) -> str:
    if not label or "(" not in label or not label.endswith(")"):
        return ""
    return normalize_team_abbrev(label.rsplit("(", 1)[1].rstrip(")").strip())


def name_from_player_label(label: str) -> str:
    if not label:
        return ""
    if " (" in label and label.endswith(")"):
        return label.rsplit(" (", 1)[0].strip()
    return label.strip()


def player_id_from_label(label: str) -> str:
    name = name_from_player_label(label)
    team = team_from_player_label(label)
    short_name = short_name_from_full_name(name)
    if short_name and team:
        return f"{short_name} {team}"
    return ""


def roster_player_records(roster_path: Path | None) -> set[tuple[str, str]]:
    records: set[tuple[str, str]] = set()
    if roster_path and roster_path.exists():
        with roster_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if len(row) >= 2 and row[0].strip():
                    records.add((row[0].strip(), normalize_team_abbrev(row[1].strip())))
    return records


def load_historical_player_records() -> set[tuple[str, str]]:
    records: set[tuple[str, str]] = set()
    if not HISTORICAL_PLAYER_DB.exists():
        return records

    with HISTORICAL_PLAYER_DB.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            name = (row.get("player_name") or "").strip()
            team = normalize_team_abbrev((row.get("team_abbrev") or "").strip())
            if not name:
                continue
            records.add((name, team))
    return records


def sync_player_dropdown_options(roster_path: Path | None) -> list[str]:
    historical_records = load_historical_player_records()
    current_records = roster_player_records(roster_path)
    merged_records = historical_records | current_records

    if merged_records and (merged_records != historical_records or not HISTORICAL_PLAYER_DB.exists()):
        with HISTORICAL_PLAYER_DB.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["player_name", "team_abbrev", "player_label"])
            for player_name, team_abbrev in sorted(merged_records):
                writer.writerow([player_name, team_abbrev, player_label(player_name, team_abbrev)])

    return [""] + [player_label(player_name, team_abbrev) for player_name, team_abbrev in sorted(merged_records)]


def play_clock_label(row: dict[str, str]) -> str:
    quarter = row.get("quarter", "")
    minutes = row.get("minutes", "")
    seconds = row.get("seconds", "")
    if minutes != "" and seconds != "":
        return f"Q{quarter} {int_value(minutes):02d}:{int_value(seconds):02d}"
    return f"Q{quarter}" if quarter else ""


def build_on_field_entries(rows: list[dict[str, str]]) -> pd.DataFrame:
    entry_rows: list[dict[str, str]] = []
    for row in rows:
        if row.get("play_number") == "0":
            continue
        description = row.get("play_description", "")
        if description.startswith("End Quarter") or description == "End Game":
            continue

        entry_row = {
            "play_number": row.get("play_number", ""),
            "quarter": row.get("quarter", ""),
            "minutes": row.get("minutes", ""),
            "seconds": row.get("seconds", ""),
            "clock": play_clock_label(row),
            "offense": row.get("offense", ""),
            "defense": row.get("defense", ""),
            "no_play": row.get("no_play", ""),
            "run_play": row.get("run_play", ""),
            "pass_play": row.get("pass_play", ""),
            "play_description": description,
        }
        for column in ENTRY_PLAYER_COLUMNS:
            entry_row[column] = ""
        for column in ENTRY_ROLE_COLUMNS:
            entry_row[column] = ""
        entry_rows.append(entry_row)

    return pd.DataFrame(entry_rows)


def apply_previous_play_defaults(entry_df: pd.DataFrame) -> pd.DataFrame:
    if entry_df.empty:
        return entry_df

    updated_df = entry_df.copy()
    for idx in range(1, len(updated_df)):
        previous_offense = str(updated_df.at[idx - 1, "offense"]).strip()
        current_offense = str(updated_df.at[idx, "offense"]).strip()
        if previous_offense != current_offense:
            continue
        is_scrimmage_play = str(updated_df.at[idx, "run_play"]).strip() == "1" or str(updated_df.at[idx, "pass_play"]).strip() == "1"
        if not is_scrimmage_play:
            continue
        for column in ENTRY_PLAYER_COLUMNS:
            current_value = str(updated_df.at[idx, column]).strip()
            if current_value:
                continue
            previous_value = str(updated_df.at[idx - 1, column]).strip()
            if previous_value:
                updated_df.at[idx, column] = previous_value
    return updated_df


def ensure_on_field_state(game_key: str, rows: list[dict[str, str]]) -> tuple[str, str, pd.DataFrame]:
    data_key = f"on_field_entries::{game_key}"
    index_key = f"on_field_index::{game_key}"
    built_key = f"on_field_built::{game_key}"
    built_df = build_on_field_entries(rows)

    if built_key not in st.session_state or st.session_state[built_key] != f"{game_key}:{len(built_df)}":
        st.session_state[data_key] = built_df
        st.session_state[index_key] = 0
        st.session_state[built_key] = f"{game_key}:{len(built_df)}"

    st.session_state[data_key] = apply_previous_play_defaults(st.session_state[data_key])
    return data_key, index_key, st.session_state[data_key]


def player_option_index(player_options: list[str], current_value: str) -> int:
    try:
        return player_options.index(current_value)
    except ValueError:
        return 0


def clear_role_widget_state(game_key: str, play_number: str) -> None:
    for column in ENTRY_ROLE_COLUMNS:
        st.session_state.pop(f"{game_key}_{play_number}_{column}", None)


def render_on_field_entry_workflow(rows: list[dict[str, str]], output_name: Path, player_options: list[str]) -> None:
    st.subheader("On-Field Entries")
    st.caption("Step through each play and enter the QB plus five skill players. Download this as a separate CSV you can join back to the play-by-play export.")

    game_key = output_name.stem
    data_key, index_key, entry_df = ensure_on_field_state(game_key, rows)
    if entry_df.empty:
        st.info("No play rows are available for manual on-field entry.")
        return

    current_index = int(st.session_state.get(index_key, 0))
    current_index = max(0, min(current_index, len(entry_df) - 1))
    st.session_state[index_key] = current_index

    nav_cols = st.columns([1, 3, 1])
    with nav_cols[0]:
        if st.button("Previous Play", use_container_width=True, disabled=current_index == 0, key=f"prev_play_{game_key}"):
            next_index = max(current_index - 1, 0)
            next_play_number = str(entry_df.iloc[next_index]["play_number"])
            clear_role_widget_state(game_key, next_play_number)
            st.session_state[index_key] = next_index
            st.rerun()
    with nav_cols[1]:
        selected_index = st.selectbox(
            "Jump to play",
            options=list(range(len(entry_df))),
            index=current_index,
            format_func=lambda idx: f"Play {entry_df.iloc[idx]['play_number']} | {entry_df.iloc[idx]['clock']} | {entry_df.iloc[idx]['offense']} | {entry_df.iloc[idx]['play_description'][:90]}",
        )
        if selected_index != current_index:
            selected_play_number = str(entry_df.iloc[selected_index]["play_number"])
            clear_role_widget_state(game_key, selected_play_number)
            st.session_state[index_key] = selected_index
            st.rerun()
    with nav_cols[2]:
        if st.button(
            "Next Play",
            use_container_width=True,
            disabled=current_index >= len(entry_df) - 1,
            key=f"next_play_{game_key}",
        ):
            next_index = min(current_index + 1, len(entry_df) - 1)
            next_play_number = str(entry_df.iloc[next_index]["play_number"])
            clear_role_widget_state(game_key, next_play_number)
            st.session_state[index_key] = next_index
            st.rerun()

    current_row = st.session_state[data_key].iloc[current_index].to_dict()
    st.markdown(
        f"""
        <div class="note-card">
            <strong>Play {current_row["play_number"]}</strong><br>
            {current_row["clock"]} | {current_row["offense"]} vs {current_row["defense"]}<br>
            {current_row["play_description"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form(f"on_field_form_{game_key}_{current_row['play_number']}"):
        selections: dict[str, str] = {}
        role_selections: dict[str, str] = {}
        for slot in ENTRY_PLAYER_COLUMNS:
            slot_cols = st.columns([4, 1])
            selections[slot] = slot_cols[0].selectbox(
                ENTRY_SLOT_LABELS[slot],
                player_options,
                index=player_option_index(player_options, str(current_row[slot])),
                key=f"{game_key}_{current_row['play_number']}_{slot}",
            )
            role_field = f"{slot}_role"
            role_selections[slot] = slot_cols[1].selectbox(
                "Role",
                ROLE_OPTIONS,
                index=player_option_index(ROLE_OPTIONS, str(current_row.get(role_field, ""))),
                key=f"{game_key}_{current_row['play_number']}_{role_field}",
            )
        save_clicked = st.form_submit_button("Save Play Entry", use_container_width=True)

    if save_clicked:
        offense_team = normalize_team_abbrev(str(current_row.get("offense", "")).strip())
        allowed_teams = team_match_options(offense_team)
        invalid_entries: list[str] = []

        for slot in ENTRY_PLAYER_COLUMNS:
            selected_player = selections[slot].strip()
            if not selected_player:
                continue
            player_team = team_from_player_label(selected_player)
            if not player_team or player_team not in allowed_teams:
                invalid_entries.append(f"{ENTRY_SLOT_LABELS[slot]}: {selected_player}")

        if invalid_entries:
            st.error(
                "Could not save play entry. These players do not match the offense on the field "
                f"({offense_team}): " + "; ".join(invalid_entries)
            )
        else:
            updated_df = st.session_state[data_key].copy()
            for slot in ENTRY_PLAYER_COLUMNS:
                updated_df.at[current_index, slot] = selections[slot].strip()
                updated_df.at[current_index, f"{slot}_role"] = role_selections[slot].strip()
            st.session_state[data_key] = updated_df
            next_index = min(current_index + 1, len(entry_df) - 1)
            next_play_number = str(entry_df.iloc[next_index]["play_number"])
            clear_role_widget_state(game_key, next_play_number)
            st.session_state[index_key] = next_index
            st.rerun()

    completed_mask = st.session_state[data_key][ENTRY_PLAYER_COLUMNS].fillna("").apply(
        lambda row: any(str(value).strip() for value in row),
        axis=1,
    )
    completed_count = int(completed_mask.sum())
    entry_stats = st.columns(2)
    entry_stats[0].metric("Entry Rows", len(st.session_state[data_key]))
    entry_stats[1].metric("Completed Plays", completed_count)

    download_df = st.session_state[data_key].copy()
    for slot in ENTRY_PLAYER_COLUMNS:
        download_df[slot] = download_df[slot].apply(lambda value: player_id_from_label(str(value).strip()))

    entries_output = output_name.with_name(f"{output_name.stem}_on_field_entries.csv")
    st.download_button(
        "Download On-Field Entries CSV",
        data=download_df.to_csv(index=False),
        file_name=entries_output.name,
        mime="text/csv",
        use_container_width=True,
    )

    if completed_count:
        st.caption("Completed on-field rows so far.")
        st.dataframe(
            st.session_state[data_key].loc[completed_mask],
            use_container_width=True,
            hide_index=True,
        )


def resolve_roster_source(credentials_info: dict[str, str] | None) -> tuple[Path, str, str | None]:
    try:
        return write_temp_roster(credentials_info), "live_google_sheet", None
    except Exception as exc:  # noqa: BLE001
        if DEFAULT_ROSTER.exists():
            return DEFAULT_ROSTER, "bundled_fallback", str(exc)
        raise
    raise RuntimeError("No roster source is available. Check the public Google Sheet or add roster_info.csv.")


def main() -> None:
    app_css()

    st.markdown(
        """
        <div class="hero">
            <h1>UFL Fox Sports PBP Exporter</h1>
            <p>Paste a Fox Sports UFL game URL to generate a play-by-play CSV and an ambiguity report you can download immediately.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    issues = validate_inputs()
    if issues:
        for issue in issues:
            st.error(issue)
        st.stop()

    credentials_info = google_service_account_info()

    with st.sidebar:
        st.subheader("What You Get")
        st.markdown(
            """
            - Play-by-play CSV in the sample schema
            - Ambiguity report for short-name collisions
            - Missing-target warnings for thrown passes
            - Separate on-field entry CSV for QB plus five skill players
            - Live Google Sheets roster refresh on each run
            """
        )
        st.markdown('<div class="note-card">Built for Fox Sports UFL game pages with the play-by-play tab.</div>', unsafe_allow_html=True)

    default_url = "https://www.foxsports.com/ufl/week-1-birmingham-stallions-vs-louisville-kings-mar-27-2026-game-boxscore-87?tab=playbyplay"
    game_url = st.text_input("Fox Sports game URL", value=default_url, placeholder="https://www.foxsports.com/ufl/...")

    col1, col2 = st.columns([1, 3])
    with col1:
        run_clicked = st.button("Generate CSVs", type="primary", use_container_width=True)
    with col2:
        st.caption("Each run refreshes the roster from Google Sheets before building the CSVs.")

    if run_clicked:
        if not game_url.strip():
            st.error("Enter a Fox Sports game URL first.")
            return

        roster_path: Path | None = None
        roster_source = ""
        roster_warning: str | None = None
        player_options: list[str] = [""]
        try:
            with st.spinner("Scraping Fox Sports play-by-play and building exports..."):
                roster_path, roster_source, roster_warning = resolve_roster_source(credentials_info)
                headers, rows, ambiguity_rows = extract_rows(game_url.strip(), DEFAULT_TEMPLATE, roster_path)
                pbp_csv = csv_text(headers, rows)
                ambiguity_csv = csv_text(AMBIGUITY_REPORT_HEADERS, ambiguity_rows)
                player_options = sync_player_dropdown_options(roster_path)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not generate outputs: {exc}")
            return
        finally:
            if roster_source == "live_google_sheet" and roster_path and roster_path.exists():
                roster_path.unlink(missing_ok=True)

        output_name = default_output_path(game_url.strip())
        st.session_state["generated_game_result"] = {
            "game_url": game_url.strip(),
            "rows": rows,
            "ambiguity_rows": ambiguity_rows,
            "pbp_csv": pbp_csv,
            "ambiguity_csv": ambiguity_csv,
            "output_name": output_name.name,
            "ambiguity_name": f"{output_name.stem}_ambiguity_report.csv",
            "roster_source": roster_source,
            "roster_warning": roster_warning,
            "player_options": player_options,
        }

    result = st.session_state.get("generated_game_result")
    if not result:
        return

    rows = result["rows"]
    ambiguity_rows = result["ambiguity_rows"]
    pbp_csv = result["pbp_csv"]
    ambiguity_csv = result["ambiguity_csv"]
    output_name = Path(result["output_name"])
    ambiguity_name = Path(result["ambiguity_name"])
    roster_source = result["roster_source"]
    roster_warning = result["roster_warning"]
    player_options = result["player_options"]

    passing_rows, rushing_rows, receiving_rows = aggregate_player_stats(rows)

    if roster_source == "live_google_sheet":
        st.success("Used a fresh roster pull from Google Sheets for this run.")
    elif roster_warning:
        st.warning(f"Used bundled roster snapshot instead of a live refresh. Reason: {roster_warning}")

    stats = st.columns(3)
    stats[0].metric("Rows", max(len(rows) - 1, 0))
    stats[1].metric("Ambiguity Rows", len(ambiguity_rows))
    stats[2].metric("Files", 3)

    download_cols = st.columns(2)
    with download_cols[0]:
        st.download_button(
            "Download Play-by-Play CSV",
            data=pbp_csv,
            file_name=output_name.name,
            mime="text/csv",
            use_container_width=True,
        )
    with download_cols[1]:
        st.download_button(
            "Download Ambiguity Report",
            data=ambiguity_csv,
            file_name=ambiguity_name.name,
            mime="text/csv",
            use_container_width=True,
        )

    totals_tab, on_field_tab, preview_tab, ambiguity_tab = st.tabs(
        ["Player Totals", "On-Field Entries", "Preview", "Ambiguity Report"]
    )

    with totals_tab:
        pass_tab, rush_tab, rec_tab = st.tabs(["Passing", "Rushing", "Receiving"])

        with pass_tab:
            if passing_rows:
                st.dataframe(passing_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No passing stats found for this game.")

        with rush_tab:
            if rushing_rows:
                st.dataframe(rushing_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No rushing stats found for this game.")

        with rec_tab:
            if receiving_rows:
                st.dataframe(receiving_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No receiving stats found for this game.")

    with on_field_tab:
        render_on_field_entry_workflow(rows, output_name, player_options)

    with preview_tab:
        st.caption("Top rows from the generated play-by-play export.")
        st.dataframe(rows[:15], use_container_width=True, hide_index=True)

    with ambiguity_tab:
        if ambiguity_rows:
            st.dataframe(ambiguity_rows, use_container_width=True, hide_index=True)
        else:
            st.success("No ambiguity or missing-player issues were found for this game.")


if __name__ == "__main__":
    main()
