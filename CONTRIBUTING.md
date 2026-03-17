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

### Local Testing Commands

Before submitting a PR, run these checks locally:

```bash
# Install development dependencies
pip install -r requirements-dev.txt
sudo apt-get install shellcheck

# Run linters
python -m black --check src tests
python -m isort --check-only src tests
python -m flake8 src tests
python -m mypy src
shellcheck scripts/*.sh

# Run tests
PYTHONPATH=src pytest -q

# Run security scans
python -m bandit -r src
pip-audit -r requirements.txt -r requirements-dev.txt

# Compile sources
python -m compileall -q src
```

## 7. CI/CD Workflows

### Understanding GitHub Actions

The repository uses modular GitHub Actions workflows. See [.github/WORKFLOWS.md](.github/WORKFLOWS.md) for complete documentation.

### Key Workflows

1. **CI** (`.github/workflows/ci.yml`): Main CI with lint, test (Python 3.9-3.12), build, package
2. **Security Scan**: Bandit + pip-audit (runs on PR and weekly)
3. **CodeQL**: Advanced security analysis (runs on PR and weekly)
4. **PR Labeler**: Auto-labels PRs based on changed files

### Workflow Triggers

Most workflows trigger on:
- Push to `main`, `feature/**`, `hotfix/**`, `release/**`, `bugfix/**`, `chore/**`, and `refactor/**` branches
- Pull requests to `main` branch
- Manual dispatch (for testing)
- Scheduled runs (for security/compliance)

### Testing Workflow Changes

1. Make changes to workflow files in `.github/workflows/`
2. Push to your branch
3. Use "Run workflow" in the Actions tab to test manually
4. Verify all checks pass before merging

### Workflow Best Practices

- Keep workflows modular and reusable
- Use appropriate permissions (least-privilege)
- Add `workflow_dispatch` for manual testing
- Document any new workflows in WORKFLOWS.md
- Pin action versions to major versions (e.g., `@v4`)
- Use caching to speed up workflows

## 8. Copilot Workspace Customizations

This repository includes workspace-level Copilot customization files under `.github/`.

### Instructions

- `.github/instructions/xnetvn_monitord-python.instructions.md`
- `.github/instructions/xnetvn_monitord-ops.instructions.md`
- `.github/instructions/xnetvn_monitord-readme.instructions.md`
- `.github/instructions/xnetvn_monitord-docs.instructions.md`
- `.github/instructions/xnetvn_monitord-github-workflows.instructions.md`

### Prompts

- `.github/prompts/sync-monitor-docs.prompt.md` for documentation synchronization
- `.github/prompts/release-readiness.prompt.md` for pre-release checks

### Agents

- `.github/agents/ops-safety-review.agent.md` for operational safety reviews
- `.github/agents/release-readiness-review.agent.md` for release readiness reviews

Use these workspace customizations when changing Python code, tests, install/update
scripts, documentation, or GitHub Actions so the repository-specific rules are
consistently applied.

## 9. Pull Request checklist

- [ ] Tests have been run
- [ ] Documentation has been updated
- [ ] No secrets are included
- [ ] The change description is clear
