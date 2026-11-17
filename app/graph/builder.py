from langgraph.graph import END, START, StateGraph

from app.graph.deps import ChefDeps
from app.graph.logic import (
    route_after_context,
    route_after_safety,
    route_after_understand,
)
from app.graph.nodes import ChefNodes
from app.graph.state import ChefState


def build_chef_graph(deps: ChefDeps, checkpointer=None):
    nodes = ChefNodes(deps)
    graph = StateGraph(ChefState)

    graph.add_node("understand_request", nodes.understand_request)
    graph.add_node("polite_refusal", nodes.polite_refusal)
    graph.add_node("load_context", nodes.load_context)
    graph.add_node("search_recipes", nodes.search_recipes)
    graph.add_node("safety_filter", nodes.safety_filter)
    graph.add_node("relax_constraints", nodes.relax_constraints)
    graph.add_node("generate_recipe", nodes.generate_recipe)
    graph.add_node("cooking_helper", nodes.cooking_helper)
    graph.add_node("compose_answer", nodes.compose_answer)
    graph.add_node("coming_soon", nodes.coming_soon)  # temporary: replaced in Part C

    graph.add_edge(START, "understand_request")
    graph.add_conditional_edges(
        "understand_request",
        route_after_understand,
        {"refuse": "polite_refusal", "context": "load_context", "end": END},
    )
    graph.add_conditional_edges(
        "load_context",
        route_after_context,
        {"search": "search_recipes", "helper": "cooking_helper", "not_ready": "coming_soon"},
    )
    graph.add_edge("search_recipes", "safety_filter")
    graph.add_conditional_edges(
        "safety_filter",
        route_after_safety,
        {
            "compose": "compose_answer",
            "relax": "relax_constraints",
            "generate": "generate_recipe",
        },
    )
    graph.add_edge("relax_constraints", "search_recipes")
    graph.add_edge("generate_recipe", "safety_filter")  
    graph.add_edge("cooking_helper", "compose_answer")
    graph.add_edge("compose_answer", END)
    graph.add_edge("polite_refusal", END)
    graph.add_edge("coming_soon", END)

    return graph.compile(checkpointer=checkpointer)
