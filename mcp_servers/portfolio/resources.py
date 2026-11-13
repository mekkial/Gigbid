"""Resource templates so a host can load full items: portfolio://case/{id}, portfolio://proposal/{id}."""
import json

from mcp_servers.portfolio import tools


def case_resource(id: str) -> str:
    return tools.get_case_study(id).model_dump_json(indent=2)


def proposal_resource(id: str) -> str:
    p = tools._state()["proposals"].get(id)
    if not p:
        raise ValueError(f"unknown proposal '{id}'")
    return json.dumps(p, indent=2)
