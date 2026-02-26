# Compatibility shim — renderers in trajectly.cli.report, schema in trajectly.core.report
from trajectly.cli.report.renderers import render_markdown, render_pr_comment, write_reports  # noqa: F401

__all__ = ["render_markdown", "render_pr_comment", "write_reports"]
