"""Test: NotificationService Refactoring - automation Parameter."""

import sys
sys.path.insert(0, "/opt/python-modules")

from agents.services.notification_service import NotificationService, NotificationResult, get_notification_service


def test_automation_in_constructor():
    print("=== Test 1: Automation im Konstruktor ===")
    
    notifier = NotificationService("my_automation")
    assert notifier.automation == "my_automation"
    print(f"Automation: {notifier.automation}")
    print("OK\n")
    return notifier


def test_default_automation():
    print("=== Test 2: Default Automation ===")
    
    notifier = NotificationService()
    assert notifier.automation == "default"
    print(f"Default Automation: {notifier.automation}")
    print("OK\n")


def test_automation_in_result():
    print("=== Test 3: Automation im Result ===")
    
    notifier = NotificationService("test_workflow")
    # Telegram nicht konfiguriert - aber Result sollte automation haben
    result = notifier.send_telegram("Test")
    
    assert result.automation == "test_workflow"
    print(f"Result Automation: {result.automation}")
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")
    print("OK\n")


def test_factory_caching():
    print("=== Test 4: Factory mit Caching ===")
    
    n1 = get_notification_service("cache_test")
    n2 = get_notification_service("cache_test")
    assert n1 is n2
    print("Gleiche Automation = gleiche Instanz: OK")
    
    n3 = get_notification_service("other")
    assert n1 is not n3
    print("Andere Automation = andere Instanz: OK")
    
    print("OK\n")


def test_backwards_compatibility():
    print("=== Test 5: Rückwärtskompatibilität ===")
    
    # Alte Nutzung: Ohne Parameter
    notifier = NotificationService()
    assert notifier.automation == "default"
    print("Nutzung ohne Parameter funktioniert: OK")
    
    # Config-Methoden funktionieren noch
    channels = notifier.list_channels()
    print(f"Kanäle: {channels}")
    
    print("OK\n")


if __name__ == "__main__":
    print("NotificationService Refactor Tests\n" + "="*50 + "\n")
    
    test_automation_in_constructor()
    test_default_automation()
    test_automation_in_result()
    test_factory_caching()
    test_backwards_compatibility()
    
    print("="*50)
    print("Alle Tests bestanden!")
