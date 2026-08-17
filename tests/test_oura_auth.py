"""
tests/test_oura_auth.py — the Oura OAuth2 token lifecycle.

The failure these pin is specific and expensive: Oura's refresh tokens are
SINGLE USE, so a refresh whose result is not persisted destroys the
credential, and two concurrent refreshes destroy it too. Both are
unrecoverable without a human in a browser, and neither raises at the moment
it happens — which is why they are tested rather than reasoned about.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from services import oura_auth
from services.clients import oura


NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)


def _token(**kw):
    base = dict(access_token="acc", refresh_token="ref",
                expires_at=NOW + timedelta(days=30), scope="daily", obtained_at=NOW)
    base.update(kw)
    return oura_auth.OAuthToken(**base)


# ─── from_response ────────────────────────────────────────────────────────

def test_from_response_builds_a_token_with_an_absolute_expiry():
    tok = oura_auth.from_response(
        {"access_token": "a", "refresh_token": "r", "expires_in": 3600,
         "scope": "daily", "token_type": "Bearer"}, now=NOW)
    assert tok.access_token == "a"
    assert tok.refresh_token == "r"
    assert tok.expires_at == NOW + timedelta(seconds=3600)


def test_from_response_carries_the_previous_refresh_token_when_absent():
    """Oura rotates on every use, but an absent key must not be read as
    'this credential can never be renewed' — that forces a manual
    re-authorisation which may not be needed."""
    prev = _token(refresh_token="old-ref")
    tok = oura_auth.from_response({"access_token": "a", "expires_in": 60}, now=NOW,
                                  previous=prev)
    assert tok.refresh_token == "old-ref"


def test_from_response_prefers_a_rotated_refresh_token_over_the_previous():
    prev = _token(refresh_token="old-ref")
    tok = oura_auth.from_response(
        {"access_token": "a", "refresh_token": "new-ref", "expires_in": 60},
        now=NOW, previous=prev)
    assert tok.refresh_token == "new-ref"


def test_from_response_without_an_access_token_raises():
    with pytest.raises(oura_auth.OuraTokenError):
        oura_auth.from_response({"refresh_token": "r"}, now=NOW)


def test_missing_expires_in_never_yields_an_unknown_expiry():
    """The loop this prevents is fatal, not merely wasteful: expires_at=None
    makes needs_refresh permanently true, and every refresh burns a
    single-use token."""
    tok = oura_auth.from_response({"access_token": "a", "refresh_token": "r"}, now=NOW)
    assert tok.expires_at is not None
    assert not oura_auth.needs_refresh(tok, now=NOW)


def test_a_garbage_expires_in_falls_back_rather_than_raising():
    tok = oura_auth.from_response(
        {"access_token": "a", "refresh_token": "r", "expires_in": "soon"}, now=NOW)
    assert tok.expires_at == NOW + timedelta(seconds=oura_auth.DEFAULT_EXPIRES_IN_SECONDS)


# ─── needs_refresh / is_expired ───────────────────────────────────────────

def test_a_fresh_token_is_not_due():
    assert not oura_auth.needs_refresh(_token(), now=NOW)


def test_a_token_inside_the_skew_window_is_due_but_not_expired():
    tok = _token(expires_at=NOW + timedelta(hours=1))
    assert oura_auth.needs_refresh(tok, now=NOW)
    assert not oura_auth.is_expired(tok, now=NOW)


def test_the_skew_is_a_full_day_so_a_failed_refresh_has_room_to_retry():
    assert oura_auth.REFRESH_SKEW_SECONDS == 86_400
    assert oura_auth.needs_refresh(_token(expires_at=NOW + timedelta(hours=23)), now=NOW)
    assert not oura_auth.needs_refresh(_token(expires_at=NOW + timedelta(hours=25)), now=NOW)


def test_a_token_with_no_refresh_token_is_never_reported_due():
    """Reporting due would make the caller spend a request to discover there
    is nothing to spend it on. The 401 is what says it is finished."""
    tok = _token(refresh_token="", expires_at=NOW - timedelta(days=1))
    assert not oura_auth.needs_refresh(tok, now=NOW)
    assert oura_auth.is_expired(tok, now=NOW)


def test_an_unknown_expiry_counts_as_due():
    assert oura_auth.needs_refresh(_token(expires_at=None), now=NOW)


def test_none_and_empty_tokens_are_due_and_expired():
    assert oura_auth.needs_refresh(None, now=NOW)
    assert oura_auth.is_expired(None, now=NOW)
    assert oura_auth.is_expired(_token(access_token=""), now=NOW)


# ─── serialisation ────────────────────────────────────────────────────────

def test_json_round_trip_preserves_every_field():
    tok = _token()
    back = oura_auth.from_json(oura_auth.to_json(tok))
    assert back == tok


def test_a_naive_stored_datetime_is_read_as_utc_not_local():
    """The whole reason this module is timezone-aware: the app runs hosted on
    a server whose zone is not the athlete's, and a naive comparison either
    refreshes constantly or expires unnoticed."""
    raw = '{"access_token": "a", "refresh_token": "r", "expires_at": "2026-08-17T12:00:00"}'
    tok = oura_auth.from_json(raw)
    assert tok.expires_at == NOW


@pytest.mark.parametrize("raw", [None, "", "not json", "[]", '{"refresh_token": "r"}'])
def test_unusable_blobs_return_none_rather_than_raising(raw):
    """A corrupt blob in the config store must not take down a page that only
    wanted to render a sync status."""
    assert oura_auth.from_json(raw) is None


# ─── status ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tok,expected", [
    (None, "unauthenticated"),
    (_token(), "ok"),
    (_token(expires_at=NOW + timedelta(hours=1)), "due"),
    (_token(expires_at=NOW - timedelta(days=1)), "stale"),
    (_token(expires_at=NOW - timedelta(days=1), refresh_token=""), "expired"),
])
def test_status_states(tok, expected):
    assert oura_auth.status(tok, now=NOW)["state"] == expected


def test_status_never_leaks_the_token_values():
    """This is rendered on the Sync page and must be safe to screenshot."""
    blob = repr(oura_auth.status(_token(access_token="SECRET-A",
                                        refresh_token="SECRET-R"), now=NOW))
    assert "SECRET-A" not in blob and "SECRET-R" not in blob


def test_scopes_cover_every_endpoint_the_sync_reads():
    # daily summaries + sleep -> daily; workouts -> workout; sessions ->
    # session; spo2 -> spo2; the auth probe -> personal.
    for needed in ("personal", "daily", "workout", "session", "spo2"):
        assert needed in oura_auth.DEFAULT_SCOPES
    assert "email" not in oura_auth.DEFAULT_SCOPES, "nothing reads it"


# ─── clients/oura.py — the auth-vs-transient split ────────────────────────

class _Resp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_get_collection_raises_ouraautherror_on_401(monkeypatch):
    """The distinction that lets the app say 'your login needs renewing'
    instead of the caption that hid a dead credential for five days."""
    monkeypatch.setattr(oura.requests, "get",
                        lambda *a, **k: _Resp(401, {"detail": "expired"}))
    with pytest.raises(oura.OuraAuthError):
        oura.get_collection("tok", "sleep", "2026-08-01", "2026-08-07")


def test_get_collection_still_treats_404_as_no_data(monkeypatch):
    monkeypatch.setattr(oura.requests, "get", lambda *a, **k: _Resp(404))
    assert oura.get_collection("tok", "vo2_max", "2026-08-01", "2026-08-07") == []


def test_get_collection_follows_pagination(monkeypatch):
    pages = [
        _Resp(200, {"data": [{"id": 1}], "next_token": "n1"}),
        _Resp(200, {"data": [{"id": 2}], "next_token": None}),
    ]
    monkeypatch.setattr(oura.requests, "get", lambda *a, **k: pages.pop(0))
    assert oura.get_collection("t", "sleep", "a", "b") == [{"id": 1}, {"id": 2}]


@pytest.mark.parametrize("code", [400, 401])
def test_token_endpoint_rejections_become_ouraautherror(monkeypatch, code):
    monkeypatch.setattr(oura.requests, "post", lambda *a, **k: _Resp(
        code, {"error": "invalid_grant", "error_description": "already used"}))
    with pytest.raises(oura.OuraAuthError, match="already used"):
        oura.refresh_access_token("cid", "sec", "ref")


def test_a_5xx_at_the_token_endpoint_is_NOT_an_auth_error(monkeypatch):
    """A transient outage must not be reported as 're-authorise' — that sends
    the athlete to a browser for something that fixes itself."""
    monkeypatch.setattr(oura.requests, "post", lambda *a, **k: _Resp(503, text="down"))
    with pytest.raises(RuntimeError) as exc:
        oura.refresh_access_token("cid", "sec", "ref")
    assert not isinstance(exc.value, oura.OuraAuthError)


def test_refresh_without_a_stored_token_refuses_before_calling_out(monkeypatch):
    monkeypatch.setattr(oura.requests, "post", lambda *a, **k: pytest.fail("called"))
    with pytest.raises(oura.OuraAuthError, match="re-authorisation"):
        oura.refresh_access_token("cid", "sec", "")


def test_token_post_sends_form_encoded_credentials_in_the_body(monkeypatch):
    seen = {}

    def fake_post(url, data=None, timeout=None, headers=None):
        seen.update(url=url, data=data, headers=headers)
        return _Resp(200, {"access_token": "a", "expires_in": 60})

    monkeypatch.setattr(oura.requests, "post", fake_post)
    oura.refresh_access_token("cid", "sec", "ref")
    assert seen["url"] == oura.TOKEN_URL
    assert seen["data"]["grant_type"] == "refresh_token"
    assert seen["data"]["client_id"] == "cid"
    assert seen["data"]["client_secret"] == "sec"
    assert seen["headers"]["Content-Type"] == "application/x-www-form-urlencoded"


def test_unconfigured_oauth_names_both_accepted_secret_key_spellings():
    with pytest.raises(oura.OuraAuthError) as exc:
        oura.refresh_access_token("", "", "ref")
    assert "OURA_CLIENT_ID" in str(exc.value) and "CLIENT_ID" in str(exc.value)


def test_authorize_url_carries_every_required_parameter():
    url = oura.authorize_url("cid", "http://localhost:8765/callback",
                             ("daily", "personal"), "st4te")
    assert url.startswith(oura.AUTHORIZE_URL + "?")
    assert "client_id=cid" in url
    assert "response_type=code" in url
    assert "scope=daily+personal" in url
    assert "state=st4te" in url


def test_a_blank_redirect_uri_omits_the_parameter_in_both_halves(monkeypatch):
    """Measured against the live application on 2026-08-17: omitting
    redirect_uri reaches the consent screen, every localhost variant is a
    bare 400. Omission is therefore the only flow that works without first
    editing the Oura application registration — and the authorize and token
    requests have to agree, or the exchange is an invalid_grant that reads
    like a bad code."""
    url = oura.authorize_url("cid", "", ("daily",), "st")
    assert "redirect_uri" not in url

    seen = {}
    monkeypatch.setattr(oura.requests, "post", lambda u, data=None, **k: (
        seen.update(data), _Resp(200, {"access_token": "a", "expires_in": 60}))[1])
    oura.exchange_code("cid", "sec", "code", "")
    assert "redirect_uri" not in seen


def test_a_supplied_redirect_uri_is_sent_in_both_halves(monkeypatch):
    assert "redirect_uri=http" in oura.authorize_url(
        "cid", "http://localhost:8765/callback", ("daily",), "st")

    seen = {}
    monkeypatch.setattr(oura.requests, "post", lambda u, data=None, **k: (
        seen.update(data), _Resp(200, {"access_token": "a", "expires_in": 60}))[1])
    oura.exchange_code("cid", "sec", "code", "http://localhost:8765/callback")
    assert seen["redirect_uri"] == "http://localhost:8765/callback"


def test_authorize_url_refuses_a_blank_state():
    """State is the only thing tying a redirect to the request that caused
    it; a default would be identical for every caller."""
    with pytest.raises(oura.OuraAuthError):
        oura.authorize_url("cid", "http://x/cb", ("daily",), "")


def test_the_authorize_and_token_hosts_differ_and_are_not_swapped():
    """Sending either to the other's host returns a redirect to a sign-in
    page rather than an error, which reads like a wrong password."""
    assert oura.AUTHORIZE_URL.startswith("https://cloud.ouraring.com/")
    assert oura.TOKEN_URL.startswith("https://api.ouraring.com/")


# ─── the concurrency hazard, end to end ───────────────────────────────────

def _repo(monkeypatch, **cfg):
    """A Repository whose durable Config store is an in-memory dict, so these
    tests exercise the real _oc / _load_oura_token / _store_oura_token code
    without a Notion round trip. local_cache is already redirected at a
    tmp_path by tests/conftest.py's autouse fixture."""
    from services.config import Config
    from services.repository import Repository

    base = dict(notion_api_key="ntn_test", notion_db_readiness="r",
                notion_db_training="t", notion_db_config="c",
                google_sheets_id="s", google_service_account={"type": "service_account"},
                oura_client_id="cid", oura_client_secret="sec")
    base.update(cfg)
    repo = Repository(Config(**base))
    store: dict[str, str] = {}
    monkeypatch.setattr(Repository, "set_config",
                        lambda self, k, v, today=None: store.__setitem__(k, v))
    monkeypatch.setattr(Repository, "get_config_value",
                        lambda self, k: store.get(k))
    repo._durable_store = store
    return repo


