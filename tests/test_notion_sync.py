"""Sync-worker correctness against the Copy of Client Feedback Master DB.

Payload shapes below are the real ones returned by the Notion API for that database
(Status is a `select`, ID is a `unique_id`, review stage is "👀 REVIEW"). These pin
the four fixes needed to run the sync against the copy.
"""
from app import notion
from app.workers.notion_sync import _is_backward, _STATUS_ORDER


# A representative page as the Notion API returns it for the copy.
SAMPLE_PAGE = {
    "id": "03481b4e-061b-8331-adac-81791df9d257",
    "last_edited_time": "2026-06-20T00:00:00.000Z",
    "properties": {
        "Status": {"select": {"name": "👀 REVIEW"}},
        "ID": {"unique_id": {"number": 131, "prefix": None}},
        "Change Type": {"select": {"name": "AI Fix"}},
        "Priority": {"select": {"name": "MEDIUM"}},
        "Feedback": {"title": [{"plain_text": "Items not exceeding"}]},
        "PIC": {"people": [{"id": "0a9ee3e0-b8e5-49c5-bd0c-b0b91397fc4f"}]},
        "Client Page": {"relation": [{"id": "35981b4e-061b-80a0-9baa-ebf598f702ad"}]},
        "Reported Date": {"date": {"start": "2026-06-20"}},
    },
}


def test_status_reads_select_not_just_status_type():
    # The bug: reading only `.status` returns None for a select-typed Status.
    assert notion.prop_status(SAMPLE_PAGE["properties"], "Status") == "👀 REVIEW"


def test_status_still_reads_native_status_type():
    props = {"Status": {"status": {"name": "Done"}}}
    assert notion.prop_status(props, "Status") == "Done"


def test_unique_id_parses_ticket_number():
    assert notion.prop_unique_id(SAMPLE_PAGE["properties"], "ID") == 131


def test_review_stage_uses_emoji_in_ladder():
    assert "👀 REVIEW" in _STATUS_ORDER
    assert "REVIEW" not in _STATUS_ORDER  # the plain form would break ordering


def test_backward_detection_around_review():
    # A move from REVIEW back to In Progress is a regression (reopen).
    assert _is_backward("👀 REVIEW", "In Progress") is True
    # Forward progress is not.
    assert _is_backward("In Progress", "👀 REVIEW") is False
    # QA Failed is always a regression.
    assert _is_backward("Done", "QA Failed") is True
    # First-seen (no prior status) is never a transition.
    assert _is_backward(None, "Done") is False


def test_other_extractors_on_the_sample():
    props = SAMPLE_PAGE["properties"]
    assert notion.prop_title(props, "Feedback") == "Items not exceeding"
    assert notion.prop_select(props, "Change Type") == "AI Fix"
    assert notion.prop_person_id(props, "PIC") == "0a9ee3e0-b8e5-49c5-bd0c-b0b91397fc4f"
    assert notion.prop_relation_id(props, "Client Page") == "35981b4e-061b-80a0-9baa-ebf598f702ad"
    assert notion.prop_date(props, "Reported Date").year == 2026
    assert notion.prop_created_or_edited(SAMPLE_PAGE, "last_edited_time") is not None
