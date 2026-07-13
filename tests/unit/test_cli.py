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

    def test_stats(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli", "stats"])
        with patch("needradar.cli._show_project_stats") as show_stats, patch("needradar.cli._setup_logging"):
            cli.main()
        show_stats.assert_called_once_with()

    def test_run_help_identifies_full_support_default(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["cli", "run", "--help"])

        with pytest.raises(SystemExit) as exit_info:
            cli.main()

        assert exit_info.value.code == 0
        help_text = " ".join(capsys.readouterr().out.split())
        assert "full-support default: github,stackoverflow,juejin" in help_text
