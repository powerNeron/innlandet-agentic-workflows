"""Run the complete test suite with real sockets and DNS blocked."""
import argparse
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
        with patch("socket.socket",side_effect=AssertionError("Real network disabled by offline harness")), patch("socket.getaddrinfo",side_effect=AssertionError("DNS disabled by offline harness")):
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.discover("eval",pattern="test_*.py"))
        print(f"Offline tests: {result.testsRun}; failures: {len(result.failures)}; errors: {len(result.errors)}")
        return 0 if result.wasSuccessful() else 1
    finally:
        if args.output:stream.close()


if __name__=="__main__":raise SystemExit(main())
