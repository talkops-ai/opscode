"""CLI command for running environment diagnostics and health checks."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from rich.console import Console

from dcoder.commands._base import CommandContext
from dcoder.commands.core.doctor import DoctorHandler
from dcoder.config.settings import settings
from dcoder.output import OutputFormat, write_json


def run_doctor_command(args: argparse.Namespace) -> int:
    """Run `dcoder doctor` health check report."""
    output_format: OutputFormat = getattr(args, "output_format", "text")
    handler = DoctorHandler()

    ctx = CommandContext(
        app=None,
        raw_command="/doctor",
        args="",
        settings=settings,
    )

    result = asyncio.run(handler.execute(ctx))

    if output_format == "json":
        sections = [
            handler._collect_diagnostics(ctx),
            handler._collect_active_model(ctx),
            handler._collect_configuration(ctx),
            handler._collect_api_keys(ctx),
            asyncio.run(handler._collect_mcp(ctx)),
            handler._collect_devops_tools(),
            handler._collect_agents(ctx),
            handler._collect_skills(ctx),
            handler._collect_workspace(ctx),
        ]
        data = {
            "healthy": all(s.ok for s in sections),
            "sections": [
                {
                    "title": s.title,
                    "ok": s.ok,
                    "items": [{"label": i.label, "value": i.value, "ok": i.ok, "tip": i.tip} for i in s.items],
                }
                for s in sections
            ],
        }
        write_json("doctor", data)
        return 0

    Console().print(result.message)
    return 0 if result.success else 1
