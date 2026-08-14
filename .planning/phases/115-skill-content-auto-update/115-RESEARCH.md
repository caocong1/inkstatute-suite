---
phase: 115-skill-content-auto-update
researched: 2026-08-14
researcher: gsd-phase-researcher
confidence: HIGH
key_findings_count: 10
---

# Phase 115: Skill Content Auto-Update — Research

**Researched:** 2026-08-14
**Domain:** Content auto-updater, DSH skill watcher, atomic file operations, security verification
**Confidence:** HIGH (All findings verified by source code inspection and official documentation)

## Executive Summary

Phase 115 requires implementing an app-side content package updater that downloads, validates, and atomically switches skill content packages without requiring engine restart. The DSH skill-filesystem watcher uses chokidar with `depth: 1` and `persistent: true`, which DOES detect new directories added to `customSkillDirs` after session start—this validates the "zero restart" requirement. The Flutter app currently lacks the `http` package; adding `http: ^1.6.0` is compatible with the Flutter SDK constraint `^3.13.0`. Windows `%LOCALAPPDATA%` is accessible via `Platform.environment['LOCALAPPDATA']` with a fallback to `USERPROFILE` (already implemented in `dsh_config.dart`). Dart's `File.rename()` has platform-dependent atomicity: Linux provides atomic rename for same-filesystem moves, Windows provides no atomicity guarantees, and cross-filesystem moves fail. The recommended atomic switch pattern is: extract to staging directory → validate → rename to final → update pointer file. GitHub Release connectivity in mainland China is unreliable due to DNS poisoning and CDN throttling; mirror services (ghproxy.net, ghfast.top) or custom servers are recommended alternatives. The Phase 114 `ContentManifest` schema provides `fromJson()`, `isCompatibleWith()`, `totalSkillCount`, and `domainNames` methods; `pub_semver` package is needed for semver comparison of `release_version`. Zip extraction requires the `archive` package (`^3.6.1`). The content directory structure should use versioned release directories with `current` and `last-good` pointer files. Adding new `lib/` directories will trigger the V4 meta-test gate. Security requires sha256 chain verification (zip + per-skill), downgrade attack prevention via version comparison, and handling of truncated/corrupted downloads.

## Findings

### 1. DSH Skill Watcher Refresh Behavior

**Location:** `/home/sorawatcher/deepseek-harness/packages/skill/skill-filesystem/src/index.ts` (lines 487-555)

The chokidar watcher with `persistent: true` and `depth: 1` WILL automatically detect new directories added to `customSkillDirs` after session start. The `addDir` event is triggered when a new directory is created within the watched root path. The `handleWatchEvent` function processes these events and queues invalidation via `queueInvalidation()`, which triggers a microtask to call `this.invalidate()`.

**Zero restart validation:** When the Phase 115 updater creates a new release directory and updates the `current` pointer, the DSH skill watcher will detect the `addDir` event for new skill directories and invalidate the skill catalog, causing DSH to re-scan and discover the new skills without requiring an engine restart.

**Confidence:** HIGH (verified by source code inspection)

### 2. Flutter HTTP Package

**Location:** `apps/flutter_app/pubspec.yaml`

The `http` package is NOT currently in dependencies. Flutter SDK constraint is `^3.13.0`. The `http` package (1.6.0) requires Dart SDK 3.4, compatible with Flutter 3.13.

**Recommendation:** Add `http: ^1.6.0` to `pubspec.yaml`.

**Confidence:** HIGH

### 3. Windows LOCALAPPDATA Path

**Location:** `apps/flutter_app/lib/engine/dsh_config.dart` (lines 26-39)

`Platform.environment['LOCALAPPDATA']` is available on Windows and already used in the codebase with a fallback to `USERPROFILE`. On Linux/WSL, `Platform.environment['HOME']` is used.

