"""
Tests fuer iCloud CalDAV Provider.
"""
from datetime import datetime


def test_provider_exists():
    """Provider Klasse existiert."""
    from providers.icloud_calendar import ICloudCalendarProvider
    provider = ICloudCalendarProvider()
    assert provider is not None


def test_provider_has_authenticate():
    """Provider hat authenticate Methode."""
    from providers.icloud_calendar import ICloudCalendarProvider
    provider = ICloudCalendarProvider()
    assert hasattr(provider, 'authenticate')
    assert callable(provider.authenticate)


def test_provider_has_list_calendars():
    """Provider hat list_calendars Methode."""
    from providers.icloud_calendar import ICloudCalendarProvider
    provider = ICloudCalendarProvider()
    assert hasattr(provider, 'list_calendars')
    assert callable(provider.list_calendars)


def test_provider_has_pull_events():
    """Provider hat pull_events Methode."""
    from providers.icloud_calendar import ICloudCalendarProvider
    provider = ICloudCalendarProvider()
    assert hasattr(provider, 'pull_events')
    assert callable(provider.pull_events)


def test_provider_has_push_event():
    """Provider hat push_event Methode."""
    from providers.icloud_calendar import ICloudCalendarProvider
    provider = ICloudCalendarProvider()
    assert hasattr(provider, 'push_event')
    assert callable(provider.push_event)


def test_provider_has_delete_event():
    """Provider hat delete_event Methode."""
    from providers.icloud_calendar import ICloudCalendarProvider
    provider = ICloudCalendarProvider()
    assert hasattr(provider, 'delete_event')
    assert callable(provider.delete_event)


if __name__ == "__main__":
    tests = [
        test_provider_exists,
        test_provider_has_authenticate,
        test_provider_has_list_calendars,
        test_provider_has_pull_events,
        test_provider_has_push_event,
        test_provider_has_delete_event,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            print(f'{test.__name__}: PASSED')
            passed += 1
        except Exception as e:
            print(f'{test.__name__}: FAILED - {e}')
            failed += 1
    
    print(f'\n=== {passed}/{passed+failed} Tests ===')
