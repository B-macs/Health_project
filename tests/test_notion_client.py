"""
Tests for services/clients/notion.py's schema-migration helpers —
ensure_properties (generalized) and ensure_number_properties (the
number-only wrapper still used by Repository.ensure_garmin_activity_columns).
"""

from __future__ import annotations

from services.clients import notion


class _FakeDatabases:
    def __init__(self, existing_properties: dict):
        self._properties = dict(existing_properties)
        self.update_calls = []

    def retrieve(self, database_id):
        return {"properties": self._properties}

    def update(self, database_id, properties):
        self.update_calls.append({"database_id": database_id, "properties": properties})
        self._properties.update(properties)


class _FakeClient:
    def __init__(self, existing_properties: dict):
        self.databases = _FakeDatabases(existing_properties)


def test_ensure_properties_creates_only_missing_ones():
    client = _FakeClient(existing_properties={"Tightness": {"number": {}}})
    created = notion.ensure_properties(client, "db-1", {
        "Tightness": {"number": {}},          # already exists
        "New Flag": {"checkbox": {}},         # missing
    })
    assert created == ["New Flag"]
    assert client.databases.update_calls == [
        {"database_id": "db-1", "properties": {"New Flag": {"checkbox": {}}}},
    ]


def test_ensure_properties_no_op_when_all_present():
    client = _FakeClient(existing_properties={"Tightness": {"number": {}}})
    created = notion.ensure_properties(client, "db-1", {"Tightness": {"number": {}}})
    assert created == []
    assert client.databases.update_calls == []


def test_ensure_properties_supports_mixed_types_including_select_options():
    client = _FakeClient(existing_properties={})
    created = notion.ensure_properties(client, "db-1", {
        "Craving Type": {"select": {"options": [{"name": "Sweet"}, {"name": "Salty"}]}},
        "Meditation Done": {"checkbox": {}},
        "Sodium (mg)": {"number": {}},
    })
    assert set(created) == {"Craving Type", "Meditation Done", "Sodium (mg)"}
    written = client.databases.update_calls[0]["properties"]
    assert written["Craving Type"]["select"]["options"] == [{"name": "Sweet"}, {"name": "Salty"}]


def test_ensure_number_properties_still_works_via_the_generalized_helper():
    client = _FakeClient(existing_properties={})
    created = notion.ensure_number_properties(client, "db-1", ["Activity Avg HR", "Activity Max HR"])
    assert created == ["Activity Avg HR", "Activity Max HR"]
    written = client.databases.update_calls[0]["properties"]
    assert written == {"Activity Avg HR": {"number": {}}, "Activity Max HR": {"number": {}}}


def test_ensure_number_properties_skips_existing():
    client = _FakeClient(existing_properties={"Activity Avg HR": {"number": {}}})
    created = notion.ensure_number_properties(client, "db-1", ["Activity Avg HR"])
    assert created == []
