import os
from typing import Dict, List

from Crucible.config import Config
from Crucible.utils.fs_router import fs_router


class TemplateManager:
    TEMPLATE_DIR = "Templates"

    DEFAULT_TEMPLATES: Dict[str, str] = {
        "Concept.md": "---\ntags: [concept]\n---\n\n# {{title}}\n\n## Definition\n\n## Key Points\n\n## Links\n",
        "Source.md": "---\ntags: [source-note]\n---\n\n# {{title}}\n\n## Summary\n\n## Timeline\n",
        "Daily.md": "---\ntags: [daily]\n---\n\n# {{title}}\n\n## Notes\n\n## Tasks\n",
    }

    def ensure_defaults(self) -> None:
        template_root = os.path.join(Config.OBSIDIAN_VAULT_PATH, self.TEMPLATE_DIR)
        os.makedirs(template_root, exist_ok=True)
        for filename, content in self.DEFAULT_TEMPLATES.items():
            path = os.path.join(template_root, filename)
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

    def list_templates(self) -> List[str]:
        self.ensure_defaults()
        template_root = os.path.join(Config.OBSIDIAN_VAULT_PATH, self.TEMPLATE_DIR)
        return sorted([name for name in os.listdir(template_root) if name.endswith(".md")])

    def render_template(self, template_name: str, title: str) -> str:
        self.ensure_defaults()
        path = os.path.join(Config.OBSIDIAN_VAULT_PATH, self.TEMPLATE_DIR, template_name)
        if not os.path.exists(path):
            return f"---\ntags: [manual-note]\n---\n\n# {title}\n"
        with open(path, "r", encoding="utf-8") as f:
            return f.read().replace("{{title}}", title)


template_manager = TemplateManager()
