"""HackTree REST API. Run with: python main.py"""
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tree import create_default_tree

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="HackTree API", version="1.0.0")
attack_tree = create_default_tree()  # In-memory state, no database needed.


def require_node(node_id: str):
    node = attack_tree.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@app.get("/api/tree")
def get_tree() -> dict:
    return attack_tree.root.to_dict()


@app.get("/api/stats")
def get_stats() -> dict:
    return attack_tree.stats()


@app.get("/api/nodes/{node_id}")
def get_node(node_id: str) -> dict:
    return require_node(node_id).to_dict()


@app.get("/api/nodes/{node_id}/path")
def get_node_path(node_id: str) -> dict:
    node = require_node(node_id)
    return {"path": [{"id": n.id, "label": n.label} for n in node.path_from_root()]}


@app.get("/api/search")
def search_nodes(q: str = Query(..., min_length=1)) -> dict:
    matches = attack_tree.search(q)
    return {
        "matches": [{"id": n.id, "label": n.label} for n in matches],
    }


@app.get("/api/traversal")
def get_traversal(order: Literal["dfs", "bfs"] = "dfs") -> dict:
    root = attack_tree.root
    nodes = root.dfs() if order == "dfs" else root.bfs()
    return {"order": order, "nodes": [{"id": n.id, "label": n.label} for n in nodes]}


@app.post("/api/mitigations/{mitigation_id}/toggle")
def toggle_mitigation(mitigation_id: str) -> dict:
    mitigation = attack_tree.toggle_mitigation(mitigation_id)
    if mitigation is None:
        raise HTTPException(status_code=404, detail="Mitigation not found")
    return mitigation.to_dict()


@app.post("/api/reset")
def reset_simulation() -> dict:
    attack_tree.reset()
    return {"status": "reset"}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
