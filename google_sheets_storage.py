import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import gspread
from google.oauth2.service_account import Credentials

APP_DIR = Path(__file__).resolve().parent
DEFAULT_SERVICE_ACCOUNT_FILE = APP_DIR / "google_service_account.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = {
    "recommendation_sessions": [
        "session_id", "created_at", "gender", "age", "user_input",
        "desired_effect", "intensity", "liked_families",
        "disliked_families", "user_conditions", "mood_targets",
    ],
    "recommendation_materials": [
        "session_id", "material_order", "material_name_ko",
        "material_name_en", "note", "amount_ml", "score", "reasons",
    ],
    "ai_responses": [
        "session_id", "created_at", "model_name", "result_text",
        "prompt_version",
    ],
    "feedback": [
        "feedback_id", "session_id", "created_at", "scent_score",
        "effect_score", "strength_feedback", "liked_materials",
        "disliked_materials", "free_feedback",
    ],
}


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _load_service_account_info() -> dict | None:
    """환경변수 JSON 또는 Streamlit secrets에서 서비스 계정 정보를 읽습니다."""
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_json:
        return json.loads(raw_json)

    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass

    return None


def get_credentials() -> Credentials:
    service_account_info = _load_service_account_info()
    if service_account_info:
        return Credentials.from_service_account_info(
            service_account_info,
            scopes=SCOPES,
        )

    credential_path = Path(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(DEFAULT_SERVICE_ACCOUNT_FILE))
    ).expanduser()

    if credential_path.exists():
        return Credentials.from_service_account_file(
            credential_path,
            scopes=SCOPES,
        )

    raise FileNotFoundError(
        "Google 서비스 계정 인증 정보를 찾을 수 없습니다. "
        "프로젝트 폴더에 google_service_account.json을 두거나 "
        "GOOGLE_SERVICE_ACCOUNT_FILE/GOOGLE_SERVICE_ACCOUNT_JSON을 설정하세요."
    )


def get_spreadsheet_id() -> str:
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()

    if not sheet_id:
        try:
            import streamlit as st
            sheet_id = str(st.secrets.get("GOOGLE_SHEET_ID", "")).strip()
        except Exception:
            pass

    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID가 설정되지 않았습니다.")

    return sheet_id


def get_spreadsheet():
    client = gspread.authorize(get_credentials())
    return client.open_by_key(get_spreadsheet_id())


def ensure_worksheets() -> None:
    """필요한 워크시트와 헤더가 없으면 자동으로 생성합니다."""
    spreadsheet = get_spreadsheet()
    existing = {ws.title: ws for ws in spreadsheet.worksheets()}

    for title, headers in SHEET_HEADERS.items():
        worksheet = existing.get(title)
        if worksheet is None:
            worksheet = spreadsheet.add_worksheet(
                title=title,
                rows=1000,
                cols=max(len(headers), 10),
            )
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(headers, value_input_option="RAW")
        elif first_row != headers:
            worksheet.update(range_name="A1", values=[headers])


def test_connection() -> str:
    ensure_worksheets()
    spreadsheet = get_spreadsheet()
    return spreadsheet.title


def _append_with_retry(worksheet_name: str, rows: Iterable[list], retries: int = 3) -> None:
    rows = list(rows)
    if not rows:
        return

    last_error = None
    for attempt in range(retries):
        try:
            spreadsheet = get_spreadsheet()
            worksheet = spreadsheet.worksheet(worksheet_name)
            worksheet.append_rows(rows, value_input_option="USER_ENTERED")
            return
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{worksheet_name} 저장 실패: {last_error}") from last_error


def generate_session_id() -> str:
    return f"rec_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"


def generate_feedback_id() -> str:
    return f"fb_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"


def save_recommendation_session(
    session_id: str,
    gender: str,
    age: int,
    user_input: str,
    desired_effect: str,
    intensity: str,
    liked_families: list[str],
    disliked_families: list[str],
    user_conditions: list[str],
    mood_targets: list[str],
) -> None:
    _append_with_retry("recommendation_sessions", [[
        session_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        gender,
        age,
        user_input,
        desired_effect,
        intensity,
        _to_text(liked_families),
        _to_text(disliked_families),
        _to_text(user_conditions),
        _to_text(mood_targets),
    ]])


def save_recommended_materials(
    session_id: str,
    recipe: dict,
    selected_detail: list[dict],
) -> None:
    detail_by_name = {
        str(item.get("name_ko", "")): item
        for item in selected_detail
    }

    rows = []
    for order, formula_item in enumerate(recipe.get("formula", []), start=1):
        material_name = str(formula_item.get("name_ko", ""))
        detail = detail_by_name.get(material_name, {})
        rows.append([
            session_id,
            order,
            material_name,
            formula_item.get("name_en", ""),
            formula_item.get("note", ""),
            formula_item.get("amount_ml", ""),
            detail.get("score", ""),
            _to_text(detail.get("reasons", [])),
        ])

    _append_with_retry("recommendation_materials", rows)


def save_ai_response(
    session_id: str,
    model_name: str,
    result_text: str,
    prompt_version: str = "v1",
) -> None:
    _append_with_retry("ai_responses", [[
        session_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        model_name,
        result_text,
        prompt_version,
    ]])


def save_feedback(
    session_id: str,
    scent_score: int,
    effect_score: int,
    strength_feedback: str,
    liked_materials: list[str],
    disliked_materials: list[str],
    free_feedback: str,
) -> str:
    feedback_id = generate_feedback_id()
    _append_with_retry("feedback", [[
        feedback_id,
        session_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        scent_score,
        effect_score,
        strength_feedback,
        _to_text(liked_materials),
        _to_text(disliked_materials),
        free_feedback,
    ]])
    return feedback_id
