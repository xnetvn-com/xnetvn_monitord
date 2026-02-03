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

## 7. Pull Request checklist

- [ ] Tests have been run
- [ ] Documentation has been updated
- [ ] No secrets are included
- [ ] The change description is clear