def test_concurrent_refreshes_redeem_the_token_exactly_once(monkeypatch):
    """The failure this guards is unrecoverable: two threads refreshing
    together means one persists a token Oura has already invalidated, and the
    only repair is a human in a browser.

    Drives the real Repository._oc from two threads released together, so the
    second is guaranteed to arrive while the first is still in flight.
    """
    import time as _time

    repo = _repo(monkeypatch)
    repo._store_oura_token(_token(expires_at=NOW - timedelta(days=1)))

    calls = []
    barrier = threading.Barrier(2, timeout=5)

    def slow_refresh(cid, sec, refresh_token):
        calls.append(refresh_token)
        _time.sleep(0.15)          # hold the lock long enough for the racer
        n = len(calls)
        return {"access_token": f"acc-{n}", "refresh_token": f"ref-{n}",
                "expires_in": 2_592_000}

    monkeypatch.setattr(oura, "refresh_access_token", slow_refresh)

    got = []

    def worker():
        barrier.wait()
        got.append(repo._oc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)

    assert len(calls) == 1, f"refresh token redeemed {len(calls)}x — it is single use"
    assert got == ["acc-1", "acc-1"]


def test_a_refresh_is_persisted_to_both_stores_before_it_is_returned(monkeypatch):
    """A successful refresh whose result is not written down has destroyed
    the credential — the old refresh token is already dead."""
    from services.clients import local_cache

    repo = _repo(monkeypatch)
    repo._store_oura_token(_token(expires_at=NOW - timedelta(days=1)))
    monkeypatch.setattr(oura, "refresh_access_token", lambda *a: {
        "access_token": "new-acc", "refresh_token": "new-ref", "expires_in": 2_592_000})

    assert repo._oc == "new-acc"
    assert oura_auth.from_json(local_cache.read()["oura_oauth_token"]).refresh_token == "new-ref"
    assert oura_auth.from_json(repo._durable_store["oura_oauth_token"]).refresh_token == "new-ref"


