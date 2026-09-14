from __future__ import annotations

from pathlib import Path

from home_finder import web_app_v6


def rejected_record(external_id: str, failures: list[str]) -> dict:
    return {
        "listing": {
            "source": "591中古屋",
            "external_id": external_id,
            "title": f"測試房源 {external_id}",
            "url": f"https://example.com/{external_id}",
            "city": "高雄市",
            "district": "大社區",
            "total_price_wan": 1200,
            "deal_kind": "中古屋",
            "property_type": "電梯大樓",
            "main_area_ping": 12,
            "rooms": 2,
            "baths": 1,
            "parking_type": "機械式",
            "search_profile": "大樓公寓華廈",
        },
        "profile": "大樓公寓華廈",
        "status": "rejected",
        "score": 20,
        "hard_failures": failures,
        "missing_required": [],
        "strengths": [],
        "concerns": ["屋齡資料不明", "未達 2 衛浴偏好"],
        "duplicate_ids": [],
    }


def test_one_or_two_required_failures_are_only_in_barely_acceptable_group():
    payload = web_app_v6.build_dashboard_payload(
        [
            rejected_record("one", ["總價 1200 萬，超過 1150 萬"]),
            rejected_record(
                "two",
                [
                    "總價 1200 萬，超過 1150 萬",
                    "主建物坪數 12，低於最低 15",
                ],
            ),
        ]
    )

    assert [item["id"] for item in payload["groups"]["near_match"]] == [
        "one",
        "two",
    ]
    assert payload["groups"]["rejected"] == []


def test_explicitly_missing_or_non_flat_parking_is_always_rejected():
    payload = web_app_v6.build_dashboard_payload(
        [
            rejected_record("none", ["詳情欄位顯示無汽車位"]),
            rejected_record(
                "mechanical",
                ["不是平面車位：5.09坪，機械式，已含售金內"],
            ),
        ]
    )

    assert payload["groups"]["near_match"] == []
    assert [item["id"] for item in payload["groups"]["rejected"]] == [
        "none",
        "mechanical",
    ]


def test_three_required_failures_remain_visible_in_rejected_group():
    payload = web_app_v6.build_dashboard_payload(
        [
            rejected_record(
                "three",
                [
                    "總價 1200 萬，超過 1150 萬",
                    "不是平面車位：5.09坪，機械式，已含售金內",
                    "主建物坪數 12，低於最低 15",
                ],
            )
        ]
    )

    assert payload["groups"]["near_match"] == []
    assert [item["id"] for item in payload["groups"]["rejected"]] == ["three"]


def test_collective_housing_mislabeled_as_house_stays_rejected():
    record = rejected_record(
        "20706035",
        ["樓層為 19 / 22 樓，結構屬於集合住宅，不是透天／別墅"],
    )
    record["profile"] = "透天別墅"
    payload = web_app_v6.build_dashboard_payload([record])

    assert payload["groups"]["near_match"] == []
    assert [item["id"] for item in payload["groups"]["rejected"]] == [
        "20706035"
    ]


def test_explicit_condo_type_in_house_profile_stays_rejected():
    record = rejected_record(
        "condo-in-house",
        ["詳情型態是 電梯大樓，排除疑似混入的車墅廣告"],
    )
    record["profile"] = "透天別墅"
    payload = web_app_v6.build_dashboard_payload([record])

    assert payload["groups"]["near_match"] == []
    assert [item["id"] for item in payload["groups"]["rejected"]] == [
        "condo-in-house"
    ]


def test_ui_names_category_and_lists_all_reasons():
    static_dir = Path(web_app_v6.__file__).with_name("static")
    dashboard_v3 = (static_dir / "dashboard_v3.js").read_text(encoding="utf-8")
    dashboard_v5 = (static_dir / "dashboard_v5.js").read_text(encoding="utf-8")
    dashboard_v6 = (static_dir / "dashboard_v6.js").read_text(encoding="utf-8")

    assert "item.questions.forEach" in dashboard_v3
    assert "item.concerns.forEach" in dashboard_v3
    dashboard_v7 = (static_dir / "dashboard_v7.js").read_text(encoding="utf-8")
    assert "不符合必要條件（${failureCount" in dashboard_v3
    assert "差強人意" in dashboard_v5
    assert "1～2 項必要條件不符" in dashboard_v6
    assert "只差一項" not in dashboard_v5
    assert "只差一項" not in dashboard_v6
    assert 'option value="failures"' in dashboard_v7
    assert "failureCategoryV7" in dashboard_v7
    assert 'data-failure-category="${escapeHtml(value)}"' in dashboard_v7
    assert '["near_match", "rejected"].includes(state.activeStatus)' in dashboard_v7
