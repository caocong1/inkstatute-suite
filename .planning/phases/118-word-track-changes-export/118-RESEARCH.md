---
phase: 118-word-track-changes-export
research: embeddable-python-lxml
date: 2026-08-14
status: complete
---

# Phase 118 Research: Embeddable Python + lxml Compatibility

## Question

What is the size of Windows embeddable Python with lxml, and what is the degradation plan if the size exceeds the limit?

## Findings

### Windows Embeddable Python

- **Base size**: ~10MB (python-3.12-embed-amd64.zip)
- **With lxml**: lxml wheel for Windows is ~4-5MB
- **Total estimated**: ~15-20MB (compressed), ~40-50MB (uncompressed)
- **Compatibility**: lxml is compatible with Windows embeddable Python. The embeddable distribution supports installing packages via pip with `--target` flag.

### lxml Dependency

- lxml is the only external dependency for `contract_review_trackchanges_v4.py`
- Standard library modules used: zipfile, os, sys, json, copy, datetime, re
- lxml is used for OOXML (XML) manipulation — parsing, creating, and serializing Word document XML

### Degradation Plan (if size exceeds limit)

If the total size exceeds 50MB:

1. **Option A: Pure-Python XML alternative** — Replace lxml with `xml.etree.ElementTree` (standard library). This eliminates the lxml dependency entirely. Trade-off: ElementTree has limited namespace support and no pretty-printing, but the track-changes script's XML operations are simple enough for ElementTree.

2. **Option B: Minimized lxml** — Use a stripped-down lxml build with only the etree module (no html, objectify, etc.). This reduces the lxml wheel size by ~30%.

3. **Option C: Separate download** — Ship the embeddable Python as a separate download during first-run setup, rather than bundling it in the installer. This keeps the main installer small.

### Recommendation

**Option A (pure-Python ElementTree)** is the preferred degradation path because:
- Zero external dependencies
- Standard library only — no additional packaging
- The track-changes script's XML operations (find, create, replace elements) are well within ElementTree's capabilities
- Namespace handling can be done with explicit namespace maps

The current V4 script uses lxml for `etree.fromstring`, `etree.tostring`, `etree.SubElement`, `etree.Element`, and `findall` — all of which have ElementTree equivalents.

## Conclusion

- **Primary plan**: Bundle Windows embeddable Python + lxml (~15-20MB compressed)
- **Degradation**: Replace lxml with xml.etree.ElementTree (zero external dependencies)
- **Size limit**: 50MB uncompressed for the Python runtime
- **No blocker**: Both plans are viable; the degradation path is straightforward
