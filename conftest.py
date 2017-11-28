import pytest


def pytest_addoption(parser):
    parser.addoption("--dumprecent", action="store_true",
                     help="run dump_recent_tracks test/store results")
