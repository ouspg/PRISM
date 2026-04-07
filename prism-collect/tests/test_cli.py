"""Tests for the CLI entry point."""

from click.testing import CliRunner

from prism.cli import cli


class TestCli:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "OUSPG-PRISM" in result.output

    def test_collect_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["collect", "--help"])
        assert result.exit_code == 0
        assert "--domain" in result.output
        assert "--repo" in result.output
        assert "--collector" in result.output

    def test_seed_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["seed", "--help"])
        assert result.exit_code == 0
        assert "--csv-file" in result.output
        assert "--yaml-file" in result.output

    def test_db_init_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["db", "init", "--help"])
        assert result.exit_code == 0

    def test_status_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
