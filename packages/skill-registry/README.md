# inkstatute-skill-registry

Read-only Skill Registry that exposes Hermes skill metadata from solution-pack
manifests as `NeutralSkillDescriptor` records.

## Overview

This package provides:

- **`manifest_skill_to_descriptor`** — Maps a manifest skill dict to a
  `NeutralSkillDescriptor` with `skill_id` derived as `{solution_id}/{name}`.
- **`load_skills_from_manifests`** — Loads all skills from one or more
  solution-pack manifest JSON files.
- **`SkillRegistry`** — Read-only registry with `list_skills()`, `get_skill()`,
  and `search()` operations. No write/update/delete methods are exposed.

## Design

- The registry is constructed with a pre-loaded list of descriptors. No I/O
  occurs at query time.
- Read-only enforcement is structural: the `SkillRegistryPort` Protocol and the
  `SkillRegistry` class expose only query methods.
- Skill metadata is sourced from `solutions/*/manifest.json` files, not from a
  live Hermes API.
