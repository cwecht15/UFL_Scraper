from __future__ import annotations

import argparse
import csv
import json
import re
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


DEFAULT_TEMPLATE = Path("Sample CSV.csv")
DEFAULT_ROSTER = Path("roster_info.csv")

TEAM_ABBREV_ALIASES = {
    "BHAM": "BHM",
    "BHM": "BHM",
    "LOU": "LOU",
    "CLB": "CLB",
    "ORL": "ORL",
    "HOU": "HOU",
    "ARL": "ARL",
    "DC": "DC",
    "STL": "STL",
}

MAIN_INDICATORS = [
    "pass_play",
    "run_play",
    "no_play",
    "backwards_pass",
    "lateral",
    "dropback",
    "attempt",
    "target",
    "complete",
    "incomplete",
    "passing_touchdown",
    "intercepted",
    "interception_touchdown",
    "reception",
    "sack",
    "rush_attempt",
    "scramble",
    "kneel_down",
    "rushing_touchdown",
    "fumble",
    "fumble_1_out_of_bounds",
    "own_recovery_1",
    "fumble_lost_1",
    "opponent_recovery_1",
    "fumble_recovery_touchdown_1",
    "safety",
    "penalty",
    "penalty_declined",
    "kickoff",
    "touchback",
    "kickoff_out_of_bounds",
    "kick_return",
    "kick_return_touchdown",
    "onside_kick",
    "punt",
    "punt_touchback",
    "punt_out_of_bounds",
    "punt_inside_20",
    "punt_endzone",
    "punt_downed",
    "punt_fair_catch",
    "punt_return",
    "punt_return_touchdown",
    "punt_muffed",
    "punt_blocked",
    "field_goal",
    "field_goal_made",
    "field_goal_blocked",
    "block_field_goal_touchdown",
    "field_goal_return",
    "field_goal_return_TD",
    "1-pt",
    "1-pt Succes",
    "one point rush att",
    "1point pass att",
    "two_point_att",
    "two_point_att_succeeds",
    "two_point_rush_att",
    "two_point_pass_att",
    "defensive_two_point",
    "defensive_two_point_att_succeeds",
    "three_point_att",
    "three_point_att_succeeds",
    "three_point_rush_att",
    "three_point_pass_att",
]

PENALTY_COLUMN_MAP = {
    "false start": "false_start",
    "too many men on field": "too_many_men_on_field",
    "illegal substitution": "illegal_substitution",
    "delay of game": "delay_of_game",
    "delay of kickoff": "delay_of_kickoff",
    "unnecessary roughness": "unnecessary_roughness",
    "disqualification": "disqualification",
    "face mask": "face_mask",
    "unsportsmanlike conduct": "unsportsmanlike_conduct",
    "taunting": "taunting",
    "illegal shift": "illegal_shift",
    "illegal crackback": "illegal_crackback",
    "low block": "low_block",
    "chop block": "chop_block",
    "illegal double-team block": "illegal_double-team_block",
    "illegal blindside block": "illegal_blindside_block",
    "illegal motion": "illegal_motion",
    "illegal block above the waist": "illegal_block_above_the_waist",
    "tripping": "tripping",
    "illegal forward pass": "illegal_forward_pass",
    "illegal touch pass": "illegal_touch_pass",
    "illegal formation": "illegal_formation",
    "lowering the head to initiate contact": "lowering_the_head_to_initiate_contact",
    "intentional grounding": "intentional_grounding",
    "clipping": "clipping",
    "ineligible downfield pass": "ineligible_downfield_pass",
    "illegal use of hands": "illegal_use_of_hands",
    "offensive holding": "offensive_holding",
    "offensive pass interference": "offensive_pass_interference",
    "defensive holding": "defensive_holding",
    "defensive pass interference": "defensive_pass_interference",
    "defensive offside": "defensive_offside",
    "encroachment": "encroachment",
    "neutral zone infraction": "neutral_zone_infraction",
    "roughing the passer": "roughing_the_passer",
    "illegal contact": "illegal_contact",
    "horse collar tackle": "horse_collar_tackle",
    "illegal bat": "illegal_bat",
    "offside on free kick": "offside_on_free_kick",
    "illegal touch": "illegal_touch",
    "player out of bounds on kick": "player_out_of_bounds_on_kick",
    "kick catch interference": "kick_catch_interference",
    "fair catch interference": "fair_catch_interference",
    "running into the kicker": "running_into_the_kicker",
    "roughing the kicker": "roughing_the_kicker",
    "kick formation penalty": "kick_formation_penalty",
    "leverage": "leverage",
    "illegal wedge": "illegal_wedge",
    "ineligible downfield kick": "ineligible_downfield_kick",
    "illegal touch kick": "illegal_touch_kick",
}

RUN_LOCATION_MAP = {
    "up the middle": "Middle",
    "left guard": "Left Guard",
    "right guard": "Right Guard",
    "left tackle": "Left Tackle",
    "right tackle": "Right Tackle",
    "left end": "Left End",
    "right end": "Right End",
}

MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

