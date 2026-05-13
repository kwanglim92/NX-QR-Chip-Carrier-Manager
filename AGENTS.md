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

## Workspace Operating Mode

- 기본 작업 위치는 메인 워크트리 `C:\Users\Spare\Desktop\03. Program\새 폴더`이다.
- 별도 지시가 없으면 코드 수정, 실행, 테스트, GUI 확인은 모두 메인 워크트리 기준으로 수행한다.
- 작업 시작 전 메인 워크트리에서 `git status --short --branch`를 확인한다.
- 새 기능 작업 전에는 메인 워크트리에 체크포인트 커밋을 만들거나, 이미 미커밋 변경이 있으면 해당 변경의 소유권과 커밋 시점을 먼저 확인한다.
- Codex 임시 워크트리(`C:\Users\Spare\.codex\worktrees\...`)는 실험/격리용으로만 보고, 최신 메인 변경을 덮는 브릿지 소스로 사용하지 않는다.
- Codex와 Claude를 병행할 때는 같은 파일을 동시에 수정하지 않는다. 한쪽이 구현 중이면 다른 쪽은 리뷰/검증을 담당하거나 기능 단위로 파일 소유권을 나눈다.
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
