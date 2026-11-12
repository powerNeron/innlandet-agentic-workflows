"""Per-run output reservations and bounded provider waiting, without paid probes.

Output maxima are reserved, never measured token usage or billed cost. Prompt
bytes are a separate bound. A deadline abandons the caller; it cannot terminate
an already running remote inference. Four daemon workers bound residual work.
"""
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass
from functools import wraps
import math
import os
from threading import BoundedSemaphore, Event, Lock, Thread, get_ident
import time


class RunStopped(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Run stopped: ' + code)


@dataclass(frozen=True)
class RunPolicy:
    output_tokens: int = 1400
    input_bytes: int = 64_000
    seconds: float = 90.0
    max_calls: int = 2

    def __post_init__(self):
        for value, minimum, maximum in ((self.output_tokens, 32, 8192), (self.input_bytes, 1024, 1_000_000), (self.max_calls, 1, 2)):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError('Invalid run budget limits')
        if type(self.seconds) not in (int, float) or not math.isfinite(self.seconds) or not .01 <= self.seconds <= 180:
            raise ValueError('Invalid run deadline')

    @classmethod
    def from_env(cls):
        try:
            return cls(output_tokens=int(os.environ.get('HAMAR_RUN_OUTPUT_TOKENS', '1400')),
                       input_bytes=int(os.environ.get('HAMAR_RUN_INPUT_BYTES', '64000')),
                       seconds=float(os.environ.get('HAMAR_RUN_SECONDS', '90')))
        except (TypeError, ValueError):
            raise ValueError('Invalid trusted run configuration') from None


class RunState:
    def __init__(self, policy, *, clock=time.perf_counter):
        self.policy, self.clock = policy, clock
        self.started = clock()
        self.deadline = self.started + policy.seconds
        self.lock = Lock()
        self.output_reserved = self.bytes_reserved = self.reservations = self.tasks_started = 0
        self.stopped = None
        self.finished = False
        self.ended_at = None
        self.events = []

    def _check(self):
        if self.stopped:
            raise RunStopped(self.stopped)
        if not self.finished and self.clock() >= self.deadline:
            self.stopped = 'run_deadline_exceeded'
            self.ended_at = self.clock()
            raise RunStopped(self.stopped)

    def checkpoint(self, stage):
        with self.lock:
            self._check()
            if len(self.events) < 128:
                self.events.append({'stage': stage, 'elapsed_ms': round((self.clock() - self.started) * 1000, 3)})

    def stop(self, code):
        with self.lock:
            self.stopped = self.stopped or code
            self.ended_at = self.ended_at if self.ended_at is not None else self.clock()
            raise RunStopped(self.stopped)

    def admit_tool(self, stage):
        """Linearize new tool work before caller completion, without token use."""
        with self.lock:
            self._check()
            if self.finished:
                raise RunStopped('run_closed')
            if len(self.events)<128:
                self.events.append({'stage':stage,'elapsed_ms':round((self.clock()-self.started)*1000,3)})

    def reserve(self, output_tokens, prompt_bytes):
        with self.lock:
            self._check()
            if self.finished:
                raise RunStopped('run_closed')
            if type(output_tokens) is not int or output_tokens <= 0 or type(prompt_bytes) is not int or prompt_bytes < 0:
                raise ValueError('Invalid generation reservation')
            code = None
            if self.reservations >= self.policy.max_calls or self.output_reserved + output_tokens > self.policy.output_tokens:
                code = 'run_budget_exceeded'
            elif self.bytes_reserved + prompt_bytes > self.policy.input_bytes:
                code = 'run_input_limit'
            if code:
                self.stopped = code
                self.ended_at = self.clock()
                raise RunStopped(code)
            self.output_reserved += output_tokens
            self.bytes_reserved += prompt_bytes
            self.reservations += 1

    def remaining(self):
        with self.lock:
            self._check()
            return max(0., self.deadline - self.clock())

    def finish(self):
        with self.lock:
            self._check()
            self.finished = True
            self.ended_at = self.ended_at if self.ended_at is not None else self.clock()

    def snapshot(self):
        with self.lock:
            return {'output_token_limit': self.policy.output_tokens, 'output_tokens_reserved': self.output_reserved,
                    'actual_token_usage': None, 'scope': 'Reserved generated/output maxima; not total tokens or billed cost',
                    'prompt_byte_limit': self.policy.input_bytes, 'prompt_bytes_reserved': self.bytes_reserved,
                    'call_limit': self.policy.max_calls, 'reservations': self.reservations,
                    'provider_tasks_started': self.tasks_started, 'deadline_seconds': self.policy.seconds,
                    'elapsed_ms': round(((self.ended_at if self.ended_at is not None else self.clock()) - self.started) * 1000, 3), 'stopped_code': self.stopped,
                    'finished': self.finished, 'events': list(self.events)}


_current = ContextVar('aisha_run', default=None)
_slots = BoundedSemaphore(4)
_workers_lock = Lock()
_owners = {}
_active_workers = 0


def current_run():
    return _current.get()


def checkpoint(stage):
    state = current_run()
    if state is not None:
        state.checkpoint(stage)


def remaining_seconds(default):
    state = current_run()
    return min(default, state.remaining()) if state is not None else default


@contextmanager
def run_scope(policy=None, *, clock=time.perf_counter):
    existing = current_run()
    if existing is not None:
        existing.checkpoint('nested_scope')
        yield existing
        existing.checkpoint('nested_return')
        return
    state = RunState(policy or RunPolicy.from_env(), clock=clock)
    token = _current.set(state)
    try:
        yield state
        state.checkpoint('run_return')
        state.finish()
    except Exception:
        if state.stopped:
            raise RunStopped(state.stopped) from None
        raise
    finally:
        # Copied contexts may outlive a failed/abandoned caller. Closing the
        # request on every exit prevents their capabilities from being replayed.
        # This records caller completion, not cancellation of residual workers.
        with state.lock:
            state.finished = True
            state.ended_at = state.ended_at if state.ended_at is not None else state.clock()
        _current.reset(token)


def controlled_run(function):
    @wraps(function)
    def execute(*args, **kwargs):
        with run_scope(getattr(args[0], 'run_policy', None) if args else None):
            checkpoint(function.__qualname__)
            value = function(*args, **kwargs)
            checkpoint('result_ready')
            return value
    return execute


def active_workers():
    with _workers_lock:
        return _active_workers


def _start(function, *, owner=None, state=None, cleanup_owner=False):
    """Never release a slot until the actual task AND deferred cleanup end."""
    global _active_workers
    if not _slots.acquire(blocking=False):
        return None
    done, box = Event(), []
    context = copy_context()
    key = id(owner) if owner is not None else None
    with _workers_lock:
        if key is not None and not cleanup_owner and getattr(owner, '_aisha_close_requested', False):
            _slots.release()
            return None
        _active_workers += 1
        if key is not None and not cleanup_owner:
            record = _owners.setdefault(key, {'owner': owner, 'active': 0, 'cleanup': None, 'cleaning': None})
            record['active'] += 1
    def work():
        global _active_workers
        try:
            if cleanup_owner:
                with _workers_lock:
                    _owners[key]['cleaning'] = get_ident()
            if state is not None:
                state.checkpoint('provider_dispatched')
                with state.lock:
                    state.tasks_started += 1
            box.append((True, context.run(function)))
        except BaseException as error:
            box.append((False, error))
        finally:
            done.set()
            closer = None
            with _workers_lock:
                if key is not None and not cleanup_owner:
                    record = _owners[key]
                    record['active'] -= 1
                    if record['active'] == 0:
                        closer = record['cleanup']
                        if closer is None:
                            _owners.pop(key)
                        else:
                            record['cleaning'] = get_ident()
            try:
                if closer is not None:
                    try:
                        closer()
                    except BaseException:
                        # Caller already left; no late SDK diagnostics are logged.
                        pass
            finally:
                with _workers_lock:
                    if closer is not None or cleanup_owner:
                        owner._aisha_close_done = True
                        _owners.pop(key, None)
                    _active_workers -= 1
                _slots.release()
    worker = Thread(target=work, daemon=True, name='aisha-bounded-provider')
    try:
        worker.start()
    except BaseException:
        with _workers_lock:
            if key is not None:
                if cleanup_owner:
                    _owners.pop(key)
                else:
                    _owners[key]['active'] -= 1
                    if _owners[key]['active'] == 0:
                        _owners.pop(key)
            _active_workers -= 1
        _slots.release()
        raise
    return done, box


def bounded_tool_call(function, *, timeout_seconds=10):
    """Share the existing worker cap/deadline without reserving model tokens.

    Timeout abandons the caller; residual work keeps its slot until it exits.
    This is not cancellation of an HTTP request or a remote inference.
    """
    state = current_run()
    if state is None or state.finished:
        raise RunStopped('run_request_inactive')
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 10:
        raise ValueError('Invalid trusted tool timeout')
    state.checkpoint('source_dispatch')
    def admitted_call():
        if current_run() is not state:
            raise RunStopped('run_request_inactive')
        state.admit_tool('source_worker_admitted')
        return function()
    task = _start(admitted_call)
    if task is None:
        state.stop('run_capacity_exceeded')
    done, box = task
    if not done.wait(min(timeout_seconds, state.remaining())):
        state.stop('run_deadline_exceeded' if state.remaining() <= 0 else 'run_source_timeout')
    state.checkpoint('source_return')
    success, value = box[0]
    if not success:
        raise value
    return value


def guarded_generation(function):
    @wraps(function)
    def generate(client, system_prompt, user_prompt):
        with run_scope() as state:
            with _workers_lock:
                closed = getattr(client, '_aisha_close_requested', False)
            if closed:
                state.stop('run_provider_closed')
            maximum = getattr(client.config, 'num_predict', None)
            if maximum is None:
                maximum = client.config.max_output_tokens
            size = len((system_prompt + '\n\n' + user_prompt).encode('utf-8'))
            state.reserve(maximum, size)
            task = _start(lambda: function(client, system_prompt, user_prompt), owner=client, state=state)
            if task is None:
                state.stop('run_capacity_exceeded')
            done, box = task
            if not done.wait(state.remaining()):
                state.stop('run_deadline_exceeded')
            state.checkpoint('provider_return')
            success, value = box[0]
            if not success:
                raise value
            return value
    return generate


def cleanup_provider(owner, closer):
    """Defer close to active owner, else wait at most .1s in the same worker cap.

    False means untracked cleanup could not start because capacity was exhausted.
    No new worker is created outside the cap and no running client is closed.
    """
    direct = False
    with _workers_lock:
        record = _owners.get(id(owner)) if owner is not None else None
        if owner is not None:
            if getattr(owner, '_aisha_close_done', False):
                return True
            owner._aisha_close_requested = True
        if record is not None:
            if record['cleaning'] == get_ident():
                direct = True
            else:
                if record['cleaning'] is None:
                    record['cleanup'] = closer
                return True
        elif owner is not None:
            # Publish close intent BEFORE releasing the owner lock or launching.
            _owners[id(owner)] = {'owner': owner, 'active': 0, 'cleanup': None, 'cleaning': None}
    if direct:
        closer()
        return True
    task = _start(closer, owner=owner, cleanup_owner=owner is not None)
    if task is None:
        if owner is not None:
            with _workers_lock:
                _owners.pop(id(owner), None)
        return False
    done, box = task
    if done.wait(.1) and not box[0][0]:
        raise box[0][1]
    return True
