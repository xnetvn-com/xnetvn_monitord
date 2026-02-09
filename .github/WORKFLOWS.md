# GitHub Actions Workflows Documentation

This document describes all GitHub Actions workflows in the xnetvn_monitord repository.

## Workflow Architecture

The CI/CD pipeline is modular and organized into the following categories:

### 🔨 Core CI/CD Workflows

#### 1. CI (`.github/workflows/ci.yml`)
**Main continuous integration workflow**

- **Triggers**: Push to `main`, Pull requests to `main`, Manual dispatch
- **Jobs**:
  - `lint`: Code quality checks (Black, Isort, Flake8, Mypy, ShellCheck)
  - `tests`: Run pytest with coverage on Python 3.9, 3.10, 3.11, 3.12
  - `build`: Compile Python sources
  - `package`: Create source archive
- **Concurrency**: Cancels in-progress runs on new commits
- **Permissions**: `contents: read`

#### 2. CI Lint (`.github/workflows/ci-lint.yml`)
**Reusable linting workflow**

- **Triggers**: Workflow call, Manual dispatch
- **Tools**: Black, Isort, Flake8, Mypy, ShellCheck
- **Can be called by other workflows**: Yes

#### 3. CI Test (`.github/workflows/ci-test.yml`)
**Reusable testing workflow**

- **Triggers**: Workflow call, Manual dispatch
- **Python Version**: 3.11
- **Environment**: `PYTHONPATH=src`

#### 4. CI Build (`.github/workflows/ci-build.yml`)
**Reusable build workflow**

- **Triggers**: Workflow call, Manual dispatch
- **Action**: Compiles Python sources using `compileall`

### 🔒 Security Workflows

#### 5. Security Scan (`.github/workflows/security-scan.yml`)
**Security vulnerability scanning**

- **Triggers**: Push to `main`/`development`, PRs, Weekly schedule (Mon 2:17 AM), Manual dispatch
- **Tools**:
  - Bandit (with SARIF output for GitHub Security tab)
  - pip-audit (dependency vulnerability scan)
- **Permissions**: `contents: read`, `security-events: write`
- **Schedule**: `17 2 * * 1` (Every Monday at 2:17 AM)

#### 6. CodeQL Advanced (`.github/workflows/codeql.yml`)
**GitHub's semantic code analysis**

- **Triggers**: Push to `main`, PRs, Weekly schedule (Wed 6:27 PM)
- **Languages**: Python
- **Permissions**: `security-events: write`, `packages: read`, `actions: read`, `contents: read`
- **Schedule**: `27 18 * * 3` (Every Wednesday at 6:27 PM)

### 📊 Code Quality Workflows

#### 7. Code Quality (`.github/workflows/code-quality.yml`)
**Manual code quality check**

- **Triggers**: Manual dispatch only
- **Action**: Calls `ci-lint.yml` reusable workflow

#### 8. Code Analysis (`.github/workflows/code-analysis.yml`)
**Code complexity analysis**

- **Triggers**: Push to `main`, PRs, Weekly schedule (Mon 3:00 AM), Manual dispatch
- **Tool**: Radon (cyclomatic complexity)
- **Schedule**: `0 3 * * 1` (Every Monday at 3:00 AM)

### 📝 Documentation & Compliance

#### 9. Changelog Check (`.github/workflows/changelog.yml`)
**Validates CHANGELOG.md updates**

- **Triggers**: Pull requests to `main`, Manual dispatch
- **Validation**: Ensures `[Unreleased]` section exists

#### 10. Compliance Check (`.github/workflows/compliance-check.yml`)
**Validates required documentation**

- **Triggers**: Weekly schedule (Mon 5:00 AM), Manual dispatch
- **Required Files**: LICENSE, SECURITY.md, CODE_OF_CONDUCT.md, CHANGELOG.md
- **Schedule**: `0 5 * * 1` (Every Monday at 5:00 AM)

#### 11. Docs Deploy (`.github/workflows/docs-deploy.yml`)
**Documentation validation and deployment**

- **Triggers**: Push to `main`, Manual dispatch
- **Validation**: Checks `docs/vi` and `docs/en` directories exist
- **Artifact**: Uploads docs directory

### 🚀 Release & Automation

#### 12. Release (`.github/workflows/release.yml`)
**Automated release creation**

- **Triggers**: Version tags (`v*.*.*`)
- **Action**: Creates GitHub release with auto-generated notes
- **Permissions**: `contents: write`

#### 13. PR Labeler (`.github/workflows/pr-labeler.yml`)
**Automatic PR labeling**

- **Triggers**: PRs opened, synchronized, or reopened
- **Action**: Auto-labels based on changed files
- **Configuration**: `.github/labeler.yml`
- **Permissions**: `contents: read`, `pull-requests: write`

### 🧪 Performance Testing

#### 14. Performance Test (`.github/workflows/performance-test.yml`)
**Performance regression testing**

- **Triggers**: Weekly schedule (Mon 4:00 AM), Manual dispatch
- **Command**: `pytest -q -m performance --no-cov`
- **Schedule**: `0 4 * * 1` (Every Monday at 4:00 AM)

## Reusable Components

### Composite Actions

#### Setup Python Environment (`.github/actions/setup-python-env`)
Reusable action for setting up Python with caching.

**Inputs**:
- `python-version` (default: '3.11')
- `cache-dependency-path` (default: 'requirements-dev.txt')
- `install-dependencies` (default: 'true')
- `dependencies-file` (default: 'requirements-dev.txt')

