"""
scripts/authorize_oura.py — one-time Oura OAuth2 authorisation.

Oura retired Personal Access Tokens in December 2025. This project's PAT
stopped authenticating on 2026-08-12 and five nights of sleep went
unrecorded, so there is no longer a way to paste a static token into
secrets.toml — a credential has to be granted in a browser. This script is
that grant, and it should need running exactly once: everything after is
automatic refresh inside Repository._oc.

WHAT IT WRITES. The token pair goes to BOTH stores via
Repository.save_oura_oauth_token — .sync_state.json for speed and the Notion
Config DB for durability, because the hosted filesystem is wiped on redeploy
(key rule 18). Nothing is written to secrets.toml: the refresh token rotates
on every use and a rotating value cannot live in a file the deploy treats as
immutable.

THE REDIRECT URI IS THE ONE THING THAT WILL TRIP YOU UP, so the default is
the flow that needs no setup: leave --redirect-uri blank and the parameter is
omitted entirely, which OAuth2 permits for a client with a single registered
URI and which Oura then fills in from the application itself. Measured
against this application on 2026-08-17: omitting it reaches the consent
screen, while http://localhost:8765/callback, its https form and 127.0.0.1
are all rejected with a bare `400 invalid_request` naming neither the
expected nor the supplied value. So the registered URI is something other
than this machine, and guessing it is not worth the attempt.

That default implies --manual: with no local port to listen on, you consent
in the browser, land on whatever the application has registered, and paste
that URL back. The page there may well show an error — that does not matter.
The authorization code is in the query string, and the query string is all
this needs.

To use the loopback server instead, register a URI on the Oura application
first and then pass it, matching EXACTLY on scheme, host, port and path.

Usage:
    python scripts/authorize_oura.py                       # paste-back, no setup
    python scripts/authorize_oura.py --check               # probe status, change nothing
    python scripts/authorize_oura.py --redirect-uri http://localhost:8765/callback

Reads credentials from .streamlit/secrets.toml or environment variables via
services.config.load_config — nothing here imports streamlit.
"""

from __future__ import annotations

import argparse
import http.server
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The athlete runs this on Windows, where the console is cp1252 and a stray
# emoji is an UnicodeEncodeError that kills the script AFTER the network call
# it was reporting on. Ask for UTF-8, and fall back to replacing what cannot
# be encoded - a mangled glyph beats a traceback over a print. Output below
# stays ASCII anyway; this is the belt to that braces.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from services import oura_auth                       # noqa: E402
from services.clients import oura                    # noqa: E402
from services.config import load_config              # noqa: E402
from services.repository import Repository           # noqa: E402

DEFAULT_REDIRECT_URI = "http://localhost:8765/callback"


