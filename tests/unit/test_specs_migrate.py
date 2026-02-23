from __future__ import annotations

from pathlib import Path

import yaml

from trajectly.specs.migrate import migrate_spec_file


def test_migrate_spec_file_writes_v03_payload(tmp_path: Path) -> None:
    legacy_spec = tmp_path / "legacy.agent.yaml"
    legacy_spec.write_text(
        """
name: legacy-demo
command: python agent.py
workdir: .
fixture_policy: by_hash
strict: true
contracts:
  tools:
    deny: [delete_account]
""".strip(),
        encoding="utf-8",
    )

    destination = migrate_spec_file(spec_path=legacy_spec, output_path=None, in_place=False)
    assert destination.exists()
    assert destination.name == "legacy.agent.v03.yaml"

    payload = yaml.safe_load(destination.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "0.3"
    assert payload["name"] == "legacy-demo"
    assert payload["contracts"]["tools"]["deny"] == ["delete_account"]
    assert "refinement" in payload
    assert "replay" in payload


def test_migrate_spec_file_in_place_rewrites_source(tmp_path: Path) -> None:
    legacy_spec = tmp_path / "inplace.agent.yaml"
    legacy_spec.write_text(
        """
name: in-place-demo
command: python agent.py
""".strip(),
        encoding="utf-8",
    )

    destination = migrate_spec_file(spec_path=legacy_spec, output_path=None, in_place=True)
    assert destination == legacy_spec
    payload = yaml.safe_load(legacy_spec.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "0.3"
