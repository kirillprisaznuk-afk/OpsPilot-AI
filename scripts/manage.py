import argparse
import json
import time

from app.db.session import engine
from app.services.integrity import load_dataset, validate
from app.services.scenarios import verify_scenarios
from app.services.seeding import reset, seed
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description="OpsPilot synthetic database maintenance")
    parser.add_argument("command", choices=["seed", "reset", "verify"])
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    start = time.perf_counter()
    with Session(engine()) as db, db.begin():
        if args.command == "seed":
            result = seed(db)
        elif args.command == "reset":
            reset(db, args.confirm)
            result = {"reset": True}
        else:
            result = {**validate(load_dataset(db)), "scenarios": verify_scenarios(db)}
    print(
        json.dumps(
            {**result, "elapsed_seconds": round(time.perf_counter() - start, 3)},
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