def _load_overrides() -> dict:
    """secrets.toml as a plain dict, matching what repo.py hands load_config.

    Falls back to environment variables (an empty overrides dict) when the
    file is absent, which is the hosted case.
    """
    path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:                       # pragma: no cover - py<3.11
        import tomli as tomllib                       # type: ignore
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    overrides = {k: v for k, v in data.items() if isinstance(v, str)}
    if "google_service_account" in data:
        overrides["google_service_account"] = data["google_service_account"]
    return overrides


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Catches the single redirect and hands the query back on the class.

    Deliberately answers ANY path rather than only the registered one: a
    mismatch between the path Oura redirects to and the path this checks
    would hang forever with no message, which is a worse failure than
    accepting a request meant for something else on a loopback port that
    exists for two seconds.
    """

    query: dict | None = None

    def do_GET(self):                                  # noqa: N802 - stdlib API
        parsed = urllib.parse.urlparse(self.path)
        _CallbackHandler.query = dict(urllib.parse.parse_qsl(parsed.query))
        ok = "code" in _CallbackHandler.query
        body = (
            "<h2>Oura authorised.</h2><p>You can close this tab and return "
            "to the terminal.</p>" if ok else
            f"<h2>Authorisation failed.</h2><pre>{_CallbackHandler.query}</pre>"
        )
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *_args):                     # noqa: D102 - silence stdlib logging
        return


def _catch_redirect(redirect_uri: str, timeout: float) -> dict:
    parsed = urllib.parse.urlparse(redirect_uri)
    server = http.server.HTTPServer((parsed.hostname or "localhost", parsed.port or 80),
                                    _CallbackHandler)
    server.timeout = timeout
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout)
    server.server_close()
    if _CallbackHandler.query is None:
        raise SystemExit(
            f"Timed out after {timeout:.0f}s waiting for the redirect to {redirect_uri}.\n"
            "Most likely the redirect URI registered on the Oura application does not "
            "match. Check it at https://cloud.ouraring.com/oauth/applications, or "
            "re-run with --manual."
        )
    return _CallbackHandler.query


def _report(repo: Repository, probe: bool = False) -> None:
    """Print the credential's status.

    `probe` makes one live /personal_info call. It is the default for --check
    because the stored value cannot answer the question on its own: a
    Personal Access Token carries no expiry, so a revoked one looks exactly
    like a healthy one until Oura is actually asked. That gap is the whole
    reason the 2026-08-12 outage ran for five days.
    """
    st = repo.oura_auth_status()
    print(f"  credential kind : {st['kind']}")
    print(f"  state           : {st['state']}")
    print(f"  oauth configured: {st['oauth_configured']}")
    if st.get("expires_at"):
        print(f"  expires at      : {st['expires_at']}")
    if st.get("scope"):
        print(f"  scope           : {st['scope']}")
    if st.get("persist_error"):
        print(f"  [!] durable store : {st['persist_error']}")
    if st.get("rejected"):
        print(f"  [!] last rejected : {st['rejected']}")
    if probe:
        token = repo._oc
        if not token:
            print("  live probe      : no credential to test")
        else:
            try:
                oura.verify_token(token)
                print("  live probe      : OK - authenticates against /personal_info")
            except oura.OuraAuthError as exc:
                # Record it, so the app's Home banner reflects what this
                # probe just learned instead of waiting for the next sync to
                # rediscover it.
                repo._record_oura_auth_failure(exc)
                print(f"  live probe      : REJECTED - {exc}")
                st = repo.oura_auth_status()
            except Exception as exc:
                print(f"  live probe      : could not reach Oura ({exc})")
    if st["needs_authorisation"]:
        print("  -> re-authorisation required (run this script without --check)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--redirect-uri", default="",
                    help="must match the Oura application EXACTLY. Default is blank, "
                         "which omits the parameter and lets Oura use the application's "
                         "own registered URI — the only flow this application currently "
                         f"accepts. Pass e.g. {DEFAULT_REDIRECT_URI} only after "
                         "registering it at cloud.ouraring.com/oauth/applications.")
    ap.add_argument("--manual", action="store_true",
                    help="print the URL and paste the redirect back, instead of serving. "
                         "Implied when --redirect-uri is blank, since there is no known "
                         "local port to listen on.")
    ap.add_argument("--check", action="store_true",
                    help="report the stored credential's status and exit")
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="seconds to wait for the redirect (default 180)")
    ap.add_argument("--scopes", default=" ".join(oura_auth.DEFAULT_SCOPES),
                    help="space-separated scopes to request")
    args = ap.parse_args()

    config = load_config(_load_overrides())
    repo = Repository(config)

    if args.check:
        print("Oura credential status:")
        _report(repo, probe=True)
        return 0

    if not config.oura_client_id or not config.oura_client_secret:
        print("No Oura OAuth application configured.\n"
              "Set OURA_CLIENT_ID and OURA_CLIENT_SECRET (or CLIENT_ID/CLIENT_SECRET) "
              "in .streamlit/secrets.toml. Register an application at "
              "https://cloud.ouraring.com/oauth/applications.", file=sys.stderr)
        return 2

    # A fresh random state per run, checked on the way back. This is the only
    # thing tying the redirect to the request that caused it.
    state = secrets.token_urlsafe(24)
    url = oura.authorize_url(config.oura_client_id, args.redirect_uri,
                             args.scopes.split(), state)

    # Blank redirect URI means Oura picks the registered one, so there is no
    # port here to listen on — serving would wait for a redirect that is
    # going somewhere else entirely, and time out after three minutes with a
    # message about a mismatch that isn't the problem.
    manual = args.manual or not args.redirect_uri

    print("Authorise this app against your Oura account:\n")
    print(f"  {url}\n")
    if args.redirect_uri:
        print(f"Redirect URI in use: {args.redirect_uri}")
        print("It must be registered EXACTLY at "
              "https://cloud.ouraring.com/oauth/applications\n")
    else:
        print("Redirect URI: omitted - Oura will use the one registered on the")
        print("application, and your browser will land there after you consent.")
        print("Copy that URL from the address bar even if the page itself errors:")
        print("the authorization code is in the query string, which is all that")
        print("is needed here.\n")

    if manual:
        try:
            webbrowser.open(url)
        except Exception:
            pass  # Printing the URL above is the real interface.
        landed = input("Paste the full URL your browser landed on:\n> ").strip()
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(landed).query))
    else:
        try:
            webbrowser.open(url)
        except Exception:
            pass  # Printing the URL above is the real interface; opening is a courtesy.
        print(f"Waiting up to {args.timeout:.0f}s for the redirect...")
        query = _catch_redirect(args.redirect_uri, args.timeout)

    if query.get("error"):
        print(f"Oura refused authorisation: {query.get('error')} "
              f"{query.get('error_description', '')}".strip(), file=sys.stderr)
        return 1
    code = query.get("code")
    if not code:
        print(f"No authorization code came back. Received: {sorted(query)}", file=sys.stderr)
        return 1
    if query.get("state") != state:
        # Refuse rather than warn. A mismatched state means this redirect is
        # not the answer to the request just made, and exchanging it would
        # bind the app to a credential of unknown origin.
        print("State mismatch - this redirect does not belong to this request. "
              "Nothing was stored; run the script again.", file=sys.stderr)
        return 1

    print("Exchanging the code for a token pair...")
    try:
        payload = oura.exchange_code(config.oura_client_id, config.oura_client_secret,
                                     code, args.redirect_uri)
    except oura.OuraAuthError as exc:
        print(f"Exchange failed: {exc}", file=sys.stderr)
        return 1

    token = repo.save_oura_oauth_token(payload)

    # Prove it works before claiming success - the whole reason this script
    # exists is that a credential which looks fine and is not cost five days
    # of data.
    try:
        oura.verify_token(token.access_token)
    except oura.OuraAuthError as exc:
        print(f"[!] Stored, but the new token did not authenticate: {exc}", file=sys.stderr)
        return 1

    print("\nOK - Authorised, stored and verified against /personal_info.\n")
    _report(repo)
    print("\nNext: backfill the nights missed while the old credential was dead:")
    print("  python scripts/backfill_oura_history.py --apply --range <start>:<end>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
