"""Conversa com o agente na AWS e mostra cada ferramenta que ele chamou.

  uv run python scripts/chat.py            # alias de teste (DRAFT)
  uv run python scripts/chat.py --live     # alias publicado

Cada mensagem custa tokens do modelo.
"""

import argparse

from agent_client.client import DRAFT_ALIAS_ID, ask, terraform_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="usa o alias 'live'")
    args = parser.parse_args()

    outputs = terraform_outputs()
    alias = outputs["agent_alias_id"] if args.live else DRAFT_ALIAS_ID
    session_id = None
    print(f"agente {outputs['agent_id']} / alias {alias}. Ctrl+D para sair.\n")

    while True:
        try:
            question = input("você> ").strip()
        except EOFError:
            print()
            return
        if not question:
            continue
        turn = ask(question, outputs["agent_id"], alias, session_id, outputs["region"])
        session_id = turn.session_id  # mantém o contexto da conversa
        for call in turn.tool_calls:
            print(f"  [tool] {call.name} {call.params}")
        print(f"agente> {turn.text}\n")


if __name__ == "__main__":
    main()
