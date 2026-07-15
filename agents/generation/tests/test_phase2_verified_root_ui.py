from agents.generation.phase2.monitor import INDEX_HTML


def test_verified_root_proof_spine_shows_integration_pending() -> None:
    assert 'const rootVerified = rootIntegrated || rootStatus === "informally_verified"' in INDEX_HTML
    assert "root strictly verified" in INDEX_HTML
    assert "integration pending" in INDEX_HTML
