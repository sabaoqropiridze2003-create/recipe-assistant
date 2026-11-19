from langgraph.graph import END, START, StateGraph

from app.graph.deps import ChefDeps
from app.graph.logic import (
    route_after_confirm,
    route_after_context,
    route_after_prepare,
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
    graph.add_node("build_shopping_list", nodes.build_shopping_list)
    graph.add_node("prepare_save_recipe", nodes.prepare_save_recipe)
    graph.add_node("confirm_action", nodes.confirm_action)
    graph.add_node("save_pending_action", nodes.save_pending_action)

    graph.add_edge(START, "understand_request")
    graph.add_conditional_edges(
        "understand_request",
        route_after_understand,
        {"refuse": "polite_refusal", "context": "load_context", "end": END},
    )
    graph.add_conditional_edges(
        "load_context",
        route_after_context,
        {
            "search": "search_recipes",
            "helper": "cooking_helper",
            "shopping": "build_shopping_list",
            "save_recipe": "prepare_save_recipe",
        },
    )
    for builder_node in ("build_shopping_list", "prepare_save_recipe"):
        graph.add_conditional_edges(
            builder_node,
            route_after_prepare,
            {"confirm": "confirm_action", "compose": "compose_answer"},
        )
    graph.add_conditional_edges(
        "confirm_action",
        route_after_confirm,
        {"save": "save_pending_action", "compose": "compose_answer"},
    )
    graph.add_edge("save_pending_action", "compose_answer")
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

    return graph.compile(checkpointer=checkpointer)