def test_a_failed_refresh_keeps_serving_a_still_valid_access_token(monkeypatch):
    """The 24-hour skew exists so a transient failure has retries left. Raising
    on the first one would take the sync down for a credential that works."""
    repo = _repo(monkeypatch)
    repo._store_oura_token(_token(expires_at=NOW + timedelta(hours=1)))

    def boom(*a):
        raise RuntimeError("Oura is down")

    monkeypatch.setattr(oura, "refresh_access_token", boom)
    assert repo._oc == "acc"


def test_a_failed_refresh_on_an_already_expired_token_does_raise(monkeypatch):
    """Past expiry there is nothing left to serve, and returning the dead
    token would produce the mystery 401 this work exists to remove."""
    repo = _repo(monkeypatch)
    repo._store_oura_token(_token(expires_at=NOW - timedelta(days=1)))
    monkeypatch.setattr(oura, "refresh_access_token",
                        lambda *a: (_ for _ in ()).throw(oura.OuraAuthError("dead")))
    with pytest.raises(oura.OuraAuthError):
        repo._oc


def test_oauth_takes_precedence_over_a_configured_pat(monkeypatch):
    repo = _repo(monkeypatch, oura_token="legacy-pat")
    repo._store_oura_token(_token(access_token="oauth-acc"))
    assert repo._oc == "oauth-acc"


