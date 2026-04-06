---
name: Skills Management & Registry
description: Manage, discover, and maintain the skills catalog with versioning and dependency tracking.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [16-verification-qa]
---

# SKILL 00 — Skills Management & Registry

## Overview

This skill defines the standard process for managing the skills catalog. It covers adding new skills, tracking dependencies, versioning, and discovering skills by tag or source file.

**When to use:** Whenever creating, modifying, or searching for a skill document.

## Directory Structure

```
_agent/skills/
├── skills-en/           ← Primary (English)
│   ├── 00-skills-management/SKILL.md
│   ├── 01-pyside6-dark-theme/SKILL.md
│   └── ...
├── skills-ko/           ← Reference (Korean)
│   ├── 00-스킬-관리/SKILL.md
│   └── ...
└── registry.json        ← Master index
```

## Registry Schema (`registry.json`)

```json
{
  "version": "1.0",
  "updated": "2026-03-10",
  "skills": [
    {
      "id": "00",
      "folder_en": "00-skills-management",
      "folder_ko": "00-스킬-관리",
      "name": "Skills Management & Registry",
      "description": "Manage, discover, and maintain the skills catalog.",
      "version": "1.0",
      "tags": ["meta", "management", "registry"],
      "dependencies": ["16-verification-qa"],
      "source_files": []
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Two-digit ID (`"00"`, `"01"`, …) |
| `folder_en` | string | Directory name under `skills-en/` |
| `folder_ko` | string | Directory name under `skills-ko/` |
| `name` | string | Human-readable skill name |
| `version` | string | Semantic version (`major.minor`) |
| `tags` | string[] | Searchable keywords |
| `dependencies` | string[] | Required skill folder names |
| `source_files` | string[] | Relative paths from `src/` |

## Adding a New Skill

### Step 1 — Assign an ID
Use the next sequential two-digit number. IDs are **never reused**.

### Step 2 — Create SKILL.md

Template:
```yaml
---
name: [Skill Name]
description: [One-line description]
version: 1.0
project_origin: [Project Name]
related_skills: [list of related skill folder names]
---
```

Required sections: Overview, Tech Stack, Architecture, Core Patterns, Code Examples, Pitfalls & Gotchas, Testing Checklist, Related Files.

### Step 3 — Update Registry
Add the new entry to `registry.json`.

### Step 4 — Verify
Run SKILL 16 verification checklist.

## Dependency Graph

```mermaid
graph TD
    S00["00 Skills Mgmt"] --> S16["16 Verification"]
    S06["06 CSV Parser"] --> S07["07 Statistics"]
    S07 --> S08["08 Die Analysis"]
    S08 --> S05["05 Wafer Map"]
    S05 --> S04["04 3D Surface"]
    S07 --> S02["02 Matplotlib"]
    S08 --> S03["03 PyQtGraph"]
    S01["01 Dark Theme"] --> S11["11 Custom Widgets"]
    S11 --> S12["12 MVC Mixin"]
    S12 --> S13["13 Threading"]
    S06 --> S15["15 Multi-Recipe"]
    S09["09 Export"] --> S12
    S10["10 TIFF Loader"] --> S12
    S14["14 Settings"] --> S12
```

## Version Bump Rules

| Change Type | Bump | Example |
|-------------|:----:|---------|
| Typo fix, formatting | None | — |
| New code example | Minor | 1.0 → 1.1 |
| New pattern/API | Major | 1.2 → 2.0 |
| Skill split/merged | Major | New ID |

## Pitfalls & Gotchas

- **Never delete a skill ID.** Mark deprecated with `"deprecated": true`.
- **Korean versions are summaries**, not literal translations.
- **Keep `registry.json` in sync** — always update when modifying skills.

## Testing Checklist

- [ ] `registry.json` valid JSON
- [ ] All `folder_en` entries match existing directories
- [ ] All `source_files` point to existing paths
- [ ] Skill count matches directory count
- [ ] No duplicate IDs
