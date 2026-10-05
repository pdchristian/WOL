"""Ensure the two version lines in wol_app/__init__.py match their build files.

``__version__``     desktop line: Windows (setup.iss), Ubuntu (deb reads
                    ``__version__`` directly), macOS (PyInstaller spec), docs.
``MOBILE_VERSION``  mobile line: Android (build.gradle.kts, WebApp fallbacks)
                    and iOS (project.yml, WebApp fallbacks, Bridge.swift).

The lines may differ on purpose — a desktop-only feature does not change the
mobile clients, so their release number stays where it was.

Run manually: ``python update_version.py --check``
Bump desktop: ``python update_version.py 2.4.0``
Bump mobile:  ``python update_version.py --mobile 2.3.8``
"""

import update_docs_version as sync
import update_version


class TestVersionSync:
    def test_source_version_valid(self):
        for version in (sync.read_version(), sync.read_mobile_version()):
            parts = version.split(".")
            assert len(parts) == 3, f"expected X.Y.Z, got {version}"
            assert all(p.isdigit() for p in parts)

    def test_all_variants_match_source(self):
        drift = update_version.check()
        assert not drift, (
            f"Version drift vs. {sync.VERSION_SOURCE.name} "
            f"(desktop {sync.read_version()} / "
            f"mobile {sync.read_mobile_version()}):\n" + "\n".join(drift)
        )

    def test_mobile_files_follow_the_mobile_line(self):
        """The WebView clients must never be synced to the desktop version."""
        mobile_files = {
            "android_html/app/build.gradle.kts",
            "ios/project.yml",
            "ios/WebApp/app.js",
            "ios/WebApp/bridge.js",
            "android_html/app/src/main/assets/app/app.js",
            "android_html/app/src/main/assets/app/bridge.js",
            "ios/WolManager/WebView/Bridge.swift",
        }
        assert mobile_files <= set(sync.MOBILE_PATTERNS)
        assert not (mobile_files & set(sync.DOC_PATTERNS))

    def test_mobile_files_are_written_by_the_sync(self, tmp_path, monkeypatch):
        """Propagation must apply MOBILE_PATTERNS, not only the desktop table.

        Guarding the bug where ``update_file`` always looked the file up in
        ``DOC_PATTERNS``, so every Android/iOS file was silently reported as
        "already in sync" while keeping its old versionName.
        """
        # Arrange
        source = tmp_path / "wol_app" / "__init__.py"
        source.parent.mkdir(parents=True)
        source.write_text('__version__ = "1.2.3"\nMOBILE_VERSION = "9.9.9"\n',
                          encoding="utf-8")
        gradle = tmp_path / "android_html" / "app" / "build.gradle.kts"
        gradle.parent.mkdir(parents=True)
        gradle.write_text('versionName = "1.0.0"\n', encoding="utf-8")
        monkeypatch.setattr(sync, "ROOT", tmp_path)
        monkeypatch.setattr(sync, "VERSION_SOURCE", source)

        # Act
        sync.main()

        # Assert
        assert 'versionName = "9.9.9"' in gradle.read_text(encoding="utf-8")

    def test_mobile_drift_is_detected(self, monkeypatch):
        """A stale Android version is reported against MOBILE_VERSION."""
        monkeypatch.setattr(sync, "read_mobile_version", lambda: "0.0.1")
        drift = update_version.check()
        assert any("build.gradle.kts" in line for line in drift), drift

    def test_desktop_drift_is_detected(self, monkeypatch):
        monkeypatch.setattr(sync, "read_version", lambda: "0.0.1")
        drift = update_version.check()
        assert any("setup.iss" in line for line in drift), drift

    def test_check_function_detects_drift(self, tmp_path, monkeypatch):
        """The drift detector itself must actually catch mismatches."""
        # Arrange: minimal tree with the source version and one stale build file.
        source = tmp_path / "wol_app" / "__init__.py"
        source.parent.mkdir(parents=True)
        source.write_text('__version__ = "9.9.9"\nMOBILE_VERSION = "9.9.9"\n',
                          encoding="utf-8")
        (tmp_path / "setup.iss").write_text('#define AppVersion "1.0.0"\n', encoding="utf-8")
        monkeypatch.setattr(sync, "ROOT", tmp_path)
        monkeypatch.setattr(sync, "VERSION_SOURCE", source)

        # Act
        drift = update_version.check()

        # Assert
        assert drift, "drift detector found no mismatch"
        assert any("1.0.0" in line for line in drift)
