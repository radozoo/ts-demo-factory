"""Build ThoughtSpot Model TML from a Jinja2 template."""
from __future__ import annotations

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from thoughtspot_tml import Model

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def build_model_tml(template_name: str, context: dict) -> str:
    """
    Render *template_name* (relative to templates/) with *context*,
    then round-trip through thoughtspot_tml.Model.

    Returns validated TML YAML string.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        keep_trailing_newline=True,
    )
    template = env.get_template(template_name)
    raw = template.render(**context)
    model_obj = Model.loads(raw)
    return model_obj.dumps()
