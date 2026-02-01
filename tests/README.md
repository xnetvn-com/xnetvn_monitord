# Test Suite Documentation

## Tổng Quan

Đây là bộ test toàn diện cho xNetVN Monitor Daemon, được thiết kế để đảm bảo chất lượng cao và độ tin cậy của hệ thống giám sát.

## Cấu Trúc Test

```
tests/
├── __init__.py                    # Test package initialization
├── conftest.py                     # Shared fixtures và configuration
├── unit/                          # Unit tests (isolated components)
│   ├── test_config_loader.py     # ConfigLoader tests (20 tests)
│   ├── test_service_monitor.py   # ServiceMonitor tests (35 tests)
│   ├── test_resource_monitor.py  # ResourceMonitor tests (30 tests)
│   ├── test_email_notifier.py    # EmailNotifier tests (25 tests)
│   ├── test_telegram_notifier.py # TelegramNotifier tests (20 tests)
│   ├── test_notification_manager.py # NotificationManager tests (25 tests)
│   └── test_daemon.py            # MonitorDaemon tests (30 tests)
├── integration/                   # Integration tests
│   └── test_monitoring_workflow.py # Workflow integration tests
├── e2e/                          # End-to-end tests
│   └── test_full_workflow.py     # Full system tests
├── performance/                   # Performance tests
│   └── test_performance.py       # Benchmarks và profiling
└── security/                     # Security tests
    └── test_security.py          # Security validation
```

## Cài Đặt

### 1. Cài Đặt Dependencies

```bash
# Từ thư mục gốc dự án
pip install -r requirements-dev.txt
```

### 2. Kiểm Tra Cài Đặt

```bash
pytest --version
pytest --collect-only
```

## Chạy Tests

### Chạy Tất Cả Tests

```bash
# Sử dụng script tiện ích
bash scripts/run_tests.sh

# Hoặc trực tiếp với pytest
pytest
```

### Chạy Theo Loại Test

```bash
# Chỉ unit tests (nhanh nhất)
pytest -m unit

# Integration tests
pytest -m integration

# E2E tests (chậm nhất)
pytest -m e2e

# Security tests
pytest -m security

# Performance tests
pytest -m performance
```

### Chạy Theo Module

```bash
# Test một file cụ thể
pytest tests/unit/test_config_loader.py

# Test một class cụ thể
pytest tests/unit/test_config_loader.py::TestConfigLoaderLoad

# Test một function cụ thể
pytest tests/unit/test_config_loader.py::TestConfigLoaderLoad::test_should_load_valid_yaml_successfully
```

### Options Hữu Ích

```bash
# Chạy với output verbose
pytest -v

# Dừng sau test đầu tiên fail
pytest -x

# Chạy parallel (nhanh hơn)
pytest -n auto

# Chỉ chạy failed tests từ lần trước
pytest --lf

# Chạy với coverage report
pytest --cov=xnetvn_monitord --cov-report=html
```

## Coverage Report

### Generate Coverage

```bash
# HTML report (chi tiết nhất)
pytest --cov=xnetvn_monitord --cov-report=html
# Mở htmlcov/index.html trong browser

# Terminal report
pytest --cov=xnetvn_monitord --cov-report=term-missing

# XML report (cho CI/CD)
pytest --cov=xnetvn_monitord --cov-report=xml
```

### Coverage Goals

- **Overall:** ≥ 85%
- **Critical modules (ConfigLoader, ServiceMonitor, ResourceMonitor):** ≥ 90%
- **Notification modules:** ≥ 85%
- **Daemon orchestration:** ≥ 80%

## Debug Tools

### Test Service Monitoring

```bash
# Test systemctl check
python debug/test_service_check.py --method systemctl --service-name nginx

# Test auto detection (systemd/OpenRC/SysV)
python debug/test_service_check.py --method auto --service-name nginx

# Test SysV service check
python debug/test_service_check.py --method service --service-name nginx

# Test OpenRC service check
python debug/test_service_check.py --method openrc --service-name nginx

# Test process check
python debug/test_service_check.py --method process --service-name nginx

# Test regex check
python debug/test_service_check.py --method process_regex --pattern "php-fpm.*master"

# Test custom command
python debug/test_service_check.py --method custom --command "/usr/local/bin/check.sh"
```

