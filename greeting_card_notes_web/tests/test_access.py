"""Access checks: one account cannot use another's note, and private text stays out of PostHog."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.posthog_client import build_event

AUTH = {"Authorization": "Bearer token"}
NOTE_BODY = {
    "occasion_category": "celebrate",
    "specific_moment": "birthday",
    "recipient_name": "Priya",
    "relationship": "friend",
    "relationship_closeness": "warm",
    "known_context": "She remembers the small things.",
    "owner_id": "user-b",
}


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_notes_require_sign_in(self):
        self.assertEqual(self.client.get("/api/notes").status_code, 401)

    @patch("backend.main.fetch_auth_user", return_value={"id": "user-a", "email": "a@example.com"})
    @patch("backend.main.list_notes", return_value=[])
    def test_list_uses_the_token_user(self, list_notes, _fetch_user):
        response = self.client.get("/api/notes?owner_id=user-b", headers=AUTH)
        self.assertEqual(response.status_code, 200)
        list_notes.assert_called_once_with("user-a")

    @patch("backend.main.fetch_auth_user", return_value={"id": "user-a", "email": "a@example.com"})
    @patch("backend.main.get_owned_note", return_value=None)
    def test_other_account_note_is_not_found(self, get_owned_note, _fetch_user):
        response = self.client.get("/api/notes/note-b", headers=AUTH)
        self.assertEqual(response.status_code, 404)
        get_owned_note.assert_called_once_with("note-b", "user-a")
        self.assertNotIn("a@example.com", response.text)

    @patch("backend.main.fetch_auth_user", return_value={"id": "user-a", "email": "a@example.com"})
    @patch("backend.main.save_draft", return_value=None)
    def test_other_account_draft_cannot_be_updated(self, save_draft, _fetch_user):
        response = self.client.patch("/api/notes/note-b", headers=AUTH, json=NOTE_BODY)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(save_draft.call_args.args[0], "user-a")
        self.assertEqual(save_draft.call_args.kwargs["note_id"], "note-b")

    @patch("backend.main.fetch_auth_user", return_value={"id": "user-a", "email": "a@example.com"})
    @patch("backend.main.start_generation", return_value=None)
    def test_generate_uses_the_token_user(self, start_generation, _fetch_user):
        response = self.client.post(
            "/api/notes/generate",
            headers=AUTH,
            json={**NOTE_BODY, "note_id": "note-b"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(start_generation.call_args.args[0], "user-a")
        self.assertEqual(start_generation.call_args.kwargs["note_id"], "note-b")
        self.assertNotIn("She remembers", response.text)

    @patch("backend.main.fetch_auth_user", return_value={"id": "user-a", "email": "a@example.com"})
    def test_non_staff_cannot_score(self, _fetch_user):
        with patch.dict(os.environ, {"STAFF_USER_IDS": "user-b"}):
            response = self.client.post(
                "/api/review/outputs/output-1/qa",
                headers=AUTH,
                json={"qa_score": 4, "qa_notes": "private"},
            )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("a@example.com", response.text)
        self.assertNotIn("private", response.text)

    @patch("backend.services.note_store.request")
    def test_review_rows_omit_email_and_owner(self, request):
        request.return_value = [
            {
                "id": "note-1",
                "recipient_name": "Priya",
                "occasion_category": "celebrate",
                "specific_moment": "birthday",
                "relationship": "friend",
                "status": "ready",
                "updated_at": "2026-10-17T00:00:00Z",
                "owner_id": "user-b",
                "email": "b@example.com",
            }
        ]
        from backend.services.note_store import list_for_review

        row = list_for_review()[0]
        self.assertNotIn("email", row)
        self.assertNotIn("owner_id", row)
        self.assertEqual(row["recipient_name"], "Priya")

    def test_purge_requires_a_secret(self):
        with patch.dict(os.environ, {"CRON_SECRET": "", "PURGE_SECRET": ""}):
            missing = self.client.get("/api/internal/purge")
        self.assertEqual(missing.status_code, 503)
        with patch.dict(os.environ, {"CRON_SECRET": "real-secret", "PURGE_SECRET": ""}):
            rejected = self.client.get(
                "/api/internal/purge",
                headers={"Authorization": "Bearer browser-token"},
            )
        self.assertEqual(rejected.status_code, 401)

    @patch("backend.main.purge_expired_notes", return_value=2)
    def test_purge_runs_with_the_cron_secret(self, purge_expired_notes):
        with patch.dict(os.environ, {"CRON_SECRET": "real-secret", "PURGE_SECRET": ""}):
            response = self.client.get(
                "/api/internal/purge",
                headers={"Authorization": "Bearer real-secret"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["purged"], 2)
        purge_expired_notes.assert_called_once_with()

    def test_posthog_event_drops_private_text(self):
        event = build_event(
            "note_generated",
            "user-a",
            {
                "note_id": "note-1",
                "email": "a@example.com",
                "recipient_name": "Priya",
                "known_context": "She remembers the small things.",
                "content": "Happy birthday.",
            },
        )
        self.assertEqual(event["distinct_id"], "user-a")
        self.assertEqual(event["properties"]["note_id"], "note-1")
        self.assertNotIn("email", event["properties"])
        self.assertNotIn("recipient_name", event["properties"])
        self.assertNotIn("known_context", event["properties"])
        self.assertNotIn("content", event["properties"])
        self.assertFalse(event["properties"]["$process_person_profile"])


if __name__ == "__main__":
    unittest.main()
