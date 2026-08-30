from graph.workflow import create_graph


def test_graph_compiles_without_contacting_ollama() -> None:
    graph = create_graph().get_graph()

    assert set(graph.nodes) == {
        "__start__",
        "__end__",
        "manager",
        "planner",
        "coder",
        "reviewer",
    }

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("__start__", "manager") in edges
    assert ("planner", "manager") in edges
    assert ("coder", "reviewer") in edges
    assert ("reviewer", "manager") in edges