## Workflow Triggers Summary

| Workflow | Push (main) | PR (main) | Schedule | Manual | Tag |
|----------|-------------|-----------|----------|--------|-----|
| CI | ✅ | ✅ | ❌ | ✅ | ❌ |
| Security Scan | ✅ | ✅ | ✅ Mon 2:17 | ✅ | ❌ |
| CodeQL | ✅ | ✅ | ✅ Wed 18:27 | ❌ | ❌ |
| Code Analysis | ✅ | ✅ | ✅ Mon 3:00 | ✅ | ❌ |
| Changelog | ❌ | ✅ | ❌ | ✅ | ❌ |
| Compliance | ❌ | ❌ | ✅ Mon 5:00 | ✅ | ❌ |
| Docs Deploy | ✅ | ❌ | ❌ | ✅ | ❌ |
| Performance | ❌ | ❌ | ✅ Mon 4:00 | ✅ | ❌ |
| PR Labeler | ❌ | ✅ | ❌ | ❌ | ❌ |
| Release | ❌ | ❌ | ❌ | ❌ | ✅ |

## Security Best Practices

### Permissions
All workflows use **least-privilege permissions**:
- Most workflows: `contents: read` only
- Security workflows: Add `security-events: write` for SARIF upload
- Release: `contents: write` for creating releases
- PR Labeler: `pull-requests: write` for labeling

### Secrets Management
- Never commit secrets to workflows
- Use GitHub Secrets for sensitive data
- Use environment variables in systemd or `.env` files
- All checkout actions use `persist-credentials: false`

### Dependency Security
- Actions pinned to major versions (v4, v5)
- pip-audit checks for vulnerable dependencies weekly
- Bandit scans for security issues in Python code
- CodeQL performs advanced security analysis

## Caching Strategy

### pip Cache
All Python workflows use pip caching:
```yaml
uses: actions/setup-python@v5
with:
  python-version: '3.11'
  cache: 'pip'
  cache-dependency-path: requirements-dev.txt
```

**Benefits**:
- Faster workflow execution
- Reduced network traffic
- Consistent dependency resolution

## Concurrency Control

Workflows with `concurrency` groups:
- **CI**: `ci-${{ github.ref }}`
- **CI Lint**: `ci-lint-${{ github.ref }}`
- **CI Test**: `ci-test-${{ github.ref }}`
- **CI Build**: `ci-build-${{ github.ref }}`
- **Code Analysis**: `code-analysis-${{ github.ref }}`
- **Docs Deploy**: `docs-deploy-${{ github.ref }}`

All use `cancel-in-progress: true` to cancel outdated runs.

## Testing Matrix

### Python Versions
The main CI workflow tests against:
- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12

Coverage artifacts are only uploaded for Python 3.11.

## Optimization Features

### Recent Improvements
1. ✅ **Reusable Composite Action**: Created `setup-python-env` for DRY
2. ✅ **Python Version Matrix**: Tests across Python 3.9-3.12
3. ✅ **SARIF Upload**: Security scan results appear in GitHub Security tab
4. ✅ **ShellCheck Integration**: Added to CI lint workflow
5. ✅ **Manual Triggers**: Added `workflow_dispatch` to key workflows

### Performance Considerations
- **Timeout Minutes**: Set appropriately (5-20 minutes)
- **fail-fast**: Disabled in matrix builds to see all failures
- **Concurrency**: Cancels old runs to save resources
- **Caching**: pip cache reduces dependency installation time

## Local Testing

### Prerequisites
```bash
pip install -r requirements-dev.txt
sudo apt-get install shellcheck
```

### Run Checks Locally

#### Linting
```bash
python -m black --check src tests
python -m isort --check-only src tests
python -m flake8 src tests
python -m mypy src
shellcheck scripts/*.sh
```

#### Tests
```bash
PYTHONPATH=src pytest -q
```

#### Security
```bash
python -m bandit -r src
pip-audit -r requirements.txt -r requirements-dev.txt
```

#### Build
```bash
python -m compileall -q src
```

## Troubleshooting

### Common Issues

**Q: Tests fail locally but pass in CI**
- Ensure `PYTHONPATH=src` is set
- Check Python version matches CI

**Q: pip cache not working**
- Verify `cache-dependency-path` matches your requirements file
- Clear cache: Go to Actions → Caches in GitHub UI

**Q: Workflow doesn't trigger**
- Check branch protection rules
- Verify trigger conditions in workflow file
- Check if workflow is disabled

## Contributing

When modifying workflows:
1. Test locally first when possible
2. Use manual dispatch to test in GitHub
3. Follow existing patterns for consistency
4. Update this documentation
5. Use Conventional Commits (e.g., `feat(ci):`, `fix(ci):`)

## Status Badges

Add to README.md:
```markdown
[![CI](https://github.com/xnetvn-com/xnetvn_monitord/workflows/CI/badge.svg)](https://github.com/xnetvn-com/xnetvn_monitord/actions/workflows/ci.yml)
[![Security Scan](https://github.com/xnetvn-com/xnetvn_monitord/workflows/Security%20Scan/badge.svg)](https://github.com/xnetvn-com/xnetvn_monitord/actions/workflows/security-scan.yml)
[![CodeQL](https://github.com/xnetvn-com/xnetvn_monitord/workflows/CodeQL%20Advanced/badge.svg)](https://github.com/xnetvn-com/xnetvn_monitord/actions/workflows/codeql.yml)
```

---

**Last Updated**: 2026-02-09
**Maintained By**: xNetVN Inc.