TEAM_NAME_RE = re.compile(r"^[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)+$")
PLAYER_RE = r"[A-Z]\.[A-Za-z'\\-]+"
PLAYER_NAME_MAPPINGS = [
    ("passer", "passer_name", "passer_id"),
    ("receiver", "receiver_name", "receiver_id"),
    ("rusher", "runner_name", "runner_id"),
    ("1pt Rusher", "1pt Rusher Name", "1pt Rusher ID"),
    ("1PT Passer", "1pt Passer Name", "1pt Passer ID"),
    ("1PT Rec", "1pt Rec Name", "1pt REc ID"),
    ("two_point_rusher", "two_point_rusher_name", "two_point_rusher_id"),
    ("two_point_passer", "two_point_passer_name", "two_point_passer_id"),
    ("two_point_receiver", "two_point_receiver_name", "two_point_receiver_id"),
    ("three_point_rusher", "three_point_rusher_name", "three_point_rusher_id"),
    ("three_point_passer", "three_point_passer_name", "three_point_passer_id"),
    ("three_point_receiver", "three_point_receiver_name", "three_point_receiver_id"),
    ("kicker", "kicker_name", "kicker_id"),
    ("kick_returner", "kick_returner_name", "kick_returner_id"),
    ("punter", "punter_name", "punter_id"),
    ("punt_returner", "punt_returner_name", "punt_returner_id"),
    ("field_goal_kicker", "field_goal_kicker_name", "field_goal_kicker_id"),
    ("penalty_player", "penalty_player_name", "penalty_player_id"),
    ("fumble_player_1", "fumble_player_1_name", "fumble_player_1_id"),
    ("own_recovery_player_1", "own_recovery_player_1_name", "own_recovery_player_1_id"),
    ("fumble_lost_player_1", "fumble_lost_player_1_name", "fumble_lost_player_1_id"),
    ("opponent_recovery_player_1", "opponent_recovery_player_1_name", "opponent_recovery_player_1_id"),
    ("field_goal_blocked_player", "field_goal_blocked_player_name", "field_goal_blocked_player_id"),
    ("field_goal_recovery_player", "field_goal_recovery_player_name", "field_goal_recovery_player_id"),
    ("field_goal_return_player", "field_goal_return_player_name", "field_goal_return_player_id"),
]
AMBIGUITY_REPORT_HEADERS = [
    "issue_type",
    "play_number",
    "quarter",
    "minutes",
    "seconds",
    "player_field",
    "short_player",
    "team",
    "candidates",
    "play_description",
]


class NuxtTable:
    def __init__(self, table: list[Any]) -> None:
        self.table = table

    def deref(self, value: Any) -> Any:
        seen: set[int] = set()
        while True:
            if isinstance(value, int) and 0 <= value < len(self.table) and value not in seen:
                seen.add(value)
                value = self.table[value]
                continue
            if isinstance(value, list) and value and value[0] in {"ShallowReactive", "Reactive"}:
                value = value[1] if len(value) > 1 else None
                continue
            return value

    def obj(self, value: Any) -> dict[str, Any]:
        value = self.deref(value)
        return value if isinstance(value, dict) else {}

    def arr(self, value: Any) -> list[Any]:
        value = self.deref(value)
        return value if isinstance(value, list) else []

    def text(self, value: Any) -> str:
        value = self.deref(value)
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return ""
        return str(value)


def fetch_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def load_headers(template_path: Path | None) -> list[str]:
    if template_path and template_path.exists():
        with template_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            return next(reader)
    return [
        "play_number",
        "play_description",
        "date",
        "stadium",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "quarter",
        "minutes",
        "seconds",
        "los",
        "yards_to_score",
        "down",
        "distance",
        "offense",
        "defense",
        "pass_play",
        "run_play",
        "no_play",
        "passer",
        "complete",
        "incomplete",
        "passing_yards",
        "receiver",
        "rush_attempt",
        "rusher",
        "rushing_yards",
        "kickoff",
        "kicking_team",
        "receiving_team",
        "punt",
        "punter",
        "field_goal",
        "field_goal_made",
        "field_goal_kicker",
        "field_goal_distance",
        "penalty",
        "penalty_team",
        "penalty_player",
        "penalty_yards",
    ]


def make_blank_row(headers: list[str]) -> dict[str, str]:
    row = {header: "" for header in headers}
    for column in MAIN_INDICATORS:
        if column in row:
            row[column] = "0"
    return row


def parse_game_date(url: str, soup: BeautifulSoup) -> str:
    title_text = soup.title.string if soup.title else ""
    title_match = re.search(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})", title_text)
    if title_match:
        month_name = title_match.group(1)[:3].lower()
        return f"{MONTH_MAP[month_name]}/{int(title_match.group(2))}/{title_match.group(3)}"

    path_match = re.search(r"-(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)-(\d{1,2})-(\d{4})-", url, re.I)
    if path_match:
        month = MONTH_MAP[path_match.group(1).lower()]
        return f"{month}/{int(path_match.group(2))}/{path_match.group(3)}"
    return ""


def extract_stadium(table: NuxtTable) -> str:
    def clean_candidate(text: str) -> str:
        text = re.sub(r"^From\s+", "", text, flags=re.I)
        text = re.sub(r"\s+in\s+[A-Z][A-Za-z .'-]+,\s*[A-Z]{2}$", "", text)
        return text.strip()

    candidates: list[str] = []
    for item in table.table:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        if ":" in text or "judge" in text.lower():
            continue
        if re.search(r"\d", text):
            continue
        if "." in text:
            continue
        if len(text.split()) < 2:
            continue
        if re.search(r"\b(Stadium|Dome|Arena|Park|Center)\b", text):
            candidates.append(clean_candidate(text))

    if candidates:
        candidates.sort(key=len, reverse=True)
        return candidates[0]

    for item in table.table:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or ":" in text or "judge" in text.lower():
            continue
        if re.search(r"\bField\b", text):
            return clean_candidate(text)

    return ""


