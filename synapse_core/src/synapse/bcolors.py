# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum


class TextTarget(Enum):
    kTerminal = "terminal"
    kHTML = "html"


class MarkupColors:
    """
    Markup-style wrappers for text formatting using custom tags,
    to be parsed for either terminal (via rich) or HTML.
    """

    @staticmethod
    def header(text: str) -> str:
        return MarkupColors.okgreen(MarkupColors.bold(text))

    @staticmethod
    def okblue(text: str) -> str:
        return f"[blue]{text}[/blue]"

    @staticmethod
    def okcyan(text: str) -> str:
        return f"[cyan]{text}[/cyan]"

    @staticmethod
    def okgreen(text: str) -> str:
        return f"[green]{text}[/green]"

    @staticmethod
    def warning(text: str) -> str:
        return f"[yellow]{text}[/yellow]"

    @staticmethod
    def fail(text: str) -> str:
        return f"[red]{text}[/red]"

    @staticmethod
    def bold(text: str) -> str:
        return f"[bold]{text}[/bold]"

    @staticmethod
    def underline(text: str) -> str:
        return f"[underline]{text}[/underline]"


def parseTextStyle(text: str, target: TextTarget = TextTarget.kTerminal) -> str:
    return text
