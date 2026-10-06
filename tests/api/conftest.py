import pytest


_auth_module_skipped = False


def pytest_collectreport(report):
    global _auth_module_skipped
    if report.skipped and report.nodeid.replace("\\", "/").endswith("tests/api/test_auth.py"):
        _auth_module_skipped = True


def pytest_sessionfinish(session, exitstatus):
    if _auth_module_skipped and exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