def normalize_team_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def parse_down_distance(title: str) -> tuple[str, str, str]:
    title = " ".join(title.split())
    match = re.match(r"(?P<down>\d)(?:st|nd|rd|th) & (?P<distance>[^•]+?) • (?P<los>.+)", title)
    if match:
        return match.group("down"), match.group("distance").strip(), match.group("los").strip()

    if title in {"Period End", "Game End"}:
        return "", "", ""

    if re.match(r"^(?:[A-Z]{2,4}\s+\d+|\d+|[A-Z]{2,4}\s+End Zone)$", title):
        return "", "", title

    return "", "", ""


def compute_yards_to_score(los: str, offense: str) -> str:
    los = " ".join(los.split())
    midfield_match = re.match(r"^(?P<yard>\d+)$", los)
    if midfield_match:
        return midfield_match.group("yard")

    match = re.match(r"^(?P<team>[A-Z]{2,4}) (?P<yard>\d+)$", los)
    if not match:
        return ""

    yard = int(match.group("yard"))
    if not offense:
        return str(yard)
    return str(100 - yard if match.group("team") == offense else yard)


def extract_short_name(text: str) -> str:
    match = re.search(PLAYER_RE, text)
    return match.group(0) if match else ""


def normalize_short_name(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def normalize_team_abbrev(value: str) -> str:
    return TEAM_ABBREV_ALIASES.get(value.strip().upper(), value.strip().upper())


def short_name_from_full_name(full_name: str) -> str:
    parts = [part for part in re.split(r"\s+", full_name.strip()) if part]
    if not parts:
        return ""

    suffixes = {"JR", "JR.", "SR", "SR.", "II", "III", "IV", "V"}
    while len(parts) > 1 and parts[-1].upper().rstrip(",") in suffixes:
        parts.pop()

    first_token = re.sub(r"[^A-Za-z]", "", parts[0])
    last_token = re.sub(r"[^A-Za-z'\\-]", "", parts[-1])
    if not first_token or not last_token:
        return ""
    return f"{first_token[0].upper()}.{last_token}"


def load_roster_lookup(roster_path: Path | None) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], list[str]]]:
    lookup: dict[tuple[str, str], str] = {}
    grouped: dict[tuple[str, str], list[str]] = {}
    if not roster_path or not roster_path.exists():
        return lookup, {}

    with roster_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) < 2:
                continue
            full_name = row[0].strip()
            team = normalize_team_abbrev(row[1])
            short_name = short_name_from_full_name(full_name)
            if not full_name or not short_name or not team:
                continue
            key = (normalize_short_name(short_name), team)
            lookup[key] = full_name
            grouped.setdefault(key, []).append(full_name)
    ambiguous = {key: names for key, names in grouped.items() if len(names) > 1}
    return lookup, ambiguous


def normalize_run_location(raw: str) -> str:
    value = raw.strip().lower()
    return RUN_LOCATION_MAP.get(value, raw.strip().title())


def update_score(row: dict[str, str], score: dict[str, int], home_team: str, away_team: str) -> None:
    if "home_score" in row:
        row["home_score"] = str(score[home_team])
    if "away_score" in row:
        row["away_score"] = str(score[away_team])


def apply_penalty_flags(row: dict[str, str], penalty_name: str) -> None:
    column = PENALTY_COLUMN_MAP.get(penalty_name.strip().lower())
    if column and column in row:
        row[column] = "1"


def parse_penalty(row: dict[str, str], description: str) -> None:
    match = re.search(
        rf"PENALTY on (?P<team>[A-Z]{{2,4}})(?:-(?P<player>{PLAYER_RE}))?, (?P<name>[^,]+), (?P<yards>-?\d+) yards, (?P<result>accepted|declined)",
        description,
        re.I,
    )
    if not match:
        return

    if "penalty" in row:
        row["penalty"] = "1"
    if "penalty_team" in row:
        row["penalty_team"] = match.group("team")
    if "penalty_player" in row:
        row["penalty_player"] = match.group("player") or ""
    if "penalty_yards" in row:
        row["penalty_yards"] = match.group("yards")
    if match.group("result").lower() == "declined" and "penalty_declined" in row:
        row["penalty_declined"] = "1"
    apply_penalty_flags(row, match.group("name"))


def parse_review(row: dict[str, str], description: str) -> None:
    lowered = description.lower()
    if "reviewed" not in lowered:
        return
    if "challenge_or_review" in row:
        row["challenge_or_review"] = "1"
    if "overturned" in lowered and "challenge_or_review_result" in row:
        row["challenge_or_review_result"] = "reversed"
    elif "upheld" in lowered and "challenge_or_review_result" in row:
        row["challenge_or_review_result"] = "upheld"


