from app.services.admin_booking.catalog_prompt import build_booking_catalog_knowledge_block


def test_build_booking_catalog_knowledge_block_groups_by_staff():
    staff = [
        {"id": 23, "full_name": "Анна Петровна", "role": "master", "is_active": True},
        {"id": 24, "full_name": "Иван Сидоров", "role": "doctor", "is_active": True},
    ]
    services = [
        {
            "id": 20,
            "title": "Рукав",
            "price_rub": 100.0,
            "duration_minutes": 30,
            "staff_id": 23,
            "staff_full_name": "Анна Петровна",
            "target_role": "master",
            "is_active": True,
        },
        {
            "id": 21,
            "title": "Осмотр",
            "price_rub": 1500.0,
            "duration_minutes": 45,
            "staff_id": 24,
            "staff_full_name": "Иван Сидоров",
            "target_role": "doctor",
            "is_active": True,
        },
    ]

    block = build_booking_catalog_knowledge_block(staff, services)

    assert block.startswith("Актуальная база знаний:")
    assert "Специалисты:" in block
    assert "Анна Петровна (мастер; staff_id=23" in block
    assert "Иван Сидоров (врач; staff_id=24" in block
    assert "«Рукав» — 100 ₽" in block
    assert "service_id=20" in block
    assert "— Анна Петровна:" in block


def test_build_booking_catalog_knowledge_block_empty():
    block = build_booking_catalog_knowledge_block([], [])
    assert "Актуальная база знаний:" in block
    assert "каталог пуст" in block
