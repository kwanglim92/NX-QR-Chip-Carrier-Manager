# [Project Name]

## Project Context
- **Framework**: PySide6 + Matplotlib (Catppuccin Mocha dark theme)
- **Language**: Python 3.11+
- **Entry point**: `main.py` -> `src/` package

## Development Rules
코드를 작성하거나 수정하기 전에 반드시 `.agent/rules.md`를 읽고 따를 것.

핵심 규칙 요약:
1. 코딩 전 구현 계획을 먼저 세울 것
2. 요청하지 않은 추가 기능/추상화/에러 처리를 임의로 추가하지 말 것
3. 지시받은 목표 지점의 코드만 수정할 것
4. 구체적이고 검증 가능한 목표에 집중할 것
5. **Skill-First**: 코드 작성 전 `.agent/skills/registry.json`에서 관련 skill을 검색하고, 해당 SKILL.md의 패턴을 따를 것

## Skills Reference
- **Registry**: `.agent/skills/registry.json` (19개 skill, tags/dependencies/source_files 포함)
- **한국어 skill**: `.agent/skills/skills-ko/{폴더명}/SKILL.md`
- **영문 skill**: `.agent/skills/skills-en/{폴더명}/SKILL.md`

## Git Workflow (크기 기준 자동 판단)

단독 개발자 개인 리포이므로 PR은 **규모에 따라 선택적**. Codex는 작업 완료 시
아래 기준으로 자동 판단:

| 커밋 수 | 방식 | 흐름 |
|:------:|------|------|
| **1개** | main 직접 push | 커밋 → `git push origin main` |
| **2–4개** | 로컬 branch + fast-forward merge | `feat/xxx` 브랜치 → 커밋들 → `main` 으로 checkout → `merge --ff-only` → `push` → feat 브랜치 삭제 |
| **5개 이상** | PR 기반 | `feat/xxx` → push → GitHub PR → merge (revert 편의 + 이력 풍부) |

**예외**:
- 버그 수정·오타·문서 수정: 규모와 무관하게 **main 직접** (빠른 반영)
- 실험적/파괴적 변경: 규모와 무관하게 **PR** (쉬운 revert)
- 사용자가 명시적으로 방식 지정 시 그 지시를 우선

## Template Usage

새 프로젝트에 적용할 때:
1. `.agent/` 디렉토리를 프로젝트 루트에 복사
2. 이 `AGENTS.md`를 프로젝트 루트에 복사
3. 위의 `[Project Name]`과 `Project Context` 섹션을 프로젝트에 맞게 수정
4. `registry.json`의 `"project"` 필드를 프로젝트명으로 변경
5. 필요시 `source_files`를 프로젝트 실제 파일 구조에 맞게 조정

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