def parse_fumble(row: dict[str, str], description: str) -> None:
    if "FUMBLES" not in description:
        return

    if "fumble" in row:
        row["fumble"] = "1"
    if "fumble_1_team" in row and row.get("offense"):
        row["fumble_1_team"] = row["offense"]

    fumbler = re.search(rf"(?P<player>{PLAYER_RE}) FUMBLES", description)
    if fumbler:
        if "fumble_player_1" in row:
            row["fumble_player_1"] = fumbler.group("player")

    if "out of bounds" in description.lower() and "fumble_1_out_of_bounds" in row:
        row["fumble_1_out_of_bounds"] = "1"

    own_recovery = re.search(rf"Fumble RECOVERED by (?P<team>[A-Z]{{2,4}})-(?P<player>{PLAYER_RE})", description)
    if own_recovery:
        team = own_recovery.group("team")
        player = own_recovery.group("player")
        if row.get("offense") and team == row["offense"]:
            if "own_recovery_1" in row:
                row["own_recovery_1"] = "1"
            if "own_recovery_player_1" in row:
                row["own_recovery_player_1"] = player
            if "own_recovery_player_1_team" in row:
                row["own_recovery_player_1_team"] = team
        else:
            if "opponent_recovery_1" in row:
                row["opponent_recovery_1"] = "1"
            if "opponent_recovery_player_1" in row:
                row["opponent_recovery_player_1"] = player
            if "opponent_recovery_player_1_team" in row:
                row["opponent_recovery_player_1_team"] = team
            if "fumble_lost_1" in row:
                row["fumble_lost_1"] = "1"
            if "fumble_lost_player_1" in row:
                row["fumble_lost_player_1"] = fumbler.group("player") if fumbler else ""
            if "fumble_lost_player_1_team" in row:
                row["fumble_lost_player_1_team"] = row.get("offense", "")

        if "TOUCHDOWN" in description and "fumble_recovery_touchdown_1_team" in row:
            row["fumble_recovery_touchdown_1_team"] = team


def parse_kickoff(row: dict[str, str], title: str, description: str, teams: tuple[str, str]) -> bool:
    if " kicks " not in description or "field goal attempt" in description.lower() or "extra point" in description.lower():
        return False

    if "kickoff" in row:
        row["kickoff"] = "1"

    title_team = re.match(r"^(?P<team>[A-Z]{2,4}) \d+$", title)
    kicking_team = title_team.group("team") if title_team else ""
    receiving_team = next((team for team in teams if team and team != kicking_team), "")

    kicker = extract_short_name(description)
    if "kicker" in row:
        row["kicker"] = kicker
    if "kicking_team" in row:
        row["kicking_team"] = kicking_team
    if "receiving_team" in row:
        row["receiving_team"] = receiving_team
    if "Touchback" in description and "touchback" in row:
        row["touchback"] = "1"
    if "out of bounds" in description.lower() and "kickoff_out_of_bounds" in row:
        row["kickoff_out_of_bounds"] = "1"

    returner = re.search(rf"(?P<player>{PLAYER_RE}) returns(?: the kickoff)?", description)
    if returner:
        if "kick_return" in row:
            row["kick_return"] = "1"
        if "kick_returner" in row:
            row["kick_returner"] = returner.group("player")
    if "TOUCHDOWN" in description and "kick_return_touchdown" in row:
        row["kick_return_touchdown"] = "1"
    return True


def parse_punt(row: dict[str, str], description: str) -> bool:
    match = re.search(rf"^(?P<punter>{PLAYER_RE}) punts (?P<yards>-?\d+) yards", description)
    if not match:
        return False

    if "punt" in row:
        row["punt"] = "1"
    if "punter" in row:
        row["punter"] = match.group("punter")
    if "punt_return" in row and "returns" in description:
        row["punt_return"] = "1"
    if "punt_returner" in row:
        punt_returner = re.search(rf"(?P<player>{PLAYER_RE}) returns", description)
        if punt_returner:
            row["punt_returner"] = punt_returner.group("player")
    if "Fair catch" in description and "punt_fair_catch" in row:
        row["punt_fair_catch"] = "1"
    if "Out of bounds" in description or "out of bounds" in description:
        if "punt_out_of_bounds" in row:
            row["punt_out_of_bounds"] = "1"
    if "Touchback" in description and "punt_touchback" in row:
        row["punt_touchback"] = "1"
    if "downed" in description.lower() and "punt_downed" in row:
        row["punt_downed"] = "1"
    if "muffed" in description.lower() and "punt_muffed" in row:
        row["punt_muffed"] = "1"
    if "blocked" in description.lower() and "punt_blocked" in row:
        row["punt_blocked"] = "1"
    if "TOUCHDOWN" in description and "punt_return_touchdown" in row:
        row["punt_return_touchdown"] = "1"
    return True


def parse_field_goal(row: dict[str, str], description: str) -> bool:
    match = re.search(
        rf"^(?P<kicker>{PLAYER_RE}) (?P<distance>\d+) yard field goal attempt is (?P<result>good|no good|blocked)",
        description,
        re.I,
    )
    if not match:
        return False

    if "field_goal" in row:
        row["field_goal"] = "1"
    if "field_goal_kicker" in row:
        row["field_goal_kicker"] = match.group("kicker")
    if "field_goal_distance" in row:
        row["field_goal_distance"] = match.group("distance")

    result = match.group("result").lower()
    if result == "good" and "field_goal_made" in row:
        row["field_goal_made"] = "1"
    if result == "blocked":
        if "field_goal_blocked" in row:
            row["field_goal_blocked"] = "1"
        blocked_by = re.search(rf"(?P<player>{PLAYER_RE}) blocked the kick", description)
        if blocked_by and "field_goal_blocked_player" in row:
            row["field_goal_blocked_player"] = blocked_by.group("player")
    return True


def parse_extra_point(row: dict[str, str], description: str) -> bool:
    match = re.search(rf"^(?P<kicker>{PLAYER_RE}) extra point is (?P<result>good|no good)", description, re.I)
    if not match:
        return False

    if "1-pt" in row:
        row["1-pt"] = "1"
    if match.group("result").lower() == "good" and "1-pt Succes" in row:
        row["1-pt Succes"] = "1"
    if "1PT Passer" in row:
        row["1PT Passer"] = ""
    if "field_goal_kicker" in row:
        row["field_goal_kicker"] = ""
    return True


