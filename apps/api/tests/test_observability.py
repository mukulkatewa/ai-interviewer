from app.observability import init_error_tracking, scrub


def test_scrub_removes_everything_personal():
    event = {
        "message": "boom",
        "user": {"email": "a@b.c", "ip_address": "1.2.3.4"},
        "request": {"url": "/resumes", "method": "POST", "data": "Rahul's resume text", "cookies": {"s": "1"},
                    "headers": {"authorization": "Bearer x"}, "query_string": "next=/x"},
    }  # fmt: skip
    clean = scrub(event, {})
    assert "user" not in clean
    assert clean["request"] == {"url": "/resumes", "method": "POST"}  # the route stays: it is what you debug with
    assert clean["message"] == "boom"


def test_scrub_copes_with_events_that_have_no_request():
    assert scrub({"message": "x"}, {}) == {"message": "x"}


def test_tracking_is_off_without_a_dsn():
    assert init_error_tracking("", "production") is False