### Test Resource Monitoring

```bash
# Check current resource usage
python debug/test_resource_check.py

# With custom thresholds
python debug/test_resource_check.py \
    --cpu-threshold 5.0 \
    --memory-percent-threshold 20.0 \
    --disk-threshold 80.0
```

## Writing New Tests

### Test Structure (AAA Pattern)

```python
def test_should_do_something_when_condition():
    """Test description following Given-When-Then pattern."""
    # Arrange - Setup test data and mocks
    config = {"enabled": True}
    monitor = ServiceMonitor(config)
    
    # Act - Execute the code being tested
    result = monitor.check_all_services()
    
    # Assert - Verify expectations
    assert result is not None
    assert len(result) > 0
```

### Naming Convention

Tên test phải rõ ràng và mô tả:
- **Format:** `test_should_<expected_behavior>_when_<condition>`
- **Ví dụ:**
  - `test_should_load_valid_yaml_successfully`
  - `test_should_raise_error_when_file_not_found`
  - `test_should_detect_inactive_systemd_service`

### Using Fixtures

```python
def test_with_fixtures(config_file, temp_dir, mocker):
    """Example using multiple fixtures."""
    # config_file: Path to temporary config file
    # temp_dir: Temporary directory path
    # mocker: Pytest-mock fixture
    
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value.returncode = 0
    
    loader = ConfigLoader(str(config_file))
    config = loader.load()
    
    assert config is not None
```

### Markers

Sử dụng markers để phân loại tests:

```python
import pytest

@pytest.mark.unit
def test_unit_functionality():
    """Unit test example."""
    pass

@pytest.mark.integration
def test_integration_scenario():
    """Integration test example."""
    pass

@pytest.mark.slow
def test_long_running_process():
    """Test that takes > 1 second."""
    pass

@pytest.mark.requires_root
def test_privileged_operation():
    """Test requiring root privileges."""
    pass

@pytest.mark.security
def test_security_feature():
    """Security-focused test."""
    pass
```

## Continuous Integration

### CI/CD Pipeline

```yaml
# Example GitHub Actions workflow
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      - name: Run tests
        run: |
          pytest --cov=xnetvn_monitord --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Best Practices

### 1. Independence
- Mỗi test phải độc lập, không phụ thuộc vào thứ tự thực thi
- Sử dụng fixtures để tạo test data mới cho mỗi test

### 2. Readability
- Tên test phải mô tả rõ ràng
- Comment phức tạp logic nếu cần
- Sử dụng AAA pattern

### 3. Speed
- Unit tests phải < 1s
- Integration tests phải < 5s
- Sử dụng mocking để tránh I/O operations

### 4. Coverage
- Aim for high coverage nhưng focus vào quality
- Test edge cases và error paths
- Không test third-party libraries

### 5. Maintainability
- DRY principle - sử dụng fixtures cho code chung
- Update tests khi code thay đổi
- Delete obsolete tests

## Troubleshooting

### Tests Fail Locally But Pass in CI

```bash
# Clean cache
pytest --cache-clear

# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Import Errors

```bash
# Ensure PYTHONPATH is set correctly
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Or use pytest.ini pythonpath setting (already configured)
```

### Slow Tests

```bash
# Identify slow tests
pytest --durations=10

# Run in parallel
pytest -n auto

# Skip slow tests
pytest -m "not slow"
```

### Coverage Not Updating

```bash
# Clean coverage data
rm -rf .coverage htmlcov

# Force coverage recalculation
pytest --cov=xnetvn_monitord --cov-report=html --cov-append
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)
- [Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development)

## Support

Nếu gặp vấn đề với tests:
1. Kiểm tra [Troubleshooting](#troubleshooting) section
2. Xem log chi tiết: `pytest -vv --tb=long`
3. Mở issue trong repository với đầy đủ thông tin

---

**Lưu ý:** Test suite này được thiết kế theo các tiêu chuẩn cao nhất của ngành công nghiệp phần mềm và tuân thủ các best practices từ các công ty công nghệ hàng đầu thế giới.
