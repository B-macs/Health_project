"""
services — framework-agnostic backend access + business logic.

Zero Streamlit imports anywhere in this package (enforced by
tests/test_no_streamlit_in_services.py). The Streamlit app is one consumer of
this package; a future FastAPI service would be another, using the same
services/config.py env-var loading path.
"""