def test_a_pat_still_works_when_no_oauth_credential_is_stored(monkeypatch):
    """A working legacy token must not be broken by this module existing."""
    repo = _repo(monkeypatch, oura_token="legacy-pat")
    assert repo._oc == "legacy-pat"
    assert repo.oura_auth_status()["kind"] == "pat"


def test_no_credential_at_all_reports_needing_authorisation(monkeypatch):
    repo = _repo(monkeypatch, oura_token="")
    assert repo._oc is None
    st = repo.oura_auth_status()
    assert st["kind"] == "none" and st["needs_authorisation"]


def test_the_durable_copy_rehydrates_a_wiped_local_cache(monkeypatch):
    """The hosted filesystem is wiped on redeploy (key rule 18). Losing the
    credential that way costs a manual browser re-authorisation."""
    from services.clients import local_cache

    repo = _repo(monkeypatch)
    repo._store_oura_token(_token(access_token="survivor"))
    local_cache.update({"oura_oauth_token": None})       # simulate the redeploy

    assert repo._oc == "survivor"
    assert local_cache.read().get("oura_oauth_token"), "should be written back locally"


def test_a_failed_durable_write_is_recorded_not_raised(monkeypatch):
    """By the time this runs the refresh has happened and the old token is
    already dead — raising would abort the sync while holding the only copy
    of a credential it just declined to use."""
    from services.repository import Repository

    repo = _repo(monkeypatch)

    def boom(self, k, v, today=None):
        raise RuntimeError("Notion 502")

    monkeypatch.setattr(Repository, "set_config", boom)
    repo._store_oura_token(_token())
    assert "Notion 502" in repo.oura_auth_status()["persist_error"]
    assert repo._oc == "acc", "the local copy must still serve"


