"""Test: Logger Erweiterung - tags Parameter."""

import sys
sys.path.insert(0, "/opt/python-modules")

from agents.utils.logger import Logger, LogLevel, get_logger


def test_default_tags():
    print("=== Test 1: Default Tags im Konstruktor ===")

    logger = Logger("tag_test", tags=["production", "api"])
    assert logger.default_tags == ["production", "api"]
    print(f"Default Tags: {logger.default_tags}")
    print("OK\n")
    return logger


def test_log_with_default_tags(logger):
    print("=== Test 2: Log mit Default Tags ===")

    logger.info("Test mit Default Tags")

    logs = logger.get_logs(limit=1)
    assert len(logs) == 1
    assert "production" in logs[0].tags
    assert "api" in logs[0].tags
    print(f"Tags im Log: {logs[0].tags}")
    print("OK\n")


def test_log_with_additional_tags(logger):
    print("=== Test 3: Log mit zusätzlichen Tags ===")

    logger.info("Test mit extra Tags", tags=["verbose", "debug-info"])

    logs = logger.get_logs(limit=1)
    assert "production" in logs[0].tags  # Default
    assert "api" in logs[0].tags  # Default
    assert "verbose" in logs[0].tags  # Zusätzlich
    assert "debug-info" in logs[0].tags  # Zusätzlich
    print(f"Kombinierte Tags: {logs[0].tags}")
    print("OK\n")


def test_filter_by_tags():
    print("=== Test 4: Filter nach Tags ===")

    logger = Logger("filter_test")

    # Verschiedene Logs mit verschiedenen Tags
    logger.info("Log A", tags=["category-a"])
    logger.info("Log B", tags=["category-b"])
    logger.info("Log AB", tags=["category-a", "category-b"])

    # Filter nach category-a
    logs_a = logger.get_logs(tags=["category-a"])
    print(f"Logs mit category-a: {len(logs_a)}")
    assert len(logs_a) == 2  # Log A und Log AB

    # Filter nach category-b
    logs_b = logger.get_logs(tags=["category-b"])
    print(f"Logs mit category-b: {len(logs_b)}")
    assert len(logs_b) == 2  # Log B und Log AB

    # Filter nach beiden
    logs_ab = logger.get_logs(tags=["category-a", "category-b"])
    print(f"Logs mit category-a UND category-b: {len(logs_ab)}")
    assert len(logs_ab) == 1  # Nur Log AB

    logger.clear_all()
    print("OK\n")


def test_no_tags():
    print("=== Test 5: Log ohne Tags ===")

    logger = Logger("no_tags_test")
    logger.info("Ohne Tags")

    logs = logger.get_logs(limit=1)
    assert logs[0].tags == []
    print(f"Leere Tags: {logs[0].tags}")

    logger.clear_all()
    print("OK\n")


def test_backwards_compatibility():
    print("=== Test 6: Rückwärtskompatibilität ===")

    # Alte Nutzung: Ohne tags Parameter
    logger = Logger("compat_test")
    assert logger.default_tags == []
    print("Logger ohne Tags funktioniert: OK")

    # Log ohne tags Parameter
    logger.info("Alte Nutzung")
    logs = logger.get_logs(limit=1)
    print(f"Log erstellt: {logs[0].message}")

    logger.clear_all()
    print("OK\n")


def test_factory_with_tags():
    print("=== Test 7: Factory mit Tags ===")

    logger = get_logger("factory_test", tags=["from-factory"])
    assert logger.default_tags == ["from-factory"]
    print(f"Factory Tags: {logger.default_tags}")

    logger.clear_all()
    print("OK\n")


def cleanup():
    print("=== Cleanup ===")
    Logger("tag_test").clear_all()
    Logger("filter_test").clear_all()
    Logger("no_tags_test").clear_all()
    Logger("compat_test").clear_all()
    Logger("factory_test").clear_all()
    print("OK\n")


if __name__ == "__main__":
    print("Logger Tags Tests\n" + "="*50 + "\n")

    logger = test_default_tags()
    test_log_with_default_tags(logger)
    test_log_with_additional_tags(logger)
    test_filter_by_tags()
    test_no_tags()
    test_backwards_compatibility()
    test_factory_with_tags()
    cleanup()

    print("="*50)
    print("Alle Tests bestanden!")
