"""
BaseOrchestrator - Ablaufsteuerung für Agent-Automationen.

Bietet wiederverwendbare Pattern:
- Sequenz: Schritte nacheinander
- Parallel: Schritte gleichzeitig
- Bedingung: If/Else Verzweigung
- Schleife: Wiederholung bis Bedingung
- Retry: Wiederholung bei Fehler

Verwendung:
    orchestrator = BaseOrchestrator('my_workflow')

    # Sequenz
    results = orchestrator.run_sequence([
        ('step1', lambda ctx: do_something(ctx)),
        ('step2', lambda ctx: do_more(ctx)),
    ])
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any, Optional, Union
from datetime import datetime


@dataclass
class StepResult:
    """Ergebnis eines Orchestrator-Schritts."""
    step_name: str
    success: bool
    result: Any
    error: Optional[str]
    duration_ms: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OrchestrationResult:
    """Gesamtergebnis einer Orchestrierung."""
    orchestrator_name: str
    success: bool
    steps: List[StepResult]
    final_context: Dict[str, Any]
    total_duration_ms: int
    error: Optional[str] = None


# Type Aliases
StepFunction = Callable[[Dict[str, Any]], Any]
ConditionFunction = Callable[[Dict[str, Any]], bool]


class BaseOrchestrator:
    """
    Basis-Orchestrator für Agent-Automationen.

    Args:
        name: Name des Orchestrators (für Logging/Tracking)
        max_workers: Maximale parallele Worker für run_parallel
    """

    def __init__(self, name: str = "orchestrator", max_workers: int = 4):
        """
        Initialisiert den Orchestrator.

        Args:
            name: Name des Orchestrators (für Logging/Tracking)
            max_workers: Maximale parallele Worker für run_parallel
        """
        self.name = name
        self.max_workers = max_workers

    def _execute_step(
        self,
        step: StepFunction,
        context: Dict[str, Any],
        step_name: str = "step"
    ) -> StepResult:
        """Führt einen einzelnen Schritt aus."""
        start_time = time.time()

        try:
            result = step(context)
            duration_ms = int((time.time() - start_time) * 1000)

            return StepResult(
                step_name=step_name,
                success=True,
                result=result,
                error=None,
                duration_ms=duration_ms
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            return StepResult(
                step_name=step_name,
                success=False,
                result=None,
                error=str(e),
                duration_ms=duration_ms
            )

    def _make_result(
        self,
        success: bool,
        steps: List[StepResult],
        context: Dict[str, Any],
        start_time: float,
        error: Optional[str] = None
    ) -> OrchestrationResult:
        """Erstellt ein OrchestrationResult."""
        return OrchestrationResult(
            orchestrator_name=self.name,
            success=success,
            steps=steps,
            final_context=context,
            total_duration_ms=int((time.time() - start_time) * 1000),
            error=error
        )

    def run_sequence(
        self,
        steps: List[Union[StepFunction, tuple]],
        initial_context: Optional[Dict[str, Any]] = None,
        stop_on_error: bool = True,
        update_context: bool = True
    ) -> OrchestrationResult:
        """
        Führt Schritte nacheinander aus.

        Args:
            steps: Liste von Funktionen oder (name, function) Tuples
            initial_context: Startkontext
            stop_on_error: Bei Fehler abbrechen?
            update_context: Ergebnis jedes Schritts in Kontext übernehmen?

        Returns:
            OrchestrationResult
        """
        start_time = time.time()
        context = dict(initial_context or {})
        step_results = []

        for i, step in enumerate(steps):
            if isinstance(step, tuple):
                step_name, step_func = step
            else:
                step_name = f"step_{i+1}"
                step_func = step

            result = self._execute_step(step_func, context, step_name)
            step_results.append(result)

            if update_context and result.success and result.result is not None:
                context[step_name] = result.result

            if not result.success and stop_on_error:
                return self._make_result(
                    False, step_results, context, start_time,
                    f"Schritt '{step_name}' fehlgeschlagen: {result.error}"
                )

        return self._make_result(
            all(r.success for r in step_results),
            step_results, context, start_time
        )

    def run_parallel(
        self,
        steps: List[Union[StepFunction, tuple]],
        context: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> OrchestrationResult:
        """
        Führt Schritte parallel aus.

        Args:
            steps: Liste von Funktionen oder (name, function) Tuples
            context: Kontext (wird nicht verändert, nur gelesen)
            timeout: Timeout in Sekunden

        Returns:
            OrchestrationResult
        """
        start_time = time.time()
        context = dict(context or {})
        step_results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for i, step in enumerate(steps):
                if isinstance(step, tuple):
                    step_name, step_func = step
                else:
                    step_name = f"step_{i+1}"
                    step_func = step

                future = executor.submit(self._execute_step, step_func, context, step_name)
                futures[future] = step_name

            for future in as_completed(futures, timeout=timeout):
                try:
                    result = future.result()
                    step_results.append(result)
                except Exception as e:
                    step_results.append(StepResult(
                        step_name=futures[future],
                        success=False,
                        result=None,
                        error=str(e),
                        duration_ms=0
                    ))

        final_context = dict(context)
        for result in step_results:
            if result.success and result.result is not None:
                final_context[result.step_name] = result.result

        return self._make_result(
            all(r.success for r in step_results),
            step_results, final_context, start_time
        )

    def run_condition(
        self,
        check: ConditionFunction,
        if_true: StepFunction,
        if_false: StepFunction,
        context: Optional[Dict[str, Any]] = None
    ) -> OrchestrationResult:
        """
        Führt bedingte Verzweigung aus.

        Args:
            check: Funktion die bool zurückgibt
            if_true: Wird ausgeführt wenn check True
            if_false: Wird ausgeführt wenn check False
            context: Kontext

        Returns:
            OrchestrationResult
        """
        start_time = time.time()
        context = dict(context or {})

        try:
            condition_result = check(context)
        except Exception as e:
            return self._make_result(
                False, [], context, start_time,
                f"Bedingung fehlgeschlagen: {e}"
            )

        if condition_result:
            result = self._execute_step(if_true, context, "if_true")
        else:
            result = self._execute_step(if_false, context, "if_false")

        final_context = dict(context)
        final_context["condition_result"] = condition_result
        if result.success and result.result is not None:
            final_context[result.step_name] = result.result

        return self._make_result(
            result.success, [result], final_context, start_time,
            result.error
        )

    def run_loop(
        self,
        step: StepFunction,
        until: ConditionFunction,
        context: Optional[Dict[str, Any]] = None,
        max_iterations: int = 100,
        step_name: str = "loop_step"
    ) -> OrchestrationResult:
        """
        Führt Schritt wiederholt aus bis Bedingung erfüllt.

        Args:
            step: Funktion die wiederholt wird
            until: Funktion die True zurückgibt wenn fertig
            context: Startkontext
            max_iterations: Maximale Durchläufe
            step_name: Name für die Schritte

        Returns:
            OrchestrationResult
        """
        start_time = time.time()
        context = dict(context or {})
        step_results = []

        for i in range(max_iterations):
            result = self._execute_step(step, context, f"{step_name}_{i+1}")
            step_results.append(result)

            if result.success and result.result is not None:
                context[f"{step_name}_{i+1}"] = result.result
                context["last_result"] = result.result

            if not result.success:
                return self._make_result(
                    False, step_results, context, start_time,
                    f"Loop Iteration {i+1} fehlgeschlagen: {result.error}"
                )

            try:
                if until(context):
                    break
            except Exception as e:
                return self._make_result(
                    False, step_results, context, start_time,
                    f"Loop-Bedingung fehlgeschlagen: {e}"
                )

        context["iterations"] = len(step_results)
        return self._make_result(True, step_results, context, start_time)

    def run_retry(
        self,
        step: StepFunction,
        max_retries: int = 3,
        context: Optional[Dict[str, Any]] = None,
        delay_seconds: float = 1.0,
        backoff_multiplier: float = 2.0,
        step_name: str = "retry_step"
    ) -> OrchestrationResult:
        """
        Führt Schritt mit Retry bei Fehler aus.

        Args:
            step: Funktion die wiederholt wird
            max_retries: Maximale Versuche
            context: Kontext
            delay_seconds: Initiale Pause zwischen Versuchen
            backoff_multiplier: Multiplikator für Exponential Backoff
            step_name: Name für die Schritte

        Returns:
            OrchestrationResult
        """
        start_time = time.time()
        context = dict(context or {})
        step_results = []
        delay = delay_seconds

        for attempt in range(max_retries):
            result = self._execute_step(step, context, f"{step_name}_attempt_{attempt+1}")
            step_results.append(result)

            if result.success:
                final_context = dict(context)
                final_context[step_name] = result.result
                final_context["attempts"] = attempt + 1
                return self._make_result(True, step_results, final_context, start_time)

            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= backoff_multiplier

        return self._make_result(
            False, step_results, context, start_time,
            f"Alle {max_retries} Versuche fehlgeschlagen"
        )
