"""Verifies the type-classifier matches the n8n Differentiator JS node.

Importantly, the n8n IF node had an empty false-branch — sem types silently
returned nothing. We restore the sem path on this side, so confirm both
branches resolve.
"""

from app.crews.script_crew.crew import classify_type


def test_assignment_routes_to_weekly():
    assert classify_type("assignment") == "weekly"


def test_each_sem_type_routes_to_sem():
    for t in ["documentary", "shortfilm", "feature film", "episodic content"]:
        assert classify_type(t) == "sem", f"{t} should route to sem"


def test_unknown_type_returns_none():
    assert classify_type("random") is None
    assert classify_type("") is None
    assert classify_type(None) is None
