"""Tests for CLI — argparse parsing, setup_logging."""

import sys
from unittest.mock import patch

import pytest
from needradar import cli


class TestSetupLogging:
    def test_verbose(self):
        with patch("needradar.cli.logger") as m:
            cli._setup_logging(verbose=True)
        m.remove.assert_called_once(); m.add.assert_called_once()

    def test_normal(self):
        with patch("needradar.cli.logger") as m:
            cli._setup_logging(verbose=False)
        m.add.assert_called_once()


class TestArgparse:
    def test_run(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli", "run", "test"])
        with patch("needradar.cli.asyncio.run"), patch("needradar.cli._setup_logging"):
            cli.main()

    def test_report(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli", "report", "AI"])
        with patch("needradar.cli.asyncio.run"), patch("needradar.cli._setup_logging"):
            cli.main()

    def test_status(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli", "status"])
        with patch("needradar.cli.asyncio.run"), patch("needradar.cli._setup_logging"):
            cli.main()

    def test_no_command(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli"])
        with patch("needradar.cli._setup_logging"):
            cli.main()

    def test_with_platforms(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli", "run", "x", "--platforms", "github,zhihu"])
        with patch("needradar.cli.asyncio.run"), patch("needradar.cli._setup_logging"):
            cli.main()

    def test_verbose(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli", "-v", "status"])
        with patch("needradar.cli.asyncio.run"), patch("needradar.cli._setup_logging"):
            cli.main()
