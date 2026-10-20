"""The sync rehearsal's service (rebuild Phase 9): `uvicorn healthapi.rehearsal_service:app`.

Only the rehearsal service runs this module (scripts/sync_rehearsal.py deploys
it from the engine's image with this command). It refuses every outgoing
connection for the life of the process before anything else happens, then
serves healthapi.rehearsal's app: the engine's routes over a made-up store and
made-up devices. The engine itself never imports it.
"""

from __future__ import annotations

from .rehearsal import build_app, no_network

#: Entered once and never left: this process reaches no other machine.
_NO_NETWORK = no_network()
_NO_NETWORK.__enter__()

app = build_app()
