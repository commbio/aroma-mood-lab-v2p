# Aroma Mood Lab v2.0p (파일럿)

Streamlit 기반 퍼스널 향 추천 에이전트의 **파일럿 버전**입니다.
기존 Aroma Mood Lab v2(원료 100종)와 같은 프로그램이며, 원료 DB만 **24종**으로 줄였습니다.
기존 v2와는 별도의 GitHub 저장소·별도의 Streamlit 앱으로 운영합니다.

## 기존 v2와 달라진 점

| 항목 | v2 | v2.0p |
|---|---|---|
| 원료 DB (`materials.json`) | 100종 (블렌드 템플릿 포함) | 단품 24종 (템플릿 없음) |
| 앱 이름 표시 | Aroma Mood Lab v2 | Aroma Mood Lab v2.0p |
| 추천 로직·화면·PDF·Google Sheets 저장 | — | 동일 |

그 밖의 작은 수정:
- 원료가 부족할 때 쓰는 기본 원료 이름을 DB와 맞춤 (`시더우드` → `시더우드 아틀라스`)
- Streamlit 최신 버전에서 없어질 예정인 표 옵션(`use_container_width`)을 새 옵션(`width="stretch"`)으로 교체

## 폴더 구조

```
aroma_mood_lab_v2p/
├── app.py                          # 메인 앱
├── recipes.py                      # 레시피 계산 로직
├── safety_rules.py                 # 안전 경고 로직
├── google_sheets_storage.py        # Google Sheets 저장 로직
├── materials.json                  # 파일럿 원료 DB (24종) — 앱이 읽는 파일
├── data/
│   └── materials_v2.0p_24_db.xlsx  # 원료 DB 원본 엑셀
├── tools/
│   └── xlsx_to_materials_json.py   # 엑셀 → materials.json 변환
├── logo.png
├── requirements.txt
├── packages.txt                    # 한글 PDF 폰트
├── .gitignore
└── .streamlit/
    └── secrets.toml.example        # 비밀값 템플릿
```

## 원료 DB를 바꾸고 싶을 때

1. `data/materials_v2.0p_24_db.xlsx`의 `Pilot_DB` 시트를 수정합니다.
2. 프로젝트 폴더에서 변환 스크립트를 실행합니다.

```bash
pip install openpyxl
python tools/xlsx_to_materials_json.py
```

3. 바뀐 `materials.json`(과 엑셀)을 GitHub에 올리면 앱이 자동으로 다시 배포됩니다.

## 로컬 실행

```bash
pip install -r requirements.txt
# .env 파일에 GEMINI_API_KEY, GOOGLE_SHEET_ID 를 적고
# google_service_account.json 을 이 폴더에 둔 뒤
streamlit run app.py
```

## 배포

GitHub 저장소 생성부터 Streamlit Community Cloud 배포까지의 전체 과정은
별도의 "Aroma Mood Lab v2.0p 배포 매뉴얼" 문서를 참고하세요.

`.env`, `google_service_account.json`, `.streamlit/secrets.toml`은 GitHub에 올리지 않습니다.