def parse_conversion_attempt(row: dict[str, str], description: str) -> bool:
    match = re.match(r"^(ONE|TWO|THREE)-POINT CONVERSION ATTEMPT\.\s*(?P<body>.+)$", description, re.I)
    if not match:
        return False

    kind = match.group(1).upper()
    body = match.group("body")
    succeeds = "ATTEMPT SUCCEEDS" in body.upper()

    if kind == "ONE":
        # Current UFL rules use kick extra points, not offensive 1-point conversion tries.
        # We leave these legacy fields for kicker PATs handled in parse_extra_point.
        return False

    if kind == "TWO":
        row["two_point_att"] = "1"
        if succeeds:
            row["two_point_att_succeeds"] = "1"
        rush = re.search(rf"(?P<player>{PLAYER_RE}) rushed", body)
        if rush:
            row["two_point_rush_att"] = "1"
            if "two_point_rusher" in row:
                row["two_point_rusher"] = rush.group("player")
        else:
            passer = re.search(rf"(?P<player>{PLAYER_RE}) steps back to pass", body)
            if passer:
                row["two_point_pass_att"] = "1"
                if "two_point_passer" in row:
                    row["two_point_passer"] = passer.group("player")
                target = re.search(rf"(?:Catch made by|intended for) (?P<player>{PLAYER_RE})", body)
                if target and "two_point_receiver" in row:
                    row["two_point_receiver"] = target.group("player")
        return True

    row["three_point_att"] = "1"
    if succeeds:
        row["three_point_att_succeeds"] = "1"
    rush = re.search(rf"(?P<player>{PLAYER_RE}) rushed", body)
    if rush:
        row["three_point_rush_att"] = "1"
        if "three_point_rusher" in row:
            row["three_point_rusher"] = rush.group("player")
    else:
        passer = re.search(rf"(?P<player>{PLAYER_RE}) steps back to pass", body)
        if passer:
            row["three_point_pass_att"] = "1"
            if "three_point_passer" in row:
                row["three_point_passer"] = passer.group("player")
            target = re.search(rf"(?:Catch made by|intended for) (?P<player>{PLAYER_RE})", body)
            if target and "three_point_receiver" in row:
                row["three_point_receiver"] = target.group("player")
    return True


def parse_spike(row: dict[str, str], description: str) -> bool:
    match = re.search(rf"^(?P<passer>{PLAYER_RE}) spikes the ball\.", description)
    if not match:
        return False
    row["pass_play"] = "1"
    row["dropback"] = "1"
    row["attempt"] = "1"
    row["incomplete"] = "1"
    if "spiked_ball" in row:
        row["spiked_ball"] = "1"
    if "passer" in row:
        row["passer"] = match.group("passer")
    return True


def parse_pass(row: dict[str, str], description: str) -> bool:
    if " pass " not in description.lower() and "Pass " not in description and "steps back to pass" not in description:
        return False

    if "pass_play" in row:
        row["pass_play"] = "1"
    if "dropback" in row:
        row["dropback"] = "1"
    if "attempt" in row:
        row["attempt"] = "1"

    passer_match = re.search(rf"(?P<passer>{PLAYER_RE})", description)
    if passer_match and "passer" in row:
        row["passer"] = passer_match.group("passer")

    location_match = re.search(r"Pass (?P<location>short left|short right|short middle|deep left|deep right|deep middle)", description, re.I)
    if not location_match:
        location_match = re.search(r"pass (?P<location>short left|short right|short middle|deep left|deep right|deep middle)", description, re.I)
    if location_match and "pass_location" in row:
        row["pass_location"] = location_match.group("location").title()

    if "Catch made by" in description:
        if "complete" in row:
            row["complete"] = "1"
        if "reception" in row:
            row["reception"] = "1"
        if "target" in row:
            row["target"] = "1"
        receiver_match = re.search(rf"Catch made by (?P<receiver>{PLAYER_RE})(?: for (?P<yards>-?\d+) yards| for yards)?", description)
        if receiver_match:
            if "receiver" in row:
                row["receiver"] = receiver_match.group("receiver")
            if "passing_yards" in row and receiver_match.group("yards") is not None:
                row["passing_yards"] = receiver_match.group("yards")
    elif "pass incomplete" in description.lower() or "Pass incomplete" in description:
        if "incomplete" in row:
            row["incomplete"] = "1"
        target_match = re.search(rf"intended for (?P<target>{PLAYER_RE})", description)
        if target_match:
            if "target" in row:
                row["target"] = "1"
            if "receiver" in row:
                row["receiver"] = target_match.group("target")

    target_match = re.search(rf"intended for (?P<target>{PLAYER_RE})", description)
    if target_match:
        if "target" in row:
            row["target"] = "1"
        if "receiver" in row and not row.get("receiver"):
            row["receiver"] = target_match.group("target")

    if "INTERCEPTED" in description and "intercepted" in row:
        row["intercepted"] = "1"
    if "TOUCHDOWN" in description and "INTERCEPTED" not in description and row.get("complete") == "1" and "passing_touchdown" in row:
        row["passing_touchdown"] = "1"
    if "Sacked" in description or "sacked" in description:
        if "sack" in row:
            row["sack"] = "1"
    if "Lateral to" in description and "lateral" in row:
        row["lateral"] = "1"
    return True


