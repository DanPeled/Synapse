from enum import Enum
import re


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
    def repl(match):
        tags = match.group(1).strip().split()
        content = match.group(2)

        if target == TextTarget.kTerminal:
            tag_str = " ".join(tags)
            return f"[{tag_str}]{content}[/{tag_str}]"
        elif target == TextTarget.kHTML:
            styles = []
            for tag in tags:
                if tag == "bold":
                    styles.append("font-weight: bold")
                else:
                    styles.append(f"color: {tag}")
            return f'<span style="{"; ".join(styles)}">{content}</span>'

    pattern = re.compile(r"\[([a-zA-Z0-9\s]+)\](.*?)\[/\1\]", re.DOTALL)
    return re.sub(pattern, repl, text)
