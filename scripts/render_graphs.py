"""Render both graphs from code to docs/images (mermaid .mmd + png when the mermaid API is reachable)."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from agent.graphs.bid_graph import build_bid_graph
from agent.graphs.conversation_graph import build_conversation_graph

for name, g in [("bid_graph", build_bid_graph(None, InMemoryStore(), MemorySaver())), ("conversation_graph", build_conversation_graph(None, MemorySaver()))]:
    gr = g.get_graph()
    open(f"docs/images/{name}.mmd", "w").write(gr.draw_mermaid())
    try:
        open(f"docs/images/{name}.png", "wb").write(gr.draw_mermaid_png())
        print(name, "png ok")
    except Exception as e:
        print(name, "mermaid saved; png skipped:", str(e)[:80])
