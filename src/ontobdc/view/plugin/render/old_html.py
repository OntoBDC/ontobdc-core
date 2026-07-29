
import webbrowser
from pathlib import Path
from typing import Any, Dict, List
from jinja2 import Environment, FileSystemLoader
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.adapter.logger import BaseLoggerAdapter
from ontobdc.shared.domain.response.command import SingleHtmlContentCommandResponse


class SingleHtmlContentCommandResponseRender:
    def render(self, response: SingleHtmlContentCommandResponse, logger: BaseLoggerAdapter, render_type: str) -> None:
        output_path: Path = self._get_output_path(response)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._build_html_document(response), encoding="utf-8")

        webbrowser.open(output_path.as_uri())
        logger.log_notice(f"Opening HTML document rendered at: {output_path}")

    def _get_output_path(self, response: SingleHtmlContentCommandResponse) -> Path:
        safe_name: str = "".join(
            character.lower() if character.isalnum() else "_"
            for character in response.content_title
        ).strip("_")
        if safe_name == "":
            safe_name = "single_html_content"

        return ConfigDataAdapter().config_dir / "render" / f"{safe_name}.html"

    def _build_html_document(self, response: SingleHtmlContentCommandResponse) -> str:
        content: Dict[str, Any] = response.to_dict()["content"]
        language: str = str(content.get("language", ""))
        raw: str = str(content.get("raw", ""))
        items: List[Dict[str, str]] = list(content.get("items", []))
        body_content: str = self._build_body_content(language, raw, items)
        template = self._get_template_environment().get_template("single_html_content.html.j2")

        return template.render(
            title=str(content.get("title", "")),
            description=str(content.get("description", "")),
            source_path=str(content.get("source_path", "")),
            body_content=body_content,
        )

    def _build_body_content(self, language: str, raw: str, items: List[Dict[str, str]]) -> str:
        if len(items) > 0:
            return self._build_indexed_diagrams(language, items)

        escaped_raw: str = escape(raw)
        return self._build_single_diagram(language, escaped_raw)

    def _build_indexed_diagrams(self, language: str, items: List[Dict[str, str]]) -> str:
        links: List[str] = []
        sections: List[str] = []

        for item in items:
            item_id: str = item.get("id", "")
            item_title: str = item.get("title", "")
            item_raw: str = item.get("raw", "")

            links.append(f"<li><a href=\"#{item_id}\">{item_title}</a></li>")

            diagram_html: str = self._build_single_diagram(language, item_raw)
            sections.append(
                f"<h2 id=\"{item_id}\">{item_title}</h2>"
                f"<div class=\"panel\">{diagram_html}</div>"
            )

        return (
            "<h2>Index</h2>"
            "<ul>"
            + "\n".join(links)
            + "</ul>"
            + "\n".join(sections)
        )

    def _build_single_diagram(self, language: str, raw: str) -> str:
        if language == "mermaid@11":
            return (
                f"<div class=\"mermaid\">{raw}</div>"
                "\n"
                "  <script type=\"module\">\n"
                "    import mermaid from \"https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs\";\n"
                "    mermaid.initialize({ startOnLoad: true, theme: \"neutral\", securityLevel: \"loose\" });\n"
                "  </script>"
            )

        return f"<pre>{raw}</pre>"

    def _get_template_environment(self) -> Environment:
        template_dir: Path = Path(__file__).resolve().parent / "template"
        return Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
        )