def parse_run(row: dict[str, str], description: str) -> bool:
    rush_match = re.search(rf"^(?P<runner>{PLAYER_RE}) rushed (?P<location>.+?) for (?P<yards>-?\d+) yards", description)
    scramble_match = re.search(rf"^(?P<runner>{PLAYER_RE}) scrambles (?P<location>.+?) for (?P<yards>-?\d+) yards", description)
    kneel_match = re.search(rf"^(?P<runner>{PLAYER_RE}) kneels?(?: .*?for (?P<yards>-?\d+) yards| at .+?\.)", description)

    match = rush_match or scramble_match or kneel_match
    if not match:
        return False

    if "run_play" in row:
        row["run_play"] = "1"
    if "rush_attempt" in row:
        row["rush_attempt"] = "1"
    if "rusher" in row:
        row["rusher"] = match.group("runner")
    if "runner_name" in row and not row["runner_name"]:
        row["runner_name"] = ""
    if "rushing_yards" in row:
        row["rushing_yards"] = match.group("yards")

    location = ""
    if rush_match or scramble_match:
        location = normalize_run_location(match.group("location"))
    if location and "rush_location" in row:
        row["rush_location"] = location

    if scramble_match and "scramble" in row:
        row["scramble"] = "1"
    if kneel_match and "kneel_down" in row:
        row["kneel_down"] = "1"
    if "TOUCHDOWN" in description and "rushing_touchdown" in row:
        row["rushing_touchdown"] = "1"
    return True


def parse_special_scoring(row: dict[str, str], description: str) -> None:
    if "TOUCHDOWN" not in description:
        return
    lowered = description.lower()
    if "kick_return_touchdown" in row and row.get("kick_return") == "1":
        row["kick_return_touchdown"] = "1"
    if "punt_return_touchdown" in row and row.get("punt_return") == "1":
        row["punt_return_touchdown"] = "1"
    if "fumble_recovery_touchdown_1" in row and "fumble recovered" in lowered:
        row["fumble_recovery_touchdown_1"] = "1"
    if "interception_touchdown" in row and "intercepted" in lowered:
        row["interception_touchdown"] = "1"


def infer_score_delta(row: dict[str, str]) -> int:
    if row.get("1-pt") == "1":
        return 1 if row.get("1-pt Succes") == "1" else 0
    if row.get("two_point_att") == "1":
        return 2 if row.get("two_point_att_succeeds") == "1" else 0
    if row.get("three_point_att") == "1":
        return 3 if row.get("three_point_att_succeeds") == "1" else 0
    if row.get("field_goal") == "1":
        return 3 if row.get("field_goal_made") == "1" else 0
    if row.get("safety") == "1":
        return 2
    if any(
        row.get(column) == "1"
        for column in [
            "passing_touchdown",
            "rushing_touchdown",
            "kick_return_touchdown",
            "punt_return_touchdown",
            "interception_touchdown",
            "fumble_recovery_touchdown_1",
        ]
    ):
        return 6
    if "TOUCHDOWN" in row.get("play_description", ""):
        return 6
    return 0


def score_team_for_play(row: dict[str, str], drive_team: str, home_team: str, away_team: str) -> str:
    if row.get("kickoff") == "1" and row.get("kick_return_touchdown") == "1":
        return row.get("receiving_team", "")
    if row.get("punt_return_touchdown") == "1":
        return home_team if drive_team == away_team else away_team
    if row.get("interception_touchdown") == "1":
        return row.get("defense", "")
    if row.get("fumble_recovery_touchdown_1") == "1":
        return row.get("fumble_recovery_touchdown_1_team", "") or row.get("opponent_recovery_player_1_team", "") or row.get("defense", "")
    return drive_team


def populate_offense_defense(row: dict[str, str], drive_team: str, home_team: str, away_team: str) -> None:
    other_team = home_team if drive_team == away_team else away_team
    description = row.get("play_description", "")
    if description in {"End Quarter 1", "End Quarter 2", "End Quarter 3", "End Quarter 4", "End Game"}:
        return
    if row.get("kickoff") == "1":
        return
    if row.get("offense") == "" and drive_team:
        row["offense"] = drive_team
    if row.get("defense") == "" and other_team:
        row["defense"] = other_team


def player_team_context(row: dict[str, str], short_field: str) -> str:
    if short_field in {"passer", "receiver", "rusher", "fumble_player_1", "fumble_lost_player_1"}:
        return row.get("offense", "")
    if short_field in {
        "1pt Rusher",
        "1PT Passer",
        "1PT Rec",
        "two_point_rusher",
        "two_point_passer",
        "two_point_receiver",
        "three_point_rusher",
        "three_point_passer",
        "three_point_receiver",
    }:
        return row.get("offense", "")
    if short_field == "kicker":
        return row.get("kicking_team", "") or row.get("offense", "")
    if short_field == "punter":
        return row.get("offense", "")
    if short_field == "field_goal_kicker":
        return row.get("offense", "")
    if short_field == "kick_returner":
        return row.get("receiving_team", "") or row.get("defense", "")
    if short_field == "punt_returner":
        return row.get("defense", "")
    if short_field == "penalty_player":
        return row.get("penalty_team", "")
    if short_field == "own_recovery_player_1":
        return row.get("own_recovery_player_1_team", "") or row.get("offense", "")
    if short_field == "opponent_recovery_player_1":
        return row.get("opponent_recovery_player_1_team", "") or row.get("defense", "")
    if short_field == "field_goal_blocked_player":
        return row.get("defense", "")
    if short_field == "field_goal_recovery_player":
        return row.get("field_goal_recovery_team", "")
    if short_field == "field_goal_return_player":
        return row.get("defense", "")
    return ""


