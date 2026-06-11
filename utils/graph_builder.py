import os
from typing import Dict, List

from Crucible.config import Config
from Crucible.utils.source_index import source_index
from Crucible.utils.wiki_editor import wiki_editor


class KnowledgeGraphBuilder:
    """从 Obsidian Markdown 双链生成轻量关系图谱数据。"""

    def __init__(self, vault_path: str = Config.OBSIDIAN_VAULT_PATH):
        self.vault_path = vault_path

    def build_graph(self) -> Dict[str, List[Dict]]:
        nodes = {}
        edges = []

        if not os.path.exists(self.vault_path):
            return {"nodes": [], "edges": []}

        for root, _, files in os.walk(self.vault_path):
            for file_name in files:
                if not file_name.endswith(".md"):
                    continue

                path = os.path.join(root, file_name)
                source = os.path.splitext(file_name)[0]
                rel_path = os.path.relpath(path, self.vault_path).replace("\\", "/")
                nodes.setdefault(source, {"id": source, "path": rel_path, "out_degree": 0, "in_degree": 0})

                content = wiki_editor.read_wiki(path)
                for target in wiki_editor.extract_wiki_links(content):
                    target = target.strip()
                    if not target:
                        continue
                    target_name = os.path.splitext(os.path.basename(target))[0]
                    nodes.setdefault(target_name, {"id": target_name, "path": "", "out_degree": 0, "in_degree": 0})
                    self._add_edge(nodes, edges, source, target_name, rel_path, "wiki_link", "")

        for edge in source_index.graph_edges():
            self._add_edge(
                nodes,
                edges,
                edge["source"],
                edge["target"],
                edge["source_path"],
                edge["type"],
                edge.get("timestamp", ""),
            )

        return {"nodes": list(nodes.values()), "edges": edges}

    def _add_edge(
        self,
        nodes: Dict,
        edges: List[Dict],
        source: str,
        target: str,
        source_path: str,
        edge_type: str,
        timestamp: str,
    ) -> None:
        nodes.setdefault(source, {"id": source, "path": source_path, "out_degree": 0, "in_degree": 0})
        nodes.setdefault(target, {"id": target, "path": "", "out_degree": 0, "in_degree": 0})
        nodes[source]["out_degree"] += 1
        nodes[target]["in_degree"] += 1
        edges.append({
            "source": source,
            "target": target,
            "source_path": source_path,
            "type": edge_type,
            "timestamp": timestamp,
        })

    def build_summary(self, limit: int = 20) -> str:
        graph = self.build_graph()
        nodes = sorted(
            graph["nodes"],
            key=lambda item: item["in_degree"] + item["out_degree"],
            reverse=True,
        )
        lines = [
            f"节点数: {len(graph['nodes'])}",
            f"关系数: {len(graph['edges'])}",
            "",
            "核心节点:",
        ]
        for node in nodes[:limit]:
            lines.append(f"- {node['id']} (in={node['in_degree']}, out={node['out_degree']})")
        return "\n".join(lines)


knowledge_graph_builder = KnowledgeGraphBuilder()