def test_offline_mode_stores_locally_and_never_attempts_a_notion_write(monkeypatch):
    """Notion writes raise offline by contract (_nc); recording that as a
    persist failure would be noise, not information."""
    from services.repository import Repository

    repo = _repo(monkeypatch, datastore_path="ds.db", datastore_mode="readonly")
    monkeypatch.setattr(Repository, "set_config",
                        lambda self, k, v, today=None: pytest.fail("wrote Notion offline"))
    repo._store_oura_token(_token())
    assert repo.oura_auth_status()["persist_error"] is None


def test_oura_configured_is_true_for_a_stale_oauth_credential(monkeypatch):
    """Reporting unconfigured would route the athlete to 'add OURA_TOKEN to
    secrets.toml' — now the wrong repair, and no longer even possible."""
    repo = _repo(monkeypatch, oura_token="")
    repo._store_oura_token(_token(expires_at=NOW - timedelta(days=90)))
    assert repo.oura_configured()


def test_a_revoked_PAT_reports_healthy_until_oura_is_actually_asked(monkeypatch):
    """The gap this whole marker exists to close. A Personal Access Token
    carries no expiry, so nothing about the stored value distinguishes a
    working one from the revoked one this project ran on from 2026-08-12."""
    repo = _repo(monkeypatch, oura_token="dead-pat")
    assert repo.oura_auth_status()["needs_authorisation"] is False

    repo._record_oura_auth_failure(oura.OuraAuthError("401: expired"))
    st = repo.oura_auth_status()
    assert st["state"] == "rejected"
    assert st["needs_authorisation"] is True
    assert "401" in st["rejected"]


def test_an_observed_401_outranks_a_token_that_looks_refreshable(monkeypatch):
    """A refresh token can be revoked while still looking perfectly good."""
    repo = _repo(monkeypatch, oura_token="")
    repo._store_oura_token(_token())
    assert repo.oura_auth_status(now=NOW)["state"] == "ok"

    repo._record_oura_auth_failure(oura.OuraAuthError("401"))
    st = repo.oura_auth_status(now=NOW)
    assert st["state"] == "rejected" and st["needs_authorisation"]


def test_sync_records_the_rejection_and_re_raises(monkeypatch):
    from services.repository import Repository

    repo = _repo(monkeypatch, oura_token="dead-pat")
    monkeypatch.setattr(Repository, "_sync_oura_daily",
                        lambda self, *a: (_ for _ in ()).throw(
                            oura.OuraAuthError("401: expired")))
    with pytest.raises(oura.OuraAuthError):
        repo.sync_oura_all(days=1)
    assert repo.oura_auth_status()["needs_authorisation"]


def test_a_successful_sync_clears_a_stale_rejection(monkeypatch):
    """Otherwise the banner would survive the re-authorisation that fixed it."""
    from services.repository import Repository

    repo = _repo(monkeypatch, oura_token="pat")
    repo._record_oura_auth_failure(oura.OuraAuthError("401"))
    monkeypatch.setattr(Repository, "_sync_oura_daily", lambda self, *a: 1)
    monkeypatch.setattr(Repository, "_sync_oura_events", lambda self, *a: 0)
    monkeypatch.setattr(Repository, "_mark_oura_tab_synced",
                        lambda self, *a, **k: None)
    # The event tabs resolve their worksheet as a call ARGUMENT, so stubbing
    # _sync_oura_events alone still reaches the live Sheets client.
    monkeypatch.setattr(Repository, "_ws", lambda self, *a, **k: None)
    repo.sync_oura_all(days=1)
    st = repo.oura_auth_status()
    assert st["rejected"] is None and not st["needs_authorisation"]


def test_status_flags_a_revoked_credential_as_needing_authorisation(monkeypatch):
    """The exact 2026-08-12 state: a credential that exists, cannot be
    renewed, and will never work again."""
    repo = _repo(monkeypatch, oura_token="")
    repo._store_oura_token(_token(refresh_token="", expires_at=NOW - timedelta(days=1)))
    st = repo.oura_auth_status(now=NOW)
    assert st["state"] == "expired" and st["needs_authorisation"]
