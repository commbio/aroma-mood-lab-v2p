def check_safety(selected_materials, user_conditions):
    warnings = []

    condition_text = " ".join(user_conditions)

    for material in selected_materials:
        flags = material.get("safety_flags", [])
        name = material.get("name_ko", "")

        if "pregnancy_caution" in flags and "임산부" in condition_text:
            warnings.append(f"{name}: 임신 중 사용 주의가 필요한 원료입니다.")

        if "children_caution" in flags and ("어린이" in condition_text or "아이" in condition_text):
            warnings.append(f"{name}: 어린이 사용 시 주의가 필요한 원료입니다.")

        if "asthma_caution" in flags and ("천식" in condition_text or "호흡기" in condition_text):
            warnings.append(f"{name}: 천식 또는 호흡기 민감성이 있는 경우 주의가 필요합니다.")

        if "pet_caution" in flags and ("반려동물" in condition_text or "고양이" in condition_text or "강아지" in condition_text):
            warnings.append(f"{name}: 반려동물이 있는 공간에서는 주의가 필요합니다.")

        if "phototoxic_caution" in flags:
            warnings.append(f"{name}: 일부 감귤계 원료는 피부 사용 시 광독성 주의가 필요합니다. 룸스프레이라도 피부 직접 분사는 피하세요.")

        if "strong_irritant_possible" in flags:
            warnings.append(f"{name}: 향이 강하고 자극적으로 느껴질 수 있어 낮은 비율 사용을 권장합니다.")

    if not warnings:
        warnings.append("특별한 고위험 조건은 감지되지 않았습니다. 그래도 밀폐 공간에서 과도하게 분사하지 마세요.")

    return warnings
