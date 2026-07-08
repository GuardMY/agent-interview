# Repository Guidelines

## Documentation & Agent Notes

Documentation changes must update matching English and Chinese files, including `CHANGELOG.md` and `CHANGELOG-zh-CN.md` unless the edit is spelling-only. When `.codegraph/` exists, use CodeGraph before grep or manual file reads to understand code paths.

## Bilingual Documentation & Change Logs

Maintain all project documentation in English and Chinese. English files use `*.md`; Chinese files use matching `*-zh-CN.md` names. Both versions must express the same facts, scope, and acceptance criteria. For API, database, deployment, milestone, acceptance, or development-standard changes, always check the paired language file.

Every functional change, and every documentation-only change that affects meaning, must update `CHANGELOG.md` and `CHANGELOG-zh-CN.md`. Each entry must include the date, change type, affected modules, main changes, verification results, and unfinished items.

## Requirement Clarification Before Functional Changes

For any request that involves adding or changing functionality, ask the user one question at a time before answering with a final plan or implementation. Continue asking follow-up questions based on the user's answers until you have about 95% confidence that you fully understand the user's real needs, goals, boundaries, and acceptance criteria.
