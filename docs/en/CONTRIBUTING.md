---
post_title: "Contributing"
author1: "xNetVN Inc."
post_slug: "docs-en-contributing"
microsoft_alias: ""
featured_image: ""
categories:
	- governance
tags:
	- contributing
ai_note: "AI-assisted"
summary: "Contribution workflow and quality standards."
post_date: "2026-02-03"
---

## Contributing

## 1. General principles

- Ensure every change has a clear purpose and is tested.
- Do not commit sensitive information.
- Follow coding standards and the review workflow.

## 2. Contribution workflow

1. Fork the repository and create a new branch.
2. Make changes and update related documentation.
3. Run tests before submitting the PR.
4. Create a Pull Request using the template.

## 3. Branch naming rules

- feature/<issue-id>-short-description
- bugfix/<issue-id>-short-description
- hotfix/<issue-id>-short-description
- chore/<issue-id>-short-description

## 4. Commit messages

Follow Conventional Commits (in English):

- `feat(scope): add ...`
- `fix(scope): resolve ...`
- `chore(scope): update ...`

## 5. Code standards

- Python: PEP 8.
- Use formatters/linters (black, flake8, isort, mypy if applicable).

## 6. Testing

- Run `bash scripts/run_tests.sh`.
- Ensure unit/integration/security tests pass.

## 7. Workspace Copilot Customizations

This repository ships with Copilot workspace customizations under `.github/` to
help contributors and AI agents follow repository-specific rules.

### Instructions

- `.github/instructions/xnetvn_monitord-python.instructions.md`
- `.github/instructions/xnetvn_monitord-ops.instructions.md`
- `.github/instructions/xnetvn_monitord-readme.instructions.md`
- `.github/instructions/xnetvn_monitord-docs.instructions.md`
- `.github/instructions/xnetvn_monitord-github-workflows.instructions.md`

### Prompts

- `.github/prompts/sync-monitor-docs.prompt.md` for documentation sync
- `.github/prompts/release-readiness.prompt.md` for pre-release checks
- `.github/prompts/review-ops-change.prompt.md` for operational-risk review
- `.github/prompts/prepare-release-notes.prompt.md` for GitHub release notes drafting
- `.github/prompts/prepare-release-tag.prompt.md` for release version/tag preparation
- `.github/prompts/publish-release-via-tag.prompt.md` for automatic tag-driven release publishing
- `.github/prompts/sync-installation-docs.prompt.md` for installation/update documentation sync

### Agents

- `.github/agents/ops-safety-review.agent.md` for ops safety reviews
- `.github/agents/release-readiness-review.agent.md` for release readiness reviews

## 8. Pull Request checklist

- [ ] Tests have been run
- [ ] Documentation has been updated
- [ ] No secrets are included
- [ ] The change description is clear
