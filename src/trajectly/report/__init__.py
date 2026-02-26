# Compatibility shim — renderers in trajectly.cli.report, schema in trajectly.core.report
from trajectly.cli.report.renderers import render_markdown, render_pr_comment, write_reports

__all__ = ["render_markdown", "render_pr_comment", "write_reports"]
