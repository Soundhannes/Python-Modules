"""Test-Skript für BaseOrchestrator."""

import sys
import time
sys.path.insert(0, '/opt/python-modules')

from agents.core.base_orchestrator import BaseOrchestrator, StepResult, OrchestrationResult


def test_instanziierung():
    print('=== Test 1: Instanziierung ===')
    orch = BaseOrchestrator()
    print(f'Max Workers: {orch.max_workers}')
    assert orch.max_workers == 4
    print('OK\n')
    return orch


def test_sequence(orch):
    print('=== Test 2: Sequenz ===')

    def step1(ctx):
        return {"value": ctx.get("start", 0) + 1}

    def step2(ctx):
        prev = ctx.get("step_1", {}).get("value", 0)
        return {"value": prev + 10}

    def step3(ctx):
        prev = ctx.get("step_2", {}).get("value", 0)
        return {"value": prev + 100}

    result = orch.run_sequence(
        steps=[step1, step2, step3],
        initial_context={"start": 5}
    )

    print(f'Success: {result.success}')
    print(f'Steps: {len(result.steps)}')
    print(f'Final Context: {result.final_context}')
    print(f'Duration: {result.total_duration_ms}ms')

    assert result.success
    assert len(result.steps) == 3
    assert result.final_context["step_3"]["value"] == 116  # 5+1+10+100
    print('OK\n')


def test_sequence_with_names(orch):
    print('=== Test 3: Sequenz mit Namen ===')

    result = orch.run_sequence(
        steps=[
            ("fetch", lambda ctx: {"data": [1, 2, 3]}),
            ("process", lambda ctx: {"sum": sum(ctx["fetch"]["data"])}),
        ]
    )

    print(f'Success: {result.success}')
    print(f'Final Context: {result.final_context}')

    assert result.success
    assert result.final_context["process"]["sum"] == 6
    print('OK\n')


def test_sequence_stop_on_error(orch):
    print('=== Test 4: Sequenz mit Fehler ===')

    def failing_step(ctx):
        raise ValueError("Simulierter Fehler")

    result = orch.run_sequence(
        steps=[
            lambda ctx: {"ok": True},
            failing_step,
            lambda ctx: {"never": "reached"},
        ],
        stop_on_error=True
    )

    print(f'Success: {result.success}')
    print(f'Steps executed: {len(result.steps)}')
    print(f'Error: {result.error}')

    assert not result.success
    assert len(result.steps) == 2  # Dritter Schritt nicht ausgeführt
    assert "Simulierter Fehler" in result.error
    print('OK\n')


def test_parallel(orch):
    print('=== Test 5: Parallel ===')

    def slow_step(name, delay):
        def step(ctx):
            time.sleep(delay)
            return {"name": name, "delay": delay}
        return step

    start = time.time()
    result = orch.run_parallel(
        steps=[
            ("task_a", slow_step("A", 0.1)),
            ("task_b", slow_step("B", 0.1)),
            ("task_c", slow_step("C", 0.1)),
        ]
    )
    duration = time.time() - start

    print(f'Success: {result.success}')
    print(f'Steps: {len(result.steps)}')
    print(f'Duration: {duration:.2f}s (should be ~0.1s, not 0.3s)')

    assert result.success
    assert len(result.steps) == 3
    assert duration < 0.3  # Parallel = schneller als sequentiell
    print('OK\n')


def test_condition(orch):
    print('=== Test 6: Bedingung ===')

    result_true = orch.run_condition(
        check=lambda ctx: ctx.get("value") > 5,
        if_true=lambda ctx: "groesser",
        if_false=lambda ctx: "kleiner",
        context={"value": 10}
    )

    result_false = orch.run_condition(
        check=lambda ctx: ctx.get("value") > 5,
        if_true=lambda ctx: "groesser",
        if_false=lambda ctx: "kleiner",
        context={"value": 3}
    )

    print(f'Value=10: {result_true.final_context}')
    print(f'Value=3: {result_false.final_context}')

    assert result_true.final_context["if_true"] == "groesser"
    assert result_false.final_context["if_false"] == "kleiner"
    print('OK\n')


def test_loop(orch):
    print('=== Test 7: Loop ===')

    counter = {"value": 0}

    def increment(ctx):
        counter["value"] += 1
        return counter["value"]

    result = orch.run_loop(
        step=increment,
        until=lambda ctx: ctx.get("last_result", 0) >= 5,
        max_iterations=10
    )

    print(f'Success: {result.success}')
    print(f'Iterations: {result.final_context.get("iterations")}')
    print(f'Final value: {counter["value"]}')

    assert result.success
    assert result.final_context["iterations"] == 5
    assert counter["value"] == 5
    print('OK\n')


def test_retry(orch):
    print('=== Test 8: Retry ===')

    attempt_counter = {"count": 0}

    def flaky_step(ctx):
        attempt_counter["count"] += 1
        if attempt_counter["count"] < 3:
            raise ValueError(f"Fehler bei Versuch {attempt_counter['count']}")
        return "Erfolg beim dritten Versuch"

    result = orch.run_retry(
        step=flaky_step,
        max_retries=5,
        delay_seconds=0.1
    )

    print(f'Success: {result.success}')
    print(f'Attempts: {result.final_context.get("attempts")}')
    print(f'Result: {result.final_context.get("retry_step")}')

    assert result.success
    assert result.final_context["attempts"] == 3
    print('OK\n')


if __name__ == '__main__':
    print('BaseOrchestrator Tests\n' + '='*50 + '\n')

    orch = test_instanziierung()
    test_sequence(orch)
    test_sequence_with_names(orch)
    test_sequence_stop_on_error(orch)
    test_parallel(orch)
    test_condition(orch)
    test_loop(orch)
    test_retry(orch)

    print('='*50)
    print('Alle Tests bestanden!')
