# Security Policy

## Supported Versions

We take security seriously at xNetVN Inc. and are committed to providing security updates for the following versions of xnetvn_monitord:

| Version | Supported          |
| ------- | ------------------ |
| 0.x.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within xnetvn_monitord, please send an email to **security@xnetvn.net**. All security vulnerabilities will be promptly addressed.

### What to Include

When reporting a vulnerability, please include:

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact of the vulnerability
- Any suggested fixes (if applicable)

### Response Timeline

- **Initial Response**: Within 48 hours of report submission
- **Status Updates**: Every 7 days until resolution
- **Resolution**: We aim to address critical vulnerabilities within 30 days

### Disclosure Policy

- Please do not publicly disclose the vulnerability until we have had a chance to address it
- We will credit security researchers who responsibly disclose vulnerabilities
- Once a fix is available, we will publish a security advisory

## Security Best Practices

When deploying xnetvn_monitord:

1. **Environment Variables**: Store sensitive data (API tokens, passwords) in environment variables, never in configuration files committed to version control
2. **File Permissions**: Ensure configuration files have appropriate permissions (0600 for .env files)
3. **Updates**: Keep xnetvn_monitord updated to the latest version to receive security patches
4. **Monitoring**: Regularly review logs for suspicious activity
5. **Network Security**: Use firewall rules to restrict access to monitoring endpoints
6. **Secrets Management**: Use systemd EnvironmentFile or proper secrets management solutions

## Security Features

xnetvn_monitord includes several security features:

- Sensitive data filtering in logs and notifications
- Rate limiting for notifications to prevent spam
- Audit logging for all critical operations
- Support for secure communication channels (HTTPS, TLS)
- Input validation and sanitization

## Security Auditing

Our repository uses automated security scanning:

- **Bandit**: Static analysis for Python security issues
- **pip-audit**: Dependency vulnerability scanning
- **CodeQL**: Advanced code analysis for security vulnerabilities
- **Dependabot**: Automated dependency updates

## Contact

For security concerns, please contact:
- **Email**: security@xnetvn.net
- **General inquiries**: license@xnetvn.net
- **Website**: https://xnetvn.com

---

**Thank you for helping keep xnetvn_monitord secure!**