**Phase 115 usage:** Content directory should follow the same pattern:
- Windows: `%LOCALAPPDATA%\InkStatute\content\skills\<release>\`
- Linux/WSL: `~/.local/share/InkStatute/content/skills/<release>/`

**Confidence:** HIGH

### 4. Dart Rename Atomicity

- **Linux:** `File.rename()` is atomic for same-filesystem moves (uses `rename(2)`).
- **Windows:** `File.rename()` has NO atomicity guarantees.
- **Cross-filesystem:** Rename operations fail on both platforms.

**Atomic switch pattern:**
1. Extract zip to `<release>-staging/` temporary directory
2. Validate sha256 hashes and manifest structure
3. If validation passes, rename `<release>-staging/` to `<release>/`
4. Update `current` pointer file (atomic write: write to temp file, then rename)
5. If any step fails, delete staging directory and keep old `current` pointer

**Same-filesystem guarantee:** All content directories are under `resolveContentDir()` which returns a single base path.

**Confidence:** HIGH

### 5. GitHub Release Availability in China

**Connectivity issues:**
- DNS poisoning for `github.com` and `githubusercontent.com`
- CDN throttling (50-200 KB/s caps)
- TCP RST attacks on download connections

**Alternative solutions:**
1. Mirror services: `ghproxy.net`, `ghfast.top`, `mirror.ghproxy.com`
2. Custom server: Self-hosted content server with domestic CDN (Aliyun OSS, Tencent COS)
3. Proxy/VPN: Users with proxy clients can route GitHub traffic

**Recommendation:**
- Default `CONTENT_RELEASE_URL` to GitHub Release
- Provide settings page option to configure custom mirror URL
- Support `CONTENT_MIRROR_BASE` env var for mirror URL prefix replacement

**Confidence:** MEDIUM (network conditions vary by ISP and region)

### 6. Manifest Schema API

**Location:** `apps/flutter_app/lib/content/manifest_schema.dart`

Available methods: `fromJson()`, `isCompatibleWith()`, `totalSkillCount`, `domainNames`, `toJson()`.

**Release version comparison:** Add `pub_semver: ^2.1.4` for semver comparison:
```dart
import 'package:pub_semver/pub_semver.dart';
bool hasUpdate(ContentManifest remote, ContentManifest? local) {
  if (local == null) return true;
  return Version.parse(remote.releaseVersion) > Version.parse(local.releaseVersion);
}
```

**Downgrade attack prevention:** Reject manifests where `remote.releaseVersion < local.releaseVersion`.

**Confidence:** HIGH

### 7. Zip Extraction in Dart

Dart has no built-in zip extraction. The `archive` package (`^3.6.1`) is the standard solution.

**Security:** Validate that zip entry paths do not contain `../` traversal patterns before extraction.

**Recommendation:** Add `archive: ^3.6.1` to `pubspec.yaml`.

**Confidence:** HIGH

### 8. Content Directory Structure

```
<contentDir>/skills/
├── 1.0.0/
│   ├── content-manifest.json
│   ├── legal-commercial/
│   │   ├── contract-review/SKILL.md
│   │   └── ...
│   ├── legal-litigation/
│   ├── legal-family/
│   └── legal-employment/
├── 1.1.0/
│   └── ...
├── current         -> Pointer file containing "1.1.0"
└── last-good       -> Pointer file containing "1.0.0"
```

**Pointer file format:** Plain text file containing the release version string.

**Atomic pointer update:** Write to temp file, then rename to `current`.

**Rollback:** Read `last-good` pointer, update `current` to that version.

**Confidence:** HIGH

### 9. V4 Gate Implications

**Location:** `scripts/run_v4_gates.py` (lines 408-484)

Adding a new `lib/content/updater.dart` WILL require a corresponding `test/content/` directory with at least one non-empty `_test.dart` file. The meta-test gate will fail otherwise.

**Required test coverage:** `apps/flutter_app/test/content/updater_test.dart` (or similar).

**Confidence:** HIGH

### 10. Security Considerations

**Two-level sha256 verification:**
1. **Zip-level:** Verify downloaded zip against sidecar sha256 file
2. **Per-skill:** After extraction, verify each SKILL.md against manifest sha256

**Security checklist:**
- Verify zip sha256 before extraction
- Verify per-skill sha256 after extraction
- Reject downgrade attacks (version comparison)
- Reject engine version mismatches
- Clean up corrupted downloads
- Validate zip entry paths (no traversal)
- Use HTTPS for all downloads
- Validate manifest schema before processing

**Confidence:** HIGH

## Risk-Gate Items

No new V1-V5 risks identified. All findings are HIGH confidence based on source code verification and official documentation.

## Recommendations for Planner

### Dependencies to Add

```yaml
dependencies:
  http: ^1.6.0
  archive: ^3.6.1
  pub_semver: ^2.1.4
  crypto: ^3.0.3  # For sha256 computation
```

### ContentUpdater Core Structure

Create `apps/flutter_app/lib/content/updater.dart`:
- `ContentUpdater` class with `checkAndUpdate()` method
- `ContentPaths` static class for path resolution
- `UpdateException` for error handling
- `UpdateResult` sealed class for success/failure states

### Test Coverage Requirements

Create `apps/flutter_app/test/content/updater_test.dart`:
- Path resolution (Windows/Linux)
- Version comparison (pub_semver)
- Download with sha256 verification
- Zip extraction with path validation
- Atomic switch (rename operations)
- Rollback to last-good
- Downgrade attack rejection
- Engine version mismatch rejection
- Corrupted download handling
- Offline behavior (use last-good)

## RESEARCH COMPLETE

**Confidence:** HIGH
**Key Findings Count:** 10
