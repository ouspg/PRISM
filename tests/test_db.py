"""Tests for database utilities."""

from prism.db import _split_sql_statements


class TestSplitSqlStatements:
    def test_simple_split(self):
        sql = "CREATE TABLE foo (id INT); CREATE TABLE bar (id INT);"
        stmts = _split_sql_statements(sql)
        assert len(stmts) == 2
        assert "foo" in stmts[0]
        assert "bar" in stmts[1]

    def test_preserves_quoted_semicolons(self):
        sql = "INSERT INTO foo VALUES ('a;b'); SELECT 1;"
        stmts = _split_sql_statements(sql)
        assert len(stmts) == 2
        assert "'a;b'" in stmts[0]

    def test_trailing_without_semicolon(self):
        sql = "SELECT 1; SELECT 2"
        stmts = _split_sql_statements(sql)
        assert len(stmts) == 2

    def test_empty_string(self):
        assert _split_sql_statements("") == []

    def test_single_statement(self):
        stmts = _split_sql_statements("SELECT 1")
        assert len(stmts) == 1
        assert stmts[0] == "SELECT 1"

    def test_real_init_sql_splits(self):
        """Verify the actual init SQL can be split without errors."""
        from pathlib import Path

        sql_path = Path(__file__).resolve().parent.parent / "sql" / "001_init.sql"
        sql = sql_path.read_text()
        stmts = _split_sql_statements(sql)
        # Should produce many statements (CREATE EXTENSION, types, tables, indexes)
        assert len(stmts) > 10
        # First statement should be the CREATE EXTENSION
        assert "uuid-ossp" in stmts[0]
