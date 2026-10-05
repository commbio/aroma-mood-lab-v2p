def generate_basic_formula(selected_materials, intensity):
    """
    selected_materials: 선택된 향 원료 리스트
    intensity: 은은함 / 보통 / 강함
    """

    if intensity == "은은함":
        fragrance_percent = 1.0
    elif intensity == "강함":
        fragrance_percent = 3.0
    else:
        fragrance_percent = 2.0

    total_product_ml = 100
    fragrance_ml = total_product_ml * fragrance_percent / 100

    top = [m for m in selected_materials if m.get("note") == "top"]
    middle = [m for m in selected_materials if m.get("note") == "middle"]
    base = [m for m in selected_materials if m.get("note") == "base"]

    formula = []

    note_weights = {
        "top": 0.45,
        "middle": 0.40,
        "base": 0.15
    }

    groups = [
        ("top", top),
        ("middle", middle),
        ("base", base)
    ]

    for note_name, group in groups:
        if not group:
            continue

        group_total_ml = fragrance_ml * note_weights[note_name]
        each_ml = group_total_ml / len(group)

        for material in group:
            formula.append({
                "name_ko": material["name_ko"],
                "name_en": material["name_en"],
                "note": note_name,
                "amount_ml": round(each_ml, 3)
            })

    base_liquid_ml = round(total_product_ml - fragrance_ml, 3)

    return {
        "total_product_ml": total_product_ml,
        "fragrance_percent": fragrance_percent,
        "fragrance_total_ml": round(fragrance_ml, 3),
        "base_liquid_ml": base_liquid_ml,
        "formula": formula
    }
