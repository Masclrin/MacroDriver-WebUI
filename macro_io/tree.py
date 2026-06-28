from typing import Any, Dict, List


def build_macro_tree(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    root = {"name": "宏", "path": "宏", "folders": {}, "files": []}

    for item in items:
        rel = str(item.get("path", "")).strip().replace("\\", "/")
        if not rel:
            continue

        parts = [part for part in rel.split("/") if part]
        if not parts:
            continue

        node = root
        current_parts: List[str] = []
        for part in parts[:-1]:
            current_parts.append(part)
            folders = node["folders"]
            if part not in folders:
                folders[part] = {
                    "name": part,
                    "path": "/".join(current_parts),
                    "folders": {},
                    "files": [],
                }
            node = folders[part]

        node["files"].append(
            {
                "name": item.get("name") or parts[-1],
                "path": rel,
                "size": item.get("size"),
                "mtime": item.get("mtime"),
            }
        )

    def _to_list(node: Dict[str, Any]) -> Dict[str, Any]:
        folder_values = list(node["folders"].values())
        folder_values.sort(key=lambda x: x["name"])
        files = list(node["files"])
        files.sort(key=lambda x: x["path"])
        return {
            "name": node["name"],
            "path": node["path"],
            "folders": [_to_list(child) for child in folder_values],
            "files": files,
        }

    return _to_list(root)