def enrich_player_field(
    row: dict[str, str],
    roster_lookup: dict[tuple[str, str], str],
    short_field: str,
    name_field: str,
    id_field: str,
) -> None:
    short_name = row.get(short_field, "").strip()
    if not short_name:
        return

    team = normalize_team_abbrev(player_team_context(row, short_field))
    if id_field in row and team:
        row[id_field] = f"{short_name} {team}"

    full_name = roster_lookup.get((normalize_short_name(short_name), team))
    if name_field in row and full_name:
        row[name_field] = full_name


def enrich_player_columns(row: dict[str, str], roster_lookup: dict[tuple[str, str], str]) -> None:
    for short_field, name_field, id_field in PLAYER_NAME_MAPPINGS:
        enrich_player_field(row, roster_lookup, short_field, name_field, id_field)


def collect_ambiguity_rows(
    rows: list[dict[str, str]], ambiguous_lookup: dict[tuple[str, str], list[str]]
) -> list[dict[str, str]]:
    report_rows: list[dict[str, str]] = []

    def add_issue(
        row: dict[str, str],
        issue_type: str,
        player_field: str,
        short_player: str = "",
        team: str = "",
        candidates: str = "",
    ) -> None:
        report_rows.append(
            {
                "issue_type": issue_type,
                "play_number": row.get("play_number", ""),
                "quarter": row.get("quarter", ""),
                "minutes": row.get("minutes", ""),
                "seconds": row.get("seconds", ""),
                "player_field": player_field,
                "short_player": short_player,
                "team": team,
                "candidates": candidates,
                "play_description": row.get("play_description", ""),
            }
        )

    for row in rows:
        for short_field, _, _ in PLAYER_NAME_MAPPINGS:
            player = row.get(short_field, "").strip()
            if not player:
                continue
            team = normalize_team_abbrev(player_team_context(row, short_field))
            if not team:
                continue
            candidates = ambiguous_lookup.get((normalize_short_name(player), team))
            if not candidates:
                continue
            add_issue(row, "ambiguous_player_id", short_field, player, team, " | ".join(candidates))

        if (
            row.get("pass_play") == "1"
            and row.get("intercepted") != "1"
            and row.get("sack") != "1"
            and row.get("spiked_ball") != "1"
            and row.get("target") != "1"
        ):
            add_issue(row, "missing_targeted_receiver", "target", team=row.get("offense", ""))

        if (row.get("run_play") == "1" or row.get("rush_attempt") == "1") and not row.get("rusher", "").strip():
            add_issue(row, "missing_rusher", "rusher", team=row.get("offense", ""))

        if row.get("two_point_att") == "1":
            if row.get("two_point_rush_att") == "1" and not row.get("two_point_rusher", "").strip():
                add_issue(row, "missing_two_point_rusher", "two_point_rusher", team=row.get("offense", ""))
            if row.get("two_point_pass_att") == "1":
                if not row.get("two_point_passer", "").strip():
                    add_issue(row, "missing_two_point_passer", "two_point_passer", team=row.get("offense", ""))
                if not row.get("two_point_receiver", "").strip():
                    add_issue(row, "missing_two_point_receiver", "two_point_receiver", team=row.get("offense", ""))

        if row.get("three_point_att") == "1":
            if row.get("three_point_rush_att") == "1" and not row.get("three_point_rusher", "").strip():
                add_issue(row, "missing_three_point_rusher", "three_point_rusher", team=row.get("offense", ""))
            if row.get("three_point_pass_att") == "1":
                if not row.get("three_point_passer", "").strip():
                    add_issue(row, "missing_three_point_passer", "three_point_passer", team=row.get("offense", ""))
                if not row.get("three_point_receiver", "").strip():
                    add_issue(row, "missing_three_point_receiver", "three_point_receiver", team=row.get("offense", ""))
    return report_rows


