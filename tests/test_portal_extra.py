from __future__ import annotations

import json

from fastapi.testclient import TestClient

from warrant.demo.portal import create_portal


def test_extra_content_is_added_without_changing_defaults(tmp_path):
    extra = tmp_path / "extra.json"
    extra.write_text(
        json.dumps(
            {
                "announcements": [
                    {"id": "x1", "course": "CS301", "date": "2026-10-28", "title": "Test notice", "body": "Body text"}
                ],
                "forum": [{"thread": "t2", "author": "Test author", "text": "Test reply text"}],
            }
        ),
        encoding="utf-8",
    )
    with_extra = TestClient(create_portal(extra))
    assert "Test notice" in with_extra.get("/announcements").text
    assert "Test reply text" in with_extra.get("/forum/t2").text
    plain = TestClient(create_portal(""))
    assert "Test notice" not in plain.get("/announcements").text
    assert "Test reply text" not in plain.get("/forum/t2").text
