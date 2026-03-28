from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path

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
)


st.set_page_config(page_title="UFL Fox Sports PBP Exporter", page_icon="football", layout="wide")


def app_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(158, 201, 88, 0.10), transparent 28%),
                radial-gradient(circle at top left, rgba(233, 96, 83, 0.05), transparent 24%),
                linear-gradient(180deg, #f7f3eb 0%, #efe8dc 100%);
            color: #18220f;
        }
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .hero {
            padding: 1.2rem 1.4rem;
            border: 1px solid rgba(33, 33, 33, 0.08);
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.82);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
            margin-bottom: 1rem;
        }
        .hero h1 {
            font-size: 2rem;
            margin: 0 0 0.3rem 0;
            color: #18220f;
        }
        .hero p {
            margin: 0;
            color: #44503b;
            font-size: 1rem;
        }
        [data-testid="stSidebar"] {
            background: #23242c;
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
        .stTextInput label p,
        .stSubheader,
        .stAlert,
        .stException,
        [data-testid="stMetricLabel"] p {
            color: #24301c !important;
        }
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.62);
            border: 1px solid rgba(24, 34, 15, 0.08);
            border-radius: 16px;
            padding: 0.9rem 1rem;
        }
        [data-testid="stMetricValue"] {
            color: #18220f !important;
        }
        [data-testid="stMetricLabel"] {
            color: #506047 !important;
        }
        [data-testid="stTextInputRootElement"] input {
            color: #f8f8f6;
        }
        [data-testid="stTextInputRootElement"] label,
        [data-testid="stTextInputRootElement"] p {
            color: #24301c !important;
        }
        [data-testid="stDownloadButton"] button {
            border-radius: 14px;
            background: #171923 !important;
            color: #fffaf2 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            font-weight: 600;
        }
        [data-testid="stDownloadButton"] button p,
        [data-testid="stDownloadButton"] button span,
        [data-testid="stDownloadButton"] button div {
            color: #fffaf2 !important;
        }
        [data-testid="stDownloadButton"] button:hover {
            background: #222532 !important;
            color: #ffffff !important;
        }
        .stDataFrame,
        [data-testid="stDataFrame"] {
            background: rgba(255, 255, 255, 0.72);
            border-radius: 16px;
        }
        .note-card {
            padding: 0.9rem 1rem;
            border-radius: 14px;
            background: rgba(24, 34, 15, 0.05);
            border: 1px solid rgba(24, 34, 15, 0.08);
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

    if not run_clicked:
        return

    if not game_url.strip():
        st.error("Enter a Fox Sports game URL first.")
        return

    roster_path: Path | None = None
    roster_source = ""
    roster_warning: str | None = None
    try:
        with st.spinner("Scraping Fox Sports play-by-play and building exports..."):
            roster_path, roster_source, roster_warning = resolve_roster_source(credentials_info)
            headers, rows, ambiguity_rows = extract_rows(game_url.strip(), DEFAULT_TEMPLATE, roster_path)
            pbp_csv = csv_text(headers, rows)
            ambiguity_csv = csv_text(AMBIGUITY_REPORT_HEADERS, ambiguity_rows)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not generate outputs: {exc}")
        return
    finally:
        if roster_source == "live_google_sheet" and roster_path and roster_path.exists():
            roster_path.unlink(missing_ok=True)

    output_name = default_output_path(game_url.strip())
    ambiguity_name = output_name.with_name(f"{output_name.stem}_ambiguity_report.csv")
    passing_rows, rushing_rows, receiving_rows = aggregate_player_stats(rows)

    if roster_source == "live_google_sheet":
        st.success("Used a fresh roster pull from Google Sheets for this run.")
    elif roster_warning:
        st.warning(f"Used bundled roster snapshot instead of a live refresh. Reason: {roster_warning}")

    stats = st.columns(3)
    stats[0].metric("Rows", max(len(rows) - 1, 0))
    stats[1].metric("Ambiguity Rows", len(ambiguity_rows))
    stats[2].metric("Files", 2)

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

    st.subheader("Player Totals")
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

    st.subheader("Preview")
    st.caption("Top rows from the generated play-by-play export.")
    st.dataframe(rows[:15], use_container_width=True, hide_index=True)

    st.subheader("Ambiguity Report")
    if ambiguity_rows:
        st.dataframe(ambiguity_rows, use_container_width=True, hide_index=True)
    else:
        st.success("No ambiguity or missing-player issues were found for this game.")


if __name__ == "__main__":
    main()
