"""Invoked in a child interpreter. Candidate code must be trusted local code."""
import json
import sys
import unittest
from pathlib import Path


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed = []

    def startTest(self, test):
        self.executed.append(test.id())
        super().startTest(test)


def main():
    root, pattern, destination = sys.argv[1:]
    sys.path.insert(0, root)
    loader = unittest.TestLoader()
    suite = loader.discover(root, pattern=pattern)
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    summary = dict(ran=result.testsRun, executed=result.executed,
                   failures=[test.id() for test, _ in result.failures],
                   errors=[test.id() for test, _ in result.errors],
                   skipped=[test.id() for test, _ in result.skipped],
                   expected_failures=[test.id() for test, _ in result.expectedFailures],
                   unexpected_successes=[test.id() for test in result.unexpectedSuccesses])
    Path(destination).write_text(json.dumps(summary))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
