import json
import os
import re
import html
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai

from safety_rules import check_safety
from recipes import generate_basic_formula
from google_sheets_storage import (
    ensure_worksheets,
    generate_session_id,
    save_ai_response,
    save_feedback as save_feedback_to_sheet,
    save_recommendation_session,
    save_recommended_materials,
)

# PDF generation
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# ----------------------------
# Settings
# ----------------------------
load_dotenv()


def get_secret(key: str, default: str = "") -> str:
    """로컬(.env)과 Streamlit Cloud(secrets.toml) 양쪽에서 값을 읽어옵니다."""
    value = os.getenv(key, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(key, "")).strip()
    except Exception:
        return default


GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
APP_DIR = Path(__file__).resolve().parent
LOGO_FILE = APP_DIR / "logo.png"

st.set_page_config(
    page_title="Aroma Mood Lab v2.0p",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
    st.stop()

client = genai.Client(api_key=GEMINI_API_KEY)

MATERIALS_FILE = APP_DIR / "materials.json"
if not Path(MATERIALS_FILE).exists():
    st.error("materials.json 파일을 찾을 수 없습니다. 프로젝트 폴더에 파일럿 원료 DB 파일을 materials.json 이름으로 넣어주세요.")
    st.stop()

with open(MATERIALS_FILE, "r", encoding="utf-8") as f:
    materials = json.load(f)

# ----------------------------
# Soft Wellness CSS
# ----------------------------
st.markdown("""
<style>
:root {
    --green: #7FBF9B;
    --deep-green: #2F5D4A;
    --lilac: #B8A6E8;
    --deep-lilac: #7867A8;
    --beige: #F5E9D7;
    --cream: #FFF9EF;
    --mint: #EEF9F1;
    --rose: #FFF4F2;
    --ink: #26332D;
    --sub: #66736D;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(184,166,232,0.18), transparent 34%),
        radial-gradient(circle at top right, rgba(127,191,155,0.22), transparent 30%),
        linear-gradient(180deg, #FBFFF9 0%, #FAF6FF 45%, #FFF9EF 100%);
    color: var(--ink);
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 3.5rem;
    max-width: 1240px;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F3FBF5 0%, #F6F1FF 55%, #FFF8EC 100%);
    border-right: 1px solid rgba(80,80,80,0.08);
}

.hero {
    background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(245,233,215,0.76));
    border: 1px solid rgba(120,120,120,0.12);
    border-radius: 30px;
    padding: 2.1rem 2.2rem;
    box-shadow: 0 18px 45px rgba(70, 93, 80, 0.10);
    margin-bottom: 1.2rem;
    position: relative;
    overflow: hidden;
}

.hero:after {
    content: "";
    position: absolute;
    right: -80px;
    top: -70px;
    width: 280px;
    height: 280px;
    background: radial-gradient(circle, rgba(184,166,232,0.34), transparent 66%);
    border-radius: 50%;
}

.hero-badge {
    display: inline-block;
    background: #FFFFFF;
    color: var(--deep-lilac);
    border: 1px solid rgba(120,100,168,0.16);
    border-radius: 999px;
    padding: 0.38rem 0.82rem;
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    margin-bottom: 0.8rem;
}

.hero-title {
    font-size: 2.55rem;
    line-height: 1.15;
    font-weight: 900;
    color: var(--deep-green);
    margin-bottom: 0.55rem;
}

.hero-subtitle {
    font-size: 1.06rem;
    line-height: 1.72;
    color: #56645D;
    max-width: 760px;
}

.soft-card {
    background: rgba(255,255,255,0.88);
    border: 1px solid rgba(90,90,90,0.10);
    border-radius: 25px;
    padding: 1.25rem 1.3rem;
    box-shadow: 0 12px 34px rgba(70, 93, 80, 0.075);
    margin-bottom: 1rem;
    backdrop-filter: blur(6px);
}

.card-title {
    font-size: 1.15rem;
    font-weight: 850;
    color: var(--deep-green);
    margin-bottom: 0.35rem;
}

.card-subtitle {
    font-size: 0.93rem;
    color: var(--sub);
    margin-bottom: 0.8rem;
    line-height: 1.6;
}

.image-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.8rem;
    margin: 0.5rem 0 1rem 0;
}

.image-tile {
    border-radius: 24px;
    padding: 1rem;
    min-height: 138px;
    border: 1px solid rgba(255,255,255,0.78);
    box-shadow: 0 10px 25px rgba(80,80,80,0.08);
    position: relative;
    overflow: hidden;
}

.image-tile .emoji {
    font-size: 2.5rem;
    margin-bottom: 0.45rem;
}

.image-tile .name {
    font-size: 1.02rem;
    font-weight: 850;
    color: #2F3B35;
}

.image-tile .desc {
    font-size: 0.82rem;
    color: #5E6C65;
    line-height: 1.45;
    margin-top: 0.2rem;
}

.lavender-tile { background: linear-gradient(135deg, #F2ECFF 0%, #FFFFFF 100%); }
.citrus-tile { background: linear-gradient(135deg, #FFF1C9 0%, #FFFFFF 100%); }
.woody-tile { background: linear-gradient(135deg, #F4E5D0 0%, #FFFFFF 100%); }

.badge {
    display: inline-block;
    padding: 0.36rem 0.75rem;
    margin: 0.18rem 0.22rem 0.18rem 0;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 750;
    background: #EEF8F1;
    color: #365C49;
    border: 1px solid rgba(54,92,73,0.10);
}

.badge-lilac {
    background: #F2ECFF;
    color: #6E5A9B;
    border: 1px solid rgba(110,90,155,0.12);
}

.badge-beige {
    background: #FFF3DE;
    color: #7A5A31;
    border: 1px solid rgba(122,90,49,0.12);
}

.metric-box {
    background: rgba(255,255,255,0.9);
    border: 1px solid rgba(80,80,80,0.09);
    border-radius: 22px;
    padding: 1rem;
    text-align: center;
    box-shadow: 0 10px 25px rgba(70,93,80,0.06);
}

.metric-label {
    font-size: 0.83rem;
    color: var(--sub);
    margin-bottom: 0.25rem;
}

.metric-value {
    font-size: 1.45rem;
    font-weight: 900;
    color: var(--deep-green);
}

.result-box {
    background: #FFFFFF;
    border-radius: 22px;
    border: 1px solid rgba(80,80,80,0.10);
    padding: 1.25rem 1.3rem;
    line-height: 1.82;
    color: #2D3B35;
    box-shadow: 0 10px 26px rgba(60,60,60,0.045);
}


.result-box p { margin: 0.35rem 0 0.72rem 0; }
.result-box h3, .result-box h4, .result-box h5, .result-box h6 {
    color: var(--deep-green);
    margin: 1rem 0 0.45rem 0;
    line-height: 1.45;
}
.result-box ul, .result-box ol { margin: 0.3rem 0 0.85rem 1.35rem; padding: 0; }
.result-box li { margin: 0.25rem 0; }
.result-box strong { font-weight: 850; color: #243A31; }
.result-box em { color: #5D547A; }
.result-box code { background: #F2ECFF; padding: 0.08rem 0.3rem; border-radius: 5px; }
.result-box .md-space { height: 0.25rem; }

.recipe-item {
    background: linear-gradient(135deg, #FFFFFF 0%, #F7FCF8 100%);
    border: 1px solid rgba(70,70,70,0.08);
    border-radius: 19px;
    padding: 0.92rem 1rem;
    margin-bottom: 0.62rem;
}

.recipe-name {
    font-size: 1rem;
    font-weight: 850;
    color: #2B3B34;
}

.recipe-note {
    display: inline-block;
    margin-top: 0.32rem;
    font-size: 0.74rem;
    font-weight: 800;
    color: var(--deep-lilac);
    background: #F2ECFF;
    padding: 0.22rem 0.58rem;
    border-radius: 999px;
}

.recipe-amount {
    float: right;
    font-size: 1rem;
    font-weight: 900;
    color: var(--deep-green);
}

.warning-card {
    background: #FFF8F0;
    border: 1px solid rgba(200, 128, 76, 0.22);
    border-radius: 18px;
    padding: 0.85rem 0.95rem;
    margin-bottom: 0.55rem;
    color: #6C4D38;
    line-height: 1.55;
}

.material-mini {
    border-radius: 18px;
    background: #FFFFFF;
    border: 1px solid rgba(80,80,80,0.08);
    padding: 0.85rem 0.95rem;
    margin-bottom: 0.55rem;
}

.stButton > button {
    width: 100%;
    border-radius: 16px;
    padding: 0.82rem 1rem;
    font-weight: 850;
    border: none;
    background: linear-gradient(135deg, var(--green) 0%, var(--lilac) 100%);
    color: white;
    box-shadow: 0 10px 22px rgba(127,191,155,0.28);
}

.stButton > button:hover {
    filter: brightness(1.03);
}

.stDownloadButton > button {
    border-radius: 16px;
    padding: 0.72rem 1rem;
    font-weight: 800;
    border: 1px solid rgba(127,191,155,0.35);
    background: #FFFFFF;
    color: var(--deep-green);
}

textarea, div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    border-radius: 16px !important;
}

hr {
    border-color: rgba(80,80,80,0.10);
}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Helpers
# ----------------------------
FAMILY_ALIASES = {
    "시트러스": ["citrus", "fresh", "clean", "sweet", "sparkling"],
    "허브": ["herbal", "green", "aromatic"],
    "우디": ["woody", "dry", "warm", "smoky"],
    "플로럴": ["floral", "rosy", "powdery"],
    "민트": ["mint", "cool"],
    "레진": ["resin", "balsamic", "incense"],
    "스파이스": ["spicy", "warm", "ginger", "pepper"],
    "그린": ["green", "leafy"],
    "달콤함": ["sweet", "vanilla", "gourmand"],
    "클린": ["clean", "fresh", "aquatic", "aldehydic"]
}

CONDITION_TO_FLAGS = {
    "임산부": ["pregnancy_caution", "avoid_pregnancy", "uterine_caution"],
    "어린이 사용": ["children_caution", "avoid_children"],
    "천식": ["asthma_caution", "respiratory_caution", "strong_irritant_possible"],
    "호흡기 민감": ["asthma_caution", "respiratory_caution", "strong_irritant_possible"],
    "알레르기": ["skin_sensitization_possible", "allergen_caution", "sensitizer"],
    "반려동물 있음": ["pet_caution", "cat_caution", "dog_caution"],
    "고양이 있음": ["pet_caution", "cat_caution"],
    "강아지 있음": ["pet_caution", "dog_caution"]
}

MOOD_SYNONYMS = {
    "피곤": ["피곤", "무기력", "졸림", "나른", "지침", "fatigue", "tired"],
    "집중": ["집중", "공부", "업무", "멍함", "선명", "focus", "clarity"],
    "스트레스": ["스트레스", "긴장", "압박", "stress", "tension"],
    "불안": ["불안", "초조", "걱정", "안정", "anxiety", "calm"],
    "수면": ["수면", "잠", "자기 전", "불면", "sleep", "rest"],
    "기분전환": ["기분전환", "우울", "상쾌", "밝은", "refresh", "uplift"],
    "답답함": ["답답", "공기", "환기", "코", "breathing", "fresh air"],
    "포근함": ["포근", "따뜻", "편안", "cozy", "warm"],
}

EFFECT_HINTS = {
    "피곤": ["fatigue", "refresh", "uplift", "clarity"],
    "집중": ["focus", "clarity", "head_clear"],
    "스트레스": ["stress", "relax", "calm"],
    "불안": ["calm", "relax", "grounding"],
    "수면": ["sleep", "relax", "calm"],
    "기분전환": ["uplift", "refresh", "stress"],
    "답답함": ["breathing_space", "refresh", "clarity"],
    "포근함": ["grounding", "calm", "stability"]
}


def normalize_text(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def material_name(m):
    return m.get("name_ko") or m.get("korean_name") or m.get("name") or "이름 없음"


def material_en(m):
    return m.get("name_en") or m.get("english_name") or ""


def material_note(m):
    note = str(m.get("note") or m.get("top_middle_base") or "middle").lower()
    if "top" in note:
        return "top"
    if "base" in note:
        return "base"
    return "middle"


def material_families(m):
    families = m.get("odor_family", [])
    if isinstance(families, str):
        return [x.strip().lower() for x in re.split(r"[,/;]", families) if x.strip()]
    return [str(x).lower() for x in families]


def material_effects(m):
    effects = m.get("effects", []) or m.get("functional_tags", [])
    if isinstance(effects, str):
        return [x.strip().lower() for x in re.split(r"[,/;]", effects) if x.strip()]
    return [str(x).lower() for x in effects]


def material_keywords(m):
    keywords = m.get("mood_keywords", []) or m.get("emotional_tags", [])
    if isinstance(keywords, str):
        return [x.strip().lower() for x in re.split(r"[,/;]", keywords) if x.strip()]
    return [str(x).lower() for x in keywords]


def material_flags(m):
    flags = m.get("safety_flags", [])
    if isinstance(flags, str):
        return [x.strip().lower() for x in re.split(r"[,/;]", flags) if x.strip()]
    return [str(x).lower() for x in flags]


def material_description(m):
    return m.get("description") or m.get("room_spray_tip") or "향 설명이 아직 입력되지 않았습니다."


def extract_mood_targets(text):
    text_l = normalize_text(text)
    detected = []
    for mood, syns in MOOD_SYNONYMS.items():
        if any(s.lower() in text_l for s in syns):
            detected.append(mood)
    return detected


def family_match_score(families, selected_families):
    score = 0
    for label in selected_families:
        aliases = FAMILY_ALIASES.get(label, [])
        if any(alias in families for alias in aliases):
            score += 4
    return score


def dislike_penalty(families, disliked_families):
    penalty = 0
    for label in disliked_families:
        aliases = FAMILY_ALIASES.get(label, [])
        if any(alias in families for alias in aliases):
            penalty += 7
    return penalty


def safety_penalty(flags, user_conditions):
    penalty = 0
    matched = []
    for condition in user_conditions:
        risky_flags = CONDITION_TO_FLAGS.get(condition, [])
        for flag in risky_flags:
            if flag.lower() in flags:
                penalty += 8
                matched.append(flag)
    if "strong_irritant_possible" in flags:
        penalty += 2
    return penalty, matched


def score_materials(text, liked_families, disliked_families, user_conditions, max_candidates=20):
    text_l = normalize_text(text)
    mood_targets = extract_mood_targets(text)
    scored = []

    for m in materials:
        families = material_families(m)
        effects = material_effects(m)
        keywords = material_keywords(m)
        flags = material_flags(m)

        score = 0
        reasons = []

        # 1. Direct mood keyword score
        for kw in keywords:
            if kw and kw.lower() in text_l:
                score += 6
                reasons.append(f"기분 키워드 매칭: {kw}")

        # 2. Mood target -> effect tag score
        for mood in mood_targets:
            for effect in EFFECT_HINTS.get(mood, []):
                if effect.lower() in effects:
                    score += 5
                    reasons.append(f"상태 태그 '{mood}'에 적합")

        # 3. Desired text direct effect score
        for effect in effects:
            if effect and effect.lower() in text_l:
                score += 4
                reasons.append(f"효과 태그 매칭: {effect}")

        # 4. Family preference score
        pref_score = family_match_score(families, liked_families)
        if pref_score:
            score += pref_score
            reasons.append("선호 향 계열 반영")

        # 5. Disliked family penalty
        d_penalty = dislike_penalty(families, disliked_families)
        if d_penalty:
            score -= d_penalty
            reasons.append("비선호 향 계열 감점")

        # 6. Safety penalty
        s_penalty, matched_flags = safety_penalty(flags, user_conditions)
        if s_penalty:
            score -= s_penalty
            reasons.append("안전 조건 감점")

        # mild base score to avoid zero-only issues if preferred family matches
        if not reasons and pref_score == 0:
            score += 0

        if score > 0:
            scored.append({
                "score": score,
                "material": m,
                "reasons": reasons[:4],
                "safety_matched_flags": matched_flags
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:max_candidates], mood_targets


def auto_balance_top_middle_base(scored_candidates, target_count=6):
    """Select materials with an approximate room-spray balance: top 45%, middle 40%, base 15%."""
    by_note = {"top": [], "middle": [], "base": []}
    for item in scored_candidates:
        note = material_note(item["material"])
        by_note[note].append(item)

    targets = {"top": 2, "middle": 3, "base": 1}
    selected = []
    selected_ids = set()

    for note, count in targets.items():
        for item in by_note[note][:count]:
            selected.append(item)
            selected_ids.add(id(item["material"]))

    # Fill gaps with next best candidates regardless of note
    for item in scored_candidates:
        if len(selected) >= target_count:
            break
        if id(item["material"]) not in selected_ids:
            selected.append(item)
            selected_ids.add(id(item["material"]))

    # Fallback if still too few
    fallback_names = ["라벤더", "스위트오렌지", "베르가못 FCF", "시더우드 아틀라스", "레몬", "프랑킨센스"]
    for name in fallback_names:
        if len(selected) >= target_count:
            break
        for m in materials:
            if material_name(m) == name and id(m) not in selected_ids:
                selected.append({"score": 1, "material": m, "reasons": ["기본 밸런스 보정"], "safety_matched_flags": []})
                selected_ids.add(id(m))
                break

    return selected[:target_count]


def sanitize_for_recipe(selected_items):
    """Convert arbitrary DB rows to the field names used by recipes.py and safety_rules.py."""
    converted = []
    for item in selected_items:
        m = item["material"]
        converted.append({
            "name_ko": material_name(m),
            "name_en": material_en(m),
            "note": material_note(m),
            "odor_family": material_families(m),
            "effects": material_effects(m),
            "mood_keywords": material_keywords(m),
            "safety_flags": material_flags(m),
            "description": material_description(m)
        })
    return converted


def markdown_to_html(text):
    """Convert the subset of Markdown used by the AI response into safe HTML."""
    if not text:
        return ""

    def inline_format(value):
        value = html.escape(str(value), quote=False)
        value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
        value = re.sub(r"__(.+?)__", r"<strong>\1</strong>", value)
        value = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", value)
        value = re.sub(r"(?<!_)_([^_\n]+?)_(?!_)", r"<em>\1</em>", value)
        value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
        return value

    blocks = []
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            blocks.append("</ul>")
            in_ul = False
        if in_ol:
            blocks.append("</ol>")
            in_ol = False

    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line:
            close_lists()
            blocks.append('<div class="md-space"></div>')
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            close_lists()
            level = min(len(heading.group(1)) + 2, 6)
            blocks.append(f"<h{level}>{inline_format(heading.group(2))}</h{level}>")
            continue

        bullet = re.match(r"^[-*+]\s+(.+)$", line)
        if bullet:
            if in_ol:
                blocks.append("</ol>")
                in_ol = False
            if not in_ul:
                blocks.append("<ul>")
                in_ul = True
            blocks.append(f"<li>{inline_format(bullet.group(1))}</li>")
            continue

        numbered = re.match(r"^\d+[.)]\s+(.+)$", line)
        if numbered:
            if in_ul:
                blocks.append("</ul>")
                in_ul = False
            if not in_ol:
                blocks.append("<ol>")
                in_ol = True
            blocks.append(f"<li>{inline_format(numbered.group(1))}</li>")
            continue

        close_lists()
        blocks.append(f"<p>{inline_format(line)}</p>")

    close_lists()
    return "".join(blocks)


def markdown_to_reportlab(text):
    """Convert basic Markdown into ReportLab Paragraph markup."""
    if not text:
        return ""
    value = html.escape(str(text), quote=False)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value, flags=re.DOTALL)
    value = re.sub(r"__(.+?)__", r"<b>\1</b>", value, flags=re.DOTALL)
    value = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", value)
    value = re.sub(r"(?<!_)_([^_\n]+?)_(?!_)", r"<i>\1</i>", value)
    value = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", value, flags=re.MULTILINE)
    value = re.sub(r"^[-*+]\s+", "• ", value, flags=re.MULTILINE)
    value = re.sub(r"^\d+[.)]\s+", "• ", value, flags=re.MULTILINE)
    return value.replace("\n", "<br/>")


def render_badges(items, class_name="badge"):
    return "".join([f'<span class="{class_name}">{x}</span>' for x in items])


def render_recipe_cards(formula_items):
    html = ""
    for item in formula_items:
        html += f"""
        <div class="recipe-item">
            <div class="recipe-name">
                {item['name_ko']} <span style="font-weight:500; color:#7D8A84;">({item['name_en']})</span>
                <span class="recipe-amount">{item['amount_ml']} ml</span>
            </div>
            <div class="recipe-note">{item['note']} note</div>
        </div>
        """
    return html


def try_register_korean_font():
    if not REPORTLAB_AVAILABLE:
        return "Helvetica"

    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("KoreanFont", path))
                return "KoreanFont"
            except Exception:
                continue
    return "Helvetica"


def create_pdf_bytes(result_text, recipe, selected_materials, safety_warnings, user_input, desired_effect, intensity, gender, age):
    if not REPORTLAB_AVAILABLE:
        return None

    buffer = BytesIO()
    font_name = try_register_korean_font()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="KTitle",
        fontName=font_name,
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#2F5D4A"),
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="KHeading",
        fontName=font_name,
        fontSize=12,
        leading=18,
        textColor=colors.HexColor("#7867A8"),
        spaceBefore=10,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="KBody",
        fontName=font_name,
        fontSize=9.5,
        leading=15,
        textColor=colors.HexColor("#26332D"),
    ))

    def esc(text):
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

    story = []
    story.append(Paragraph("Aroma Mood Lab v2.0p 추천 리포트", styles["KTitle"]))
    story.append(Paragraph(f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["KBody"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("사용자 입력", styles["KHeading"]))
    story.append(Paragraph(f"성별: {esc(gender)} / 나이: {esc(age)}세", styles["KBody"]))
    story.append(Paragraph(f"기분/컨디션: {esc(user_input)}", styles["KBody"]))
    story.append(Paragraph(f"원하는 효과: {esc(desired_effect)}", styles["KBody"]))
    story.append(Paragraph(f"향 강도: {esc(intensity)}", styles["KBody"]))

    story.append(Paragraph("AI 추천 설명", styles["KHeading"]))
    story.append(Paragraph(markdown_to_reportlab(result_text), styles["KBody"]))

    story.append(Paragraph("100ml 룸스프레이 레시피", styles["KHeading"]))
    table_data = [["원료", "Note", "용량"]]
    for item in recipe["formula"]:
        table_data.append([item["name_ko"], item["note"], f"{item['amount_ml']} ml"])

    table = Table(table_data, colWidths=[75 * mm, 35 * mm, 35 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF9F1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2F5D4A")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8D8D8")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"향료 총량: {recipe['fragrance_total_ml']} ml / 베이스 액상: {recipe['base_liquid_ml']} ml / 향료 농도: {recipe['fragrance_percent']}%", styles["KBody"]))

    story.append(Paragraph("선택 원료", styles["KHeading"]))
    for m in selected_materials:
        story.append(Paragraph(f"• {m['name_ko']} ({m['name_en']}): {esc(m['description'])}", styles["KBody"]))

    story.append(Paragraph("안전 주의사항", styles["KHeading"]))
    for w in safety_warnings:
        story.append(Paragraph(f"• {esc(w)}", styles["KBody"]))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    if LOGO_FILE.exists():
        st.image(str(LOGO_FILE), width=120)
    else:
        st.caption("Community Bio 로고 파일을 찾을 수 없습니다.")

    st.markdown("## 🌿 Aroma Mood Lab v2.0p")
    st.markdown("**Soft Wellness** 스타일의 퍼스널 향 추천 에이전트입니다.")
    st.caption(f"파일럿 버전 · 원료 {len(materials)}종")
    st.markdown("---")
    st.markdown("### 🎨 브랜드 색상")
    st.markdown(render_badges(["초록", "라일락", "베이지"], "badge"), unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### 🌸 향 이미지")
    st.markdown("""
    <div class="image-tile lavender-tile">
        <div class="emoji">💜</div>
        <div class="name">Lavender</div>
        <div class="desc">차분함 · 이완 · 수면 전 분위기</div>
    </div>
    <div class="image-tile citrus-tile" style="margin-top:0.7rem;">
        <div class="emoji">🍊</div>
        <div class="name">Citrus</div>
        <div class="desc">상쾌함 · 기분전환 · 밝은 인상</div>
    </div>
    <div class="image-tile woody-tile" style="margin-top:0.7rem;">
        <div class="emoji">🌲</div>
        <div class="name">Woody</div>
        <div class="desc">안정감 · 깊이 · 지속감</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    st.caption("본 앱은 테스트용이며 의학적 진단·치료 목적이 아닙니다.")

# ----------------------------
# Brand logo + Hero
# ----------------------------

st.markdown("""
<div class="hero">
    <div class="hero-badge">SOFT WELLNESS AROMA RECOMMENDER</div>
    <div class="hero-title">🌿 Aroma Mood Lab v2.0p</div>
    <div class="hero-subtitle">
        현재의 기분과 컨디션, 선호하는 향 계열, 안전 조건을 반영해<br>
        AI가 퍼스널 향 맞춤 레시피를 제안합니다.
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Image tiles on main
# ----------------------------
st.markdown("""
<div class="image-row">
    <div class="image-tile lavender-tile">
        <div class="emoji">💜</div>
        <div class="name">Lavender Mood</div>
        <div class="desc">부드럽고 차분한 휴식감</div>
    </div>
    <div class="image-tile citrus-tile">
        <div class="emoji">🍋</div>
        <div class="name">Citrus Fresh</div>
        <div class="desc">맑고 밝은 기분 전환</div>
    </div>
    <div class="image-tile woody-tile">
        <div class="emoji">🪵</div>
        <div class="name">Woody Calm</div>
        <div class="desc">따뜻하고 안정적인 베이스</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Input card
# ----------------------------
st.markdown('<div class="soft-card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">📝 나의 상태와 향 취향 입력</div>', unsafe_allow_html=True)
st.markdown('<div class="card-subtitle">AI가 DB에서 기분 태그, 향 계열 선호도, 안전 조건, 노트 밸런스를 종합해 추천합니다.</div>', unsafe_allow_html=True)

col_a, col_b = st.columns([1.15, 0.85], gap="large")

with col_a:
    user_input = st.text_area(
        "오늘의 기분이나 몸 상태",
        placeholder="예: 피곤하고 머리가 무거워요. 집중이 잘 안 되고 상쾌하지만 너무 강하지 않은 향을 원해요.",
        height=145,
    )
    desired_effect = st.text_input(
        "원하는 효과",
        placeholder="예: 집중, 기분전환, 차분함, 수면 전 안정감"
    )

with col_b:
    profile_col1, profile_col2 = st.columns(2)
    with profile_col1:
        gender = st.selectbox("성별", ["여성", "남성", "기타/응답하지 않음"])
    with profile_col2:
        age = st.number_input("나이", min_value=1, max_value=120, value=30, step=1)
    intensity = st.selectbox("향의 강도", ["은은함", "보통", "강함"])
    liked_families = st.multiselect(
        "좋아하는 향 계열",
        list(FAMILY_ALIASES.keys()),
        default=["시트러스"]
    )
    disliked_families = st.multiselect(
        "싫어하거나 피하고 싶은 향 계열",
        list(FAMILY_ALIASES.keys()),
        default=[]
    )
    user_conditions = st.multiselect(
        "안전 조건",
        ["임산부", "어린이 사용", "천식", "호흡기 민감", "알레르기", "반려동물 있음", "고양이 있음", "강아지 있음"]
    )

run_button = st.button("✨ 퍼스널맞춤향 추천받기")
st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# Session state
# ----------------------------
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "feedback_log" not in st.session_state:
    st.session_state.feedback_log = []

# ----------------------------
# Run recommendation
# ----------------------------
if run_button:
    if not user_input.strip():
        st.warning("먼저 기분이나 컨디션을 입력해주세요.")
    else:
        combined_text = f"{user_input} {desired_effect}"
        scored_candidates, mood_targets = score_materials(
            combined_text,
            liked_families,
            disliked_families,
            user_conditions,
            max_candidates=24
        )
        selected_items = auto_balance_top_middle_base(scored_candidates, target_count=6)
        selected_materials = sanitize_for_recipe(selected_items)

        safety_warnings = check_safety(selected_materials, user_conditions)
        recipe = generate_basic_formula(selected_materials, intensity)

        selected_detail = []
        for item, converted in zip(selected_items, selected_materials):
            selected_detail.append({
                **converted,
                "score": item["score"],
                "reasons": item["reasons"]
            })

        material_summary = "\n".join([
            f"- {m['name_ko']}({m['name_en']}): {m['description']} / score={m['score']} / reasons={', '.join(m['reasons'])}"
            for m in selected_detail
        ])
        formula_summary = "\n".join([
            f"- {item['name_ko']}: {item['amount_ml']} ml"
            for item in recipe["formula"]
        ])
        safety_summary = "\n".join([f"- {w}" for w in safety_warnings])

        prompt = f"""
너는 룸스프레이용 개인 맞춤 향 추천 에이전트다.

중요 원칙:
- 의학적 진단이나 치료 효과를 단정하지 않는다.
- 치료한다, 완치한다, 질병을 고친다 같은 표현을 쓰지 않는다.
- 향의 분위기, 사용감, 기분 전환, 공간 연출 중심으로 설명한다.
- 안전 주의사항을 반드시 포함한다.
- 사용자가 임산부, 어린이, 천식, 반려동물 조건을 선택한 경우 보수적으로 안내한다.
- 답변은 Soft Wellness 브랜드 톤으로 부드럽고 정돈되게 작성한다.

사용자 기본 정보:
- 성별: {gender}
- 나이: {age}세

사용자의 입력:
{user_input}

원하는 효과:
{desired_effect}

감지된 기분 태그:
{', '.join(mood_targets) if mood_targets else '명확한 태그 없음'}

사용자 선호 향 계열:
{', '.join(liked_families) if liked_families else '없음'}

사용자 비선호 향 계열:
{', '.join(disliked_families) if disliked_families else '없음'}

선택된 향 원료와 추천 근거:
{material_summary}

100ml 룸스프레이 기준 레시피:
향료 총량: {recipe['fragrance_total_ml']} ml
베이스 액상: {recipe['base_liquid_ml']} ml
상세 배합:
{formula_summary}

안전 주의사항:
{safety_summary}

아래 형식으로 한국어로 답변해라.

1. 현재 상태 해석
2. 추천 향 컨셉
3. 추천 원료와 이유
4. 100ml 룸스프레이 기준 레시피
5. 사용 방법
6. 주의사항
"""

        with st.spinner("AI가 DB에서 향 조합을 분석하고 있습니다..."):
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

        session_id = generate_session_id()

        st.session_state.last_result = {
            "session_id": session_id,
            "user_input": user_input,
            "gender": gender,
            "age": age,
            "desired_effect": desired_effect,
            "intensity": intensity,
            "liked_families": liked_families,
            "disliked_families": disliked_families,
            "user_conditions": user_conditions,
            "mood_targets": mood_targets,
            "selected_materials": selected_materials,
            "selected_detail": selected_detail,
            "recipe": recipe,
            "safety_warnings": safety_warnings,
            "result_text": response.text,
            "scored_candidates": scored_candidates,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        try:
            ensure_worksheets()
            save_recommendation_session(
                session_id=session_id,
                gender=gender,
                age=int(age),
                user_input=user_input,
                desired_effect=desired_effect,
                intensity=intensity,
                liked_families=liked_families,
                disliked_families=disliked_families,
                user_conditions=user_conditions,
                mood_targets=mood_targets,
            )
            save_recommended_materials(
                session_id=session_id,
                recipe=recipe,
                selected_detail=selected_detail,
            )
            save_ai_response(
                session_id=session_id,
                model_name="gemini-2.5-flash",
                result_text=response.text,
                prompt_version="v1",
            )
            st.session_state.last_result["sheet_saved"] = True
            st.toast("추천 결과가 Google Sheet에 저장되었습니다.")
        except Exception as error:
            st.session_state.last_result["sheet_saved"] = False
            st.session_state.last_result["sheet_error"] = str(error)
            st.warning(
                "추천 결과는 생성되었지만 Google Sheet 저장에 실패했습니다. "
                f"오류: {error}"
            )

# ----------------------------
# Tabs
# ----------------------------
tab_result, tab_recipe, tab_dictionary, tab_feedback = st.tabs([
    "✨ 추천 결과",
    "🧪 레시피",
    "📚 원료 사전",
    "💬 내 피드백"
])

last = st.session_state.last_result

with tab_result:
    if not last:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">아직 추천 결과가 없습니다.</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-subtitle">위 입력창에 현재 기분과 원하는 효과를 적고 추천받기를 눌러주세요.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        recipe = last["recipe"]
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="metric-box"><div class="metric-label">제품 총량</div><div class="metric-value">{recipe["total_product_ml"]} ml</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-box"><div class="metric-label">향료 농도</div><div class="metric-value">{recipe["fragrance_percent"]}%</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-box"><div class="metric-label">선택 원료</div><div class="metric-value">{len(last["selected_materials"])}개</div></div>', unsafe_allow_html=True)
        with c4:
            mood_count = len(last["mood_targets"])
            st.markdown(f'<div class="metric-box"><div class="metric-label">감지 태그</div><div class="metric-value">{mood_count}개</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns([1.25, 0.75], gap="large")
        with col1:
            st.markdown('<div class="soft-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">🌸 AI 추천 설명</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="result-box">{markdown_to_html(last["result_text"])}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="soft-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">🌿 선택된 향 원료</div>', unsafe_allow_html=True)
            st.markdown(render_badges([m["name_ko"] for m in last["selected_materials"]]), unsafe_allow_html=True)
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown("**감지된 기분 태그**")
            st.markdown(render_badges(last["mood_targets"] or ["일반 추천"], "badge-lilac"), unsafe_allow_html=True)
            st.markdown("**선호 향 계열**")
            st.markdown(render_badges(last["liked_families"] or ["없음"], "badge-beige"), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="soft-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">⚠️ 안전 주의사항</div>', unsafe_allow_html=True)
            for warning in last["safety_warnings"]:
                st.markdown(f'<div class="warning-card">• {warning}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

with tab_recipe:
    if not last:
        st.info("추천을 먼저 실행하면 레시피가 표시됩니다.")
    else:
        recipe = last["recipe"]
        col1, col2 = st.columns([1, 1], gap="large")
        with col1:
            st.markdown('<div class="soft-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">🧪 100ml 룸스프레이 레시피</div>', unsafe_allow_html=True)
            st.markdown('<div class="card-subtitle">top / middle / base 자동 균형화를 거쳐 계산된 배합입니다.</div>', unsafe_allow_html=True)
            st.markdown(render_recipe_cards(recipe["formula"]), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="soft-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">📌 제조 요약</div>', unsafe_allow_html=True)
            st.markdown(f"""
- **제품 총량:** {recipe['total_product_ml']} ml  
- **향료 농도:** {recipe['fragrance_percent']}%  
- **향료 총량:** {recipe['fragrance_total_ml']} ml  
- **베이스 액상:** {recipe['base_liquid_ml']} ml  
- **추천 강도:** {last['intensity']}  
""")
            st.markdown("---")
            st.caption("실제 제품화 시에는 에탄올, 정제수, 가용화제, 보존제, 안정성, IFRA/MSDS 확인이 별도로 필요합니다.")
            st.markdown('</div>', unsafe_allow_html=True)

            pdf_bytes = create_pdf_bytes(
                last["result_text"],
                last["recipe"],
                last["selected_materials"],
                last["safety_warnings"],
                last["user_input"],
                last["desired_effect"],
                last["intensity"],
                last["gender"],
                last["age"]
            )
            if pdf_bytes:
                st.download_button(
                    label="📄 추천 결과 PDF 다운로드",
                    data=pdf_bytes,
                    file_name=f"aroma_recommendation_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )
            else:
                st.warning("PDF 기능을 사용하려면 reportlab을 설치하세요: pip install reportlab")

        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🔎 추천 점수와 근거</div>', unsafe_allow_html=True)
        for m in last["selected_detail"]:
            st.markdown(f"""
<div class="material-mini">
<b>{m['name_ko']} ({m['name_en']})</b><br>
점수: <b>{m['score']}</b><br>
근거: {', '.join(m['reasons']) if m['reasons'] else '기본 밸런스 보정'}<br>
향 계열: {', '.join(m.get('odor_family', []))}<br>
설명: {m['description']}
</div>
""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

with tab_dictionary:
    st.markdown('<div class="soft-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📚 원료 사전</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-subtitle">materials.json에 들어 있는 원료를 검색하고 필터링합니다.</div>', unsafe_allow_html=True)

    q = st.text_input("원료명, 향 계열, 효과, 키워드 검색", placeholder="예: 라벤더, citrus, focus, 차분")
    note_filter = st.multiselect("Note 필터", ["top", "middle", "base"], default=[])
    family_filter = st.multiselect("향 계열 필터", list(FAMILY_ALIASES.keys()), default=[])

    rows = []
    q_l = normalize_text(q)
    for m in materials:
        name = material_name(m)
        en = material_en(m)
        note = material_note(m)
        families = material_families(m)
        effects = material_effects(m)
        keywords = material_keywords(m)
        flags = material_flags(m)
        desc = material_description(m)

        haystack = normalize_text(" ".join([name, en, note, " ".join(families), " ".join(effects), " ".join(keywords), " ".join(flags), desc]))
        if q_l and q_l not in haystack:
            continue
        if note_filter and note not in note_filter:
            continue
        if family_filter:
            if family_match_score(families, family_filter) <= 0:
                continue

        rows.append({
            "name_ko": name,
            "name_en": en,
            "note": note,
            "odor_family": ", ".join(families),
            "effects": ", ".join(effects),
            "mood_keywords": ", ".join(keywords),
            "safety_flags": ", ".join(flags),
            "description": desc
        })

    st.write(f"검색 결과: {len(rows)}개 / 전체 {len(materials)}개")
    st.dataframe(rows, width="stretch", height=480)
    st.markdown('</div>', unsafe_allow_html=True)

with tab_feedback:
    st.markdown('<div class="soft-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">💬 내 피드백</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-subtitle">추천 결과를 평가하면 다음 버전에서 개인화 학습 데이터로 사용할 수 있습니다. 현재 버전은 세션 안에서만 저장됩니다.</div>', unsafe_allow_html=True)

    if not last:
        st.info("추천을 먼저 실행한 뒤 피드백을 남길 수 있습니다.")
    else:
        f1, f2, f3 = st.columns(3)
        with f1:
            scent_score = st.slider("향 만족도", 1, 5, 4)
        with f2:
            effect_score = st.slider("원하는 분위기 적합도", 1, 5, 4)
        with f3:
            strength_feedback = st.selectbox("향 강도 느낌", ["적당함", "너무 약함", "조금 강함", "너무 강함"])

        liked_notes = st.multiselect("특히 좋았던 원료", [m["name_ko"] for m in last["selected_materials"]])
        disliked_notes = st.multiselect("다음에는 줄이거나 빼고 싶은 원료", [m["name_ko"] for m in last["selected_materials"]])
        free_feedback = st.text_area("메모", placeholder="예: 시트러스는 좋았지만 민트가 조금 강했어요.")

        feedback_key = f"feedback_saved_{last.get('session_id', 'unknown')}"
        if st.button(
            "💾 피드백 저장",
            disabled=st.session_state.get(feedback_key, False),
        ):
            try:
                feedback_id = save_feedback_to_sheet(
                    session_id=last["session_id"],
                    scent_score=scent_score,
                    effect_score=effect_score,
                    strength_feedback=strength_feedback,
                    liked_materials=liked_notes,
                    disliked_materials=disliked_notes,
                    free_feedback=free_feedback,
                )

                feedback_record = {
                    "feedback_id": feedback_id,
                    "session_id": last["session_id"],
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "scent_score": scent_score,
                    "effect_score": effect_score,
                    "strength_feedback": strength_feedback,
                    "liked_notes": liked_notes,
                    "disliked_notes": disliked_notes,
                    "free_feedback": free_feedback,
                    "recipe": last["recipe"]["formula"],
                }
                st.session_state.feedback_log.append(feedback_record)
                st.session_state[feedback_key] = True
                st.success("피드백이 Google Sheet에 저장되었습니다.")
            except Exception as error:
                st.error(f"피드백 저장에 실패했습니다: {error}")

    if st.session_state.feedback_log:
        st.markdown("### 저장된 피드백")
        st.dataframe(st.session_state.feedback_log, width="stretch")

    st.markdown('</div>', unsafe_allow_html=True)
