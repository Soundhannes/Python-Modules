import sys
import threading
import time
sys.path.insert(0, '/opt/python-modules')
from agents.utils.human_in_loop import HumanInLoop, get_human_in_loop

def run_tests():
    print('HumanInLoop Tests\n' + '='*50)
    
    hil = HumanInLoop('test_automation')
    print('\n1. Instanziierung: OK')
    
    # Request erstellen
    request_id = hil._create_request('approval', 'Test Frage?', ['approve', 'reject'])
    assert request_id > 0
    print(f'2. Create request (id={request_id}): OK')
    
    # Pending requests abrufen
    pending = hil.get_pending_requests()
    assert any(r.id == request_id for r in pending)
    print(f'3. Get pending: {len(pending)} requests - OK')
    
    # Antworten
    success = hil.respond(request_id, 'approved', approved=True)
    assert success
    print('4. Respond: OK')
    
    # Nicht mehr pending
    pending = hil.get_pending_requests()
    assert not any(r.id == request_id for r in pending)
    print('5. No longer pending: OK')
    
    # Test mit Thread (simuliert echten Ablauf)
    def responder(rid):
        time.sleep(1)
        hil.respond(rid, 'yes', approved=True)
    
    request_id2 = hil._create_request('approval', 'Async Test?', ['approve', 'reject'])
    t = threading.Thread(target=responder, args=(request_id2,))
    t.start()
    
    # Warte mit kurzem Timeout
    result = hil._wait_for_response(request_id2, timeout=5, poll_interval=0.5)
    assert result is not None
    assert result.status == 'approved'
    print('6. Async response: OK')
    t.join()
    
    # Cancel test
    request_id3 = hil._create_request('input', 'Cancel Test?')
    cancelled = hil.cancel_request(request_id3)
    assert cancelled
    print('7. Cancel request: OK')
    
    print('\n' + '='*50)
    print('Alle Tests bestanden!')

if __name__ == '__main__':
    run_tests()
