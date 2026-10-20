"""A daily copy of Supabase in Supabase Storage (services/backup.py).

Since 2026-10-09 Supabase is the only store and the Free plan takes no
backups. Pinned here: the copy is taken from Supabase itself, uploaded under
the day's name, old copies beyond 30 days are deleted and nothing else is,
and the step only exists with Supabase as the record. Pure: fake HTTP.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from services import backup
from services.config import Config
from services.repository import Repository


class FakeHttp:
    def __init__(self, existing=(), bucket_exists=False):
        self.calls = []
        self.objects = set(existing)
        self.bucket_exists = bucket_exists

    def __call__(self, method, url, headers, data=None):
        self.calls.append((method, url.split("/storage/v1/")[1], headers.get("Content-Type")))
        if url.endswith("/storage/v1/bucket"):
            if self.bucket_exists:
                return 400, b'{"message":"The resource already exists"}'
            self.bucket_exists = True
            return 200, b"{}"
        if "/object/list/" in url:
            return 200, json.dumps([{"name": n} for n in sorted(self.objects)]).encode()
        if method == "DELETE":
            for n in json.loads(data)["prefixes"]:
                self.objects.discard(n)
            return 200, b"[]"
        self.objects.add(url.rsplit("/", 1)[1])
        return 200, b"{}"


class _Store:
    url = "https://x.supabase.co"

    def _headers(self, extra=None):
        return {"apikey": "k", "Authorization": "Bearer k", **(extra or {})}


def test_a_day_is_uploaded_under_its_name_and_old_copies_go():
    http = FakeHttp(existing={"health-2026-08-01.db.gz", "health-2026-09-20.db.gz",
                              "notes.txt"}, bucket_exists=True)
    name = backup.run(_Store(), date(2026, 10, 9), storage=backup.Storage(_Store(), http),
                      take=lambda store: b"gzipped")
    assert name == "health-2026-10-09.db.gz"
    assert http.objects == {"health-2026-09-20.db.gz", "health-2026-10-09.db.gz", "notes.txt"}
    upload = [c for c in http.calls if c[0] == "POST" and c[1].startswith("object/health-backups/")]
    assert upload and upload[0][2] == "application/gzip"


def test_the_bucket_is_created_private_once():
    http = FakeHttp()
    storage = backup.Storage(_Store(), http)
    storage.ensure_bucket()
    storage.ensure_bucket()                      # "already exists" is not an error
    assert http.bucket_exists


def test_only_our_own_dated_copies_ever_expire():
    names = ["health-2026-09-01.db.gz", "health-2026-09-10.db.gz", "health-bad.db.gz",
             "other-2026-01-01.db.gz", "health-2026-10-09.db.gz"]
    assert backup.expired(names, date(2026, 10, 9)) == ["health-2026-09-01.db.gz"]


def test_the_backup_is_not_a_step_with_notion_as_the_record():
    repo = Repository(Config(notion_api_key="k", notion_db_readiness="a",
                             notion_db_training="b", notion_db_config="d",
                             google_sheets_id="e", google_service_account={}))
    assert repo.backup_supabase_if_due(today=date(2026, 10, 9),
                                       now=datetime(2026, 10, 9, 8, 0)) == (True, None)


def test_the_backup_runs_in_the_sync_chain():
    import inspect
    src = inspect.getsource(Repository.run_home_syncs)
    assert 'results["backup"] = self.backup_supabase_if_due(' in src
    assert src.index("backup_supabase_if_due") < src.index("flush_supabase_mirror()")


def test_the_switch_check_names_each_day_of_the_last_week_without_a_copy():
    """Rebuild Phase 9's check before the switch: a backup on each of the last 7
    days. Today waits for its first sync; a name that is not ours counts for nothing."""
    from datetime import date
    from services import backup
    today = date(2026, 10, 20)
    names = [backup.object_name(date(2026, 10, d)) for d in (13, 14, 15, 16, 18, 19)] + ["notes.txt"]
    assert backup.missing_days(names, today) == [date(2026, 10, 17)]
    assert backup.missing_days(names + [backup.object_name(date(2026, 10, 17))], today) == []
    assert backup.missing_days([], today, days=2) == [date(2026, 10, 18), date(2026, 10, 19)]
