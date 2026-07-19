from home_finder import web_app


def test_dashboard_has_three_separate_goals():
    response = web_app.app.test_client().get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "大樓・公寓・華廈" in page
    assert "透天・車墅" in page
    assert "預售屋" in page
