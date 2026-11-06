import json
from pathlib import Path

from app.db.session import engine
from app.knowledge.evaluation import evaluate
from sqlalchemy import text
from sqlalchemy.orm import Session


def main():
    with Session(engine()) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        result = evaluate(db)
    Path("reports/stage3-retrieval-evaluation.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                mode: {k: v for k, v in values.items() if k != "cases"}
                for mode, values in result["modes"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
