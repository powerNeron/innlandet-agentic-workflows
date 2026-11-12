"""Synthetic run budgets and abandonment, including still-blocked dependencies."""
import json
import math
import os
from threading import Barrier, Event, Thread
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from hamar_agent.ollama_provider import OllamaClient, OllamaConfig, OllamaError
from hamar_agent.openai_provider import OpenAIClient, OpenAIConfig
from hamar_agent.provider_registry import ProviderRegistry
from hamar_agent.real_sources import MunicipalWorkflowService
from hamar_agent.search import SearchIndex
from hamar_agent.web import WebApplication
from hamar_agent.run_control import (RunPolicy, RunState, RunStopped, active_workers, cleanup_provider,
                                     current_run, run_scope)
from eval.test_municipal_workflow import document, service, envelope, record


def drain():
    end = time.monotonic() + 2
    while active_workers() and time.monotonic() < end:
        Event().wait(.002)
    if active_workers():
        raise AssertionError('Synthetic workers did not release their slots')


class RunControlTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('Real network forbidden'))
            guard.start(); self.addCleanup(guard.stop)
        self.addCleanup(drain)

    def headers(self, app):
        return {'Host': '127.0.0.1:8000', 'Origin': 'http://127.0.0.1:8000',
                'Content-Type': 'application/json', 'X-Hamar-Token': app.token}

    def test_report_percentages_have_explicit_empty_denominators(self):
        from eval.evaluate_verification import percent
        self.assertEqual(percent(3, 4), 75.)
        self.assertIsNone(percent(0, 0))
        for numerator, denominator in ((2, 1), (-1, 4), (True, 2)):
            with self.assertRaises(ValueError): percent(numerator, denominator)

    def test_report_latency_uses_nearest_rank_p95_without_fabricated_empty_values(self):
        from eval.evaluate_verification import latency_summary
        self.assertEqual(latency_summary([4, 1, 3, 2]), {'n': 4, 'mean_ms': 2.5, 'median_ms': 2.5,
            'p95_ms_nearest_rank': 4, 'max_ms': 4})
        self.assertEqual(latency_summary(list(range(1, 21)))['p95_ms_nearest_rank'], 19)
        self.assertIsNone(latency_summary([])['mean_ms'])
        for values in ([math.nan], [-1], [True]):
            with self.assertRaises(ValueError): latency_summary(values)

    def test_recovery_rate_rejects_ungrounded_over_budget_or_failed_attempts(self):
        from eval.evaluate_verification import recovery_success
        good = {'http_status': 200, 'published': True, 'grounded': True,
                'budget_compliant': True, 'fresh_run': True, 'model_calls': 1}
        self.assertTrue(recovery_success(good))
        for key, value in (('http_status', 503), ('published', False), ('grounded', False),
                           ('budget_compliant', False), ('fresh_run', False), ('model_calls', 2), ('model_calls', True)):
            with self.subTest(key=key, value=value):
                self.assertFalse(recovery_success({**good, key: value}))
        self.assertFalse(recovery_success(None))

    def test_policy_rejects_invalid_integers_nonfinite_and_out_of_range_deadlines(self):
        for changes in ({'output_tokens': True}, {'output_tokens': 31}, {'input_bytes': 0},
                        {'max_calls': 3}, {'seconds': math.nan}, {'seconds': math.inf},
                        {'seconds': False}, {'seconds': 0}, {'seconds': 181}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                RunPolicy(**changes)
        with patch.dict(os.environ, {'HAMAR_RUN_OUTPUT_TOKENS': 'invalid'}, clear=True), self.assertRaises(ValueError):
            RunPolicy.from_env()

    def test_exact_output_limit_is_reserved_atomically_before_dispatch(self):
        calls = Mock(return_value=envelope([record()]))
        client = OllamaClient(OllamaConfig(num_predict=32), transport=calls)
        with self.assertRaises(RunStopped) as error:
            with run_scope(RunPolicy(output_tokens=64)) as state:
                client.generate('system', 'first')
                client.generate('system', 'second')
                client.generate('system', 'must not dispatch')
        self.assertEqual(error.exception.code, 'run_budget_exceeded')
        self.assertEqual(calls.call_count, 2)
        self.assertEqual(state.snapshot()['output_tokens_reserved'], 64)
        self.assertEqual(state.snapshot()['actual_token_usage'], None)

    def test_full_utf8_prompt_boundary_and_no_refund_of_failed_calls(self):
        calls = Mock(side_effect=OllamaError('synthetic failure'))
        client = OllamaClient(OllamaConfig(num_predict=32), transport=calls)
        with self.assertRaises(RunStopped) as error:
            with run_scope(RunPolicy(output_tokens=64, input_bytes=1024)) as state:
                with self.assertRaises(OllamaError):
                    client.generate('å', 'a' * 1020)  # 2 + 2 separators + 1020 = 1024 bytes.
                client.generate('s', 'second request')
        self.assertEqual(error.exception.code, 'run_input_limit')
        self.assertEqual(calls.call_count, 1)
        self.assertEqual(state.snapshot()['prompt_bytes_reserved'], 1024)
        self.assertEqual(state.snapshot()['output_tokens_reserved'], 32)

    def test_standalone_generate_gets_a_new_safe_root_and_nested_scope_cannot_raise_limit(self):
        calls = Mock(return_value=envelope([record()]))
        client = OllamaClient(OllamaConfig(num_predict=32), transport=calls)
        with patch.dict(os.environ, {'HAMAR_RUN_OUTPUT_TOKENS': '32'}, clear=True):
            client.generate('s', 'one')
            client.generate('s', 'new root')
        self.assertIsNone(current_run())
        with self.assertRaises(RunStopped):
            with run_scope(RunPolicy(output_tokens=32)) as outer:
                with run_scope(RunPolicy(output_tokens=8192)) as inner:
                    self.assertIs(inner, outer)
                    client.generate('s', 'one')
                    client.generate('s', 'cannot escape outer cap')
        self.assertEqual(calls.call_count, 3)

    def test_initial_and_correction_share_one_budget_and_stop_is_not_swallowed(self):
        calls = Mock(side_effect=[envelope([record(text='Fictional unsupported fee 999')]), envelope([record()])])
        workflow = service(calls)
        workflow.run_policy = RunPolicy(output_tokens=700)
        with self.assertRaises(RunStopped) as error:
            workflow.run('fictional-test')
        self.assertEqual(error.exception.code, 'run_budget_exceeded')
        self.assertEqual(calls.call_count, 1)
        repaired = service(Mock(side_effect=[envelope([record(text='Fictional unsupported fee 999')]), envelope([record()])]))
        repaired.run_policy = RunPolicy(output_tokens=1400)
        with run_scope(repaired.run_policy) as state:
            self.assertEqual(repaired.run('fictional-test').correction.attempts, 1)
        self.assertEqual(state.snapshot()['output_tokens_reserved'], 1400)

    def test_openai_reserves_its_output_cap_without_sdk_call_when_budget_is_too_small(self):
        create = Mock(return_value=SimpleNamespace(status='completed',error=None,output_text='{}'))
        client = OpenAIClient(OpenAIConfig(model='synthetic-model', api_key='synthetic-only',
            enabled=True, privacy_authorized=True), sdk_client=SimpleNamespace(responses=SimpleNamespace(create=create)))
        with self.assertRaises(RunStopped):
            with run_scope(RunPolicy(output_tokens=511)):
                client.generate('s', 'synthetic')
        create.assert_not_called()

    def test_blocked_dependency_is_abandoned_before_release_and_cannot_publish_later(self):
        entered, release = Event(), Event()
        def blocked(*args):
            entered.set()
            release.wait(3)
            raise OllamaError('synthetic-private-late-diagnostic')
        self.addCleanup(lambda: (release.set(), drain()))
        workflow = service(blocked)
        workflow.run_policy = RunPolicy(seconds=.05)
        app = WebApplication(workflow)
        start = time.monotonic()
        response = app.dispatch('POST', '/api/answer', self.headers(app), b'{"query":"service"}')
        elapsed = time.monotonic() - start
        self.assertTrue(entered.is_set())
        self.assertFalse(release.is_set())
        self.assertGreaterEqual(elapsed, .04)
        self.assertLess(elapsed, .75)  # Test tolerance, not a real-time scheduling guarantee.
        self.assertEqual(json.loads(response.body)['error_code'], 'run_deadline_exceeded')
        self.assertNotIn(b'synthetic-private', response.body)
        self.assertEqual(active_workers(), 1)
        self.assertFalse(app.results)
        release.set(); drain()
        self.assertFalse(app.results)
        self.assertFalse(app.result_owners)

    def test_deadline_expiring_after_generation_is_checked_inside_publication_lock(self):
        for path, body in (('/api/answer', b'{"query":"vann"}'),
                           ('/api/run', b'{"source_id":"synthetic-verification-demo"}')):
            with self.subTest(path=path):
                now = [0.]
                app = WebApplication()
                def late_id(*args):
                    now[0] = 2.
                    return 'synthetic-expired-publication'
                with self.assertRaises(RunStopped):
                    with run_scope(RunPolicy(seconds=1), clock=lambda: now[0]), patch('hamar_agent.web.secrets.token_hex', side_effect=late_id):
                        response = app.dispatch('POST', path, self.headers(app), body)
                self.assertEqual(json.loads(response.body)['error_code'], 'run_deadline_exceeded')
                self.assertFalse(app.results)
                self.assertEqual(app.sessions[app.token].topic_terms, ())

    def test_request_cannot_override_trusted_policy_and_invalid_server_limits_call_no_provider(self):
        calls = Mock()
        app = WebApplication(service(calls))
        response = app.dispatch('POST', '/api/answer', self.headers(app), b'{"query":"service","output_tokens":8192}')
        self.assertEqual(response.status, 400)
        calls.assert_not_called()
        with patch.dict(os.environ, {'HAMAR_RUN_SECONDS': 'nan'}, clear=True):
            response = app.dispatch('POST', '/api/answer', self.headers(app), b'{"query":"service"}')
        self.assertEqual(json.loads(response.body)['error_code'], 'run_configuration')
        calls.assert_not_called()

    def test_expiry_between_publication_checkpoint_and_finish_cannot_leave_an_export(self):
        finish = RunState.finish
        for path, body in (('/api/answer', b'{"query":"vann"}'),
                           ('/api/run', b'{"source_id":"synthetic-verification-demo"}')):
            with self.subTest(path=path):
                now = [0.]
                app = WebApplication()
                def crossed(state):
                    if any(event['stage'] == 'publication' for event in state.events):
                        now[0] = 2.
                    return finish(state)
                with self.assertRaises(RunStopped):
                    with run_scope(RunPolicy(seconds=1), clock=lambda: now[0]), patch.object(RunState, 'finish', crossed):
                        response = app.dispatch('POST', path, self.headers(app), body)
                self.assertEqual(json.loads(response.body)['error_code'], 'run_deadline_exceeded')
                self.assertFalse(app.results)
                self.assertFalse(app.result_owners)
                self.assertEqual(app.sessions[app.token].topic_terms, ())

    def test_idle_close_blocks_new_generation_of_the_same_client(self):
        entered, release = Event(), Event()
        self.addCleanup(lambda: (release.set(), drain()))
        calls = Mock(return_value=envelope([record()]))
        client = OllamaClient(OllamaConfig(num_predict=32), transport=calls)
        def close():
            entered.set(); release.wait(3)
        self.assertTrue(cleanup_provider(client, close))
        self.assertTrue(entered.is_set())
        with self.assertRaises(RunStopped):
            client.generate('s', 'cannot use a client while close is blocked')
        calls.assert_not_called()
        self.assertEqual(active_workers(), 1)

    def test_nested_openai_close_uses_the_owner_worker(self):
        entered, release = Event(), Event()
        counts = []
        self.addCleanup(lambda: (release.set(), drain()))
        def close():
            counts.append(active_workers()); entered.set(); release.wait(3)
        client = OpenAIClient(OpenAIConfig(model='synthetic-model', api_key='synthetic-only',
            enabled=True, privacy_authorized=True), sdk_client=SimpleNamespace(close=close))
        self.assertTrue(cleanup_provider(client, client.close))
        self.assertTrue(entered.is_set())
        self.assertEqual(counts, [1])
        self.assertEqual(active_workers(), 1)

    def test_capacity_stays_occupied_after_abandonment_then_recovers(self):
        release = Event()
        calls = Mock(side_effect=lambda *args: (release.wait(3), envelope([record()]))[1])
        client = OllamaClient(OllamaConfig(num_predict=32), transport=calls)
        self.addCleanup(lambda: (release.set(), drain()))
        for _ in range(4):
            with self.assertRaises(RunStopped):
                with run_scope(RunPolicy(seconds=.02)):
                    client.generate('s', 'blocked')
        self.assertEqual(active_workers(), 4)
        with self.assertRaises(RunStopped) as error:
            client.generate('s', 'no replacement worker allowed')
        self.assertEqual(error.exception.code, 'run_capacity_exceeded')
        self.assertEqual(calls.call_count, 4)
        closed = Mock()
        self.assertTrue(cleanup_provider(client, closed))
        closed.assert_not_called()
        release.set(); drain()
        closed.assert_called_once()
        fresh = OllamaClient(OllamaConfig(num_predict=32), transport=calls)
        fresh.generate('s', 'recovered capacity with a fresh client')
        self.assertEqual(calls.call_count, 5)

    def test_cleanup_wait_is_bounded_and_keyboard_interrupt_is_preserved(self):
        release = Event()
        self.addCleanup(lambda: (release.set(), drain()))
        start = time.monotonic()
        cleanup_provider(None, lambda: release.wait(3))
        self.assertLess(time.monotonic() - start, .75)
        release.set(); drain()
        with self.assertRaises(KeyboardInterrupt):
            cleanup_provider(None, Mock(side_effect=KeyboardInterrupt()))

    def test_concurrent_runs_have_independent_budgets(self):
        results, errors = [], []
        def request():
            try:
                calls = Mock(return_value=envelope([record()]))
                client = OllamaClient(OllamaConfig(num_predict=32), transport=calls)
                with run_scope(RunPolicy(output_tokens=32)) as state:
                    client.generate('s', 'independent')
                results.append(state.snapshot()['output_tokens_reserved'])
            except BaseException as error:
                errors.append(type(error).__name__)
        threads = [Thread(target=request) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(2)
        self.assertFalse(errors)
        self.assertEqual(results, [32, 32])

    def test_two_concurrent_reservations_cannot_overspend_one_shared_state(self):
        state = RunState(RunPolicy(output_tokens=32))
        ready = Barrier(2)
        outcomes = []
        def reserve():
            ready.wait(1)
            try:
                state.reserve(32, 10)
                outcomes.append('allowed')
            except RunStopped:
                outcomes.append('denied')
        threads = [Thread(target=reserve) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(2)
        self.assertEqual(sorted(outcomes), ['allowed', 'denied'])
        self.assertEqual(state.snapshot()['output_tokens_reserved'], 32)

    def test_finished_run_elapsed_time_is_not_the_time_of_later_inspection(self):
        now = [0.]
        with run_scope(RunPolicy(seconds=1), clock=lambda: now[0]) as state:
            state.reserve(32, 10)
            now[0] = .2
        now[0] = 10.
        self.assertEqual(state.snapshot()['elapsed_ms'], 200.)

    def test_openai_cleanup_is_deferred_until_abandoned_generation_really_finishes(self):
        release, entered = Event(), Event()
        def create(**kwargs):
            entered.set(); release.wait(3)
            p = json.loads(kwargs['input'].split('SOURCE_PARAGRAPHS=', 1)[1].splitlines()[0])[0]
            return SimpleNamespace(status='completed',error=None,output_text=json.dumps({'claims': [record(text=p['text'], quote=p['text'], paragraph=p['id'])]}))
        close = Mock()
        config = OpenAIConfig(model='synthetic-model', api_key='synthetic-only', enabled=True, privacy_authorized=True)
        client = OpenAIClient(config, sdk_client=SimpleNamespace(responses=SimpleNamespace(create=create), close=close))
        workflow = MunicipalWorkflowService(SearchIndex([document()]), client, provider='openai', historical_baseline=True)
        workflow.run_policy = RunPolicy(seconds=.05)
        registry = ProviderRegistry(openai_config_factory=lambda: config, sdk_available=lambda: True)
        app = WebApplication(workflow, provider_registry=registry, service_factory=lambda *args: workflow)
        self.addCleanup(lambda: (release.set(), drain()))
        response = app.dispatch('POST', '/api/answer', self.headers(app),
            b'{"query":"service","provider":"openai","model":"synthetic-model"}')
        self.assertEqual(json.loads(response.body)['error_code'], 'run_deadline_exceeded')
        self.assertTrue(entered.is_set())
        close.assert_not_called()
        release.set(); drain()
        close.assert_called_once()
        self.assertFalse(app.results)
