"""COBOL-vs-FastAPI parity harness (port of src/programs/test/TSTVAL00.cbl).

``python -m parity`` runs every case in :mod:`parity.suite` against the ported
services it is given and writes the TSTVAL00 listing plus a structured diff
report. Cases whose ported service does not exist yet are reported as blocked
against their ticket.
"""
