"""Run the complete test suite with real sockets and DNS blocked."""
import argparse
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,help="Optional new, exclusive UTF-8 evaluation log")
    args=parser.parse_args(argv)
    stream=args.output.open("x",encoding="utf-8") if args.output else sys.stderr
    try:
        with ExitStack() as guards:
            guards.enter_context(patch("socket.socket",side_effect=AssertionError("Real network disabled by offline harness")))
            guards.enter_context(patch("socket.getaddrinfo",side_effect=AssertionError("DNS disabled by offline harness")))
            # Parent mocks cannot constrain Rust or a child interpreter. Every
            # offline test must explicitly replace the native search boundary;
            # otherwise fail before a child/gateway can be created.
            guards.enter_context(patch('hamar_agent.internet_research._spawn_search_worker',
                side_effect=AssertionError('Native search worker disabled offline')))
            # Rust/primp does not use Python socket mocks. The optional DDGS
            # real-parser contracts must never construct its native transport.
            if importlib.util.find_spec('ddgs'):
                guards.enter_context(patch('ddgs.http_client.primp.Client',side_effect=AssertionError('Native search transport disabled offline')))
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.discover("eval",pattern="test_*.py"))
        print(f"Offline tests: {result.testsRun}; failures: {len(result.failures)}; errors: {len(result.errors)}")
        return 0 if result.wasSuccessful() else 1
    finally:
        if args.output:stream.close()


if __name__=="__main__":raise SystemExit(main())
