"""Ensure the version in wol_app/__init__.py (single source of truth) matches
every build file and document: Windows (setup.iss), Ubuntu (deb build reads
__version__ directly), Android (build.gradle.kts, WebApp fallbacks) and iOS
(project.yml, WebApp fallbacks, Bridge.swift).

Run manually: ``python update_version.py --check``
Bump everywhere: ``python update_version.py 2.3.5``
"""

import update_docs_version as sync
import update_version


class TestVersionSync:
    def test_source_version_valid(self):
        version = sync.read_version()
        parts = version.split(".")
        assert len(parts) == 3, f"expected X.Y.Z, got {version}"
        assert all(p.isdigit() for p in parts)

    def test_all_variants_match_source(self):
        drift = update_version.check()
        assert not drift, (
            f"Version drift vs. {sync.VERSION_SOURCE.name} "
            f"({sync.read_version()}):\n" + "\n".join(drift)
        )

    def test_check_function_detects_drift(self, tmp_path, monkeypatch):
        """The drift detector itself must actually catch mismatches."""
        # Arrange: minimal tree with the source version and one stale build file.
        source = tmp_path / "wol_app" / "__init__.py"
        source.parent.mkdir(parents=True)
        source.write_text('__version__ = "9.9.9"\n', encoding="utf-8")
        (tmp_path / "setup.iss").write_text('#define AppVersion "1.0.0"\n', encoding="utf-8")
        monkeypatch.setattr(sync, "ROOT", tmp_path)
        monkeypatch.setattr(sync, "VERSION_SOURCE", source)

        # Act
        drift = update_version.check()

        # Assert
        assert drift, "drift detector found no mismatch"
        assert any("1.0.0" in line for line in drift)
