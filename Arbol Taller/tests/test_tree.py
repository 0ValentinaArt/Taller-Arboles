import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tree import Gate, Node, create_default_tree


def test_structure_and_traversals():
    tree = create_default_tree()
    dfs_ids = [n.id for n in tree.root.dfs()]
    bfs_ids = [n.id for n in tree.root.bfs()]
    assert dfs_ids[0] == bfs_ids[0] == "root"
    assert sorted(dfs_ids) == sorted(bfs_ids)
    assert bfs_ids[1:6] == [
        "weak-passwords", "phishing", "missing-mfa",
        "excessive-permissions", "weak-monitoring",
    ]


def test_and_or_gates():
    parent_and = Node("a", "a", gate=Gate.AND)
    parent_and.add_child(Node("x", "x", base_probability=0.5))
    parent_and.add_child(Node("y", "y", base_probability=0.4))
    assert abs(parent_and.probability() - 0.2) < 1e-9

    parent_or = Node("o", "o", gate=Gate.OR)
    parent_or.add_child(Node("x", "x", base_probability=0.5))
    parent_or.add_child(Node("y", "y", base_probability=0.4))
    assert abs(parent_or.probability() - 0.7) < 1e-9


def test_mitigations_reduce_risk():
    tree = create_default_tree()
    before = tree.root.probability()
    tree.toggle_mitigation("mfa-enforcement")
    assert tree.root.probability() < before
    tree.reset()
    assert abs(tree.root.probability() - before) < 1e-9


def test_path_and_search():
    tree = create_default_tree()
    node = tree.get_node("mfa-disabled")
    assert [n.id for n in node.path_from_root()] == ["root", "missing-mfa", "mfa-disabled"]
    assert tree.search("autenticacion")  # accent-insensitive