def build_team_lookup(table: NuxtTable, header: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    left_team = table.obj(header.get("leftTeam"))
    right_team = table.obj(header.get("rightTeam"))

    away_abbr = table.text(left_team.get("name"))
    home_abbr = table.text(right_team.get("name"))
    away_name = table.text(left_team.get("alternateName")) or table.text(left_team.get("longName"))
    home_name = table.text(right_team.get("alternateName")) or table.text(right_team.get("longName"))

    lookup = {
        normalize_team_name(away_name): away_abbr,
        normalize_team_name(home_name): home_abbr,
        normalize_team_name(table.text(left_team.get("longName"))): away_abbr,
        normalize_team_name(table.text(right_team.get("longName"))): home_abbr,
    }
    names = {"away_abbr": away_abbr, "home_abbr": home_abbr, "away_name": away_name, "home_name": home_name}
    return lookup, names


def extract_drive_team(table: NuxtTable, group: dict[str, Any], team_lookup: dict[str, str]) -> str:
    image = table.obj(group.get("image"))
    alt_text = table.text(image.get("altText"))
    lookup_key = normalize_team_name(alt_text)
    if lookup_key in team_lookup:
        return team_lookup[lookup_key]

    entity_link = table.obj(group.get("entityLink"))
    title = table.text(entity_link.get("title"))
    if TEAM_NAME_RE.match(title):
        lookup_key = normalize_team_name(title)
        return team_lookup.get(lookup_key, "")
    return ""


def extract_rows(
    url: str, template_path: Path | None, roster_path: Path | None = None
) -> tuple[list[str], list[dict[str, str]], list[dict[str, str]]]:
    soup = fetch_soup(url)
    script = soup.find("script", id="__NUXT_DATA__")
    if script is None or not script.string:
        raise RuntimeError("Could not find __NUXT_DATA__ on the Fox Sports page.")

    table = NuxtTable(json.loads(script.string))
    headers = load_headers(template_path)
    roster_lookup, ambiguous_lookup = load_roster_lookup(roster_path)

    root = table.obj(0)
    data = table.obj(root.get("data"))
    page = table.obj(data.get("options:asyncdata:event-page"))
    event = table.obj(page.get("event"))
    header = table.obj(event.get("header"))
    pbp = table.obj(event.get("pbp"))

    team_lookup, names = build_team_lookup(table, header)
    home_team = names["home_abbr"]
    away_team = names["away_abbr"]

    stadium = extract_stadium(table)
    date = parse_game_date(url, soup)

    rows: list[dict[str, str]] = []

    metadata_row = make_blank_row(headers)
    metadata_row["play_number"] = "0"
    metadata_row["date"] = date
    metadata_row["stadium"] = stadium
    metadata_row["home_team"] = home_team
    metadata_row["away_team"] = away_team
    update_score(metadata_row, {home_team: 0, away_team: 0}, home_team, away_team)
    rows.append(metadata_row)

    score = {home_team: 0, away_team: 0}
    play_number = 1

    for section_ref in table.arr(pbp.get("sections")):
        section = table.obj(section_ref)
        for group_ref in table.arr(section.get("groups")):
            group = table.obj(group_ref)
            drive_team = extract_drive_team(table, group, team_lookup)

            for play_ref in table.arr(group.get("plays")):
                play = table.obj(play_ref)
                title = table.text(play.get("title"))
                description = table.text(play.get("playDescription"))

                row = make_blank_row(headers)
                row["play_number"] = str(play_number)
                row["play_description"] = description
                row["date"] = date
                row["stadium"] = stadium
                row["home_team"] = home_team
                row["away_team"] = away_team

                period = table.text(play.get("periodOfPlay")).upper()
                quarter_map = {"1ST": "1", "2ND": "2", "3RD": "3", "4TH": "4", "OT": "OT"}
                if "quarter" in row:
                    row["quarter"] = quarter_map.get(period, period)

                time_of_play = table.text(play.get("timeOfPlay"))
                if re.match(r"^\d{1,2}:\d{2}$", time_of_play):
                    minutes, seconds = time_of_play.split(":")
                    if "minutes" in row:
                        row["minutes"] = str(int(minutes))
                    if "seconds" in row:
                        row["seconds"] = str(int(seconds))

                down, distance, los = parse_down_distance(title)
                if "down" in row:
                    row["down"] = down
                if "distance" in row:
                    row["distance"] = distance
                if "los" in row:
                    row["los"] = los

                parse_review(row, description)
                parse_kickoff(row, title, description, (home_team, away_team))
                parse_punt(row, description)
                parse_field_goal(row, description)
                parse_extra_point(row, description)
                is_conversion_attempt = parse_conversion_attempt(row, description)
                is_spike = parse_spike(row, description)
                if not is_conversion_attempt and not is_spike:
                    parse_pass(row, description)
                    parse_run(row, description)
                parse_penalty(row, description)
                parse_special_scoring(row, description)

                if "No Play" in description and "no_play" in row:
                    row["no_play"] = "1"
                if "safety" in description.lower() and "safety" in row:
                    row["safety"] = "1"

                populate_offense_defense(row, drive_team, home_team, away_team)
                parse_fumble(row, description)
                enrich_player_columns(row, roster_lookup)

                if "yards_to_score" in row:
                    row["yards_to_score"] = compute_yards_to_score(row.get("los", ""), row.get("offense", ""))

                update_score(row, score, home_team, away_team)
                if "offense_score" in row and row.get("offense") in score:
                    row["offense_score"] = str(score[row["offense"]])
                if "defense_score" in row and row.get("defense") in score:
                    row["defense_score"] = str(score[row["defense"]])

                delta = infer_score_delta(row)
                if delta:
                    scoring_team = score_team_for_play(row, drive_team, home_team, away_team)
                    if scoring_team in score:
                        score[scoring_team] += delta
                        update_score(row, score, home_team, away_team)
                        if "offense_score" in row and row.get("offense") in score:
                            row["offense_score"] = str(score[row["offense"]])
                        if "defense_score" in row and row.get("defense") in score:
                            row["defense_score"] = str(score[row["defense"]])

                rows.append(row)
                play_number += 1

    ambiguity_rows = collect_ambiguity_rows(rows, ambiguous_lookup)
    return headers, rows, ambiguity_rows


def default_output_path(url: str) -> Path:
    slug = Path(urlparse(url).path).name
    return Path(f"{slug}_play_by_play.csv")


def write_csv(headers: list[str], rows: list[dict[str, str]], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def ambiguity_report_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_ambiguity_report.csv")


def csv_text(headers: list[str], rows: list[dict[str, str]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def write_ambiguity_report(rows: list[dict[str, str]], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=AMBIGUITY_REPORT_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape UFL play-by-play data from a Fox Sports game page.")
    parser.add_argument("url", help="Fox Sports UFL game URL")
    parser.add_argument("--output", type=Path, default=None, help="Output CSV path")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="Template CSV used for header order")
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER, help="Roster CSV used to backfill player full names from short ids")
    args = parser.parse_args()

    output_path = args.output or default_output_path(args.url)
    headers, rows, ambiguity_rows = extract_rows(args.url, args.template, args.roster)
    write_csv(headers, rows, output_path)
    report_path = ambiguity_report_path(output_path)
    write_ambiguity_report(ambiguity_rows, report_path)
    print(f"Wrote {len(rows)} rows to {output_path}")
    print(f"Wrote {len(ambiguity_rows)} ambiguity rows to {report_path}")


if __name__ == "__main__":
    main()
