"""Avalia o roteamento do agente contra o golden set.

  uv run python eval/run_eval.py               # 1 execução por caso
  uv run python eval/run_eval.py --repeat 3    # mede a variância entre execuções

Mede duas coisas, a partir do trace (não do texto da resposta):
- tool: o agente chamou a ferramenta esperada (ou nenhuma, quando esperado)?
- params: os parâmetros batem com as regex esperadas (sem caixa, sem acento)?

Rode a cada mudança de prompt, schema ou modelo e compare com o último resultado.
Cada caso é uma sessão nova e custa tokens.
"""

import argparse
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from agent_client.client import DRAFT_ALIAS_ID, AgentTurn, ask, terraform_outputs
from catalog_action.matching import normalize

HERE = Path(__file__).resolve().parent


def first_tool(turn: AgentTurn):
    return turn.tool_calls[0] if turn.tool_calls else None


def grade(case: dict, turn: AgentTurn) -> dict:
    expect = case["expect"]
    call = first_tool(turn)
    called = call.name if call else "none"
    tool_ok = called == expect["tool"]

    params_ok = tool_ok
    if tool_ok and call and call.kind == "action":
        for name, pattern in expect.get("params", {}).items():
            value = normalize(call.params.get(name, ""))
            if not re.search(pattern, value):
                params_ok = False
    return {
        "id": case["id"],
        "called": called,
        "params": call.params if call else {},
        "tool_ok": tool_ok,
        "params_ok": params_ok,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--live", action="store_true", help="avalia o alias 'live'")
    args = parser.parse_args()

    outputs = terraform_outputs()
    alias = outputs["agent_alias_id"] if args.live else DRAFT_ALIAS_ID
    cases = [json.loads(line) for line in (HERE / "golden.jsonl").read_text().splitlines() if line]

    results = []
    for case in cases:
        for run in range(args.repeat):
            started = time.perf_counter()
            turn = ask(case["question"], outputs["agent_id"], alias, region=outputs["region"])
            result = grade(case, turn) | {
                "run": run,
                "seconds": round(time.perf_counter() - started, 1),
            }
            results.append(result)
            mark = "ok " if result["params_ok"] else "ERR"
            print(f"{mark} {case['id']:<22} -> {result['called']} {result['params']}")

    n = len(results)
    tool_acc = sum(r["tool_ok"] for r in results) / n
    params_acc = sum(r["params_ok"] for r in results) / n
    print(f"\ntool accuracy {tool_acc:.0%}  |  tool+params accuracy {params_acc:.0%}  |  n={n}")

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "alias": alias,
        "repeat": args.repeat,
        "tool_accuracy": tool_acc,
        "params_accuracy": params_acc,
        "results": results,
    }
    (out_dir / f"{stamp}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
