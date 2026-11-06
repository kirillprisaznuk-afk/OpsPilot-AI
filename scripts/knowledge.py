"""Controlled local maintenance. No write/upload HTTP endpoints."""

import argparse
import json

from app.db.session import engine
from app.knowledge.citations import resolve
from app.knowledge.corpus import documents, source, validate_metadata
from app.knowledge.embeddings import download_model
from app.knowledge.indexing import index_corpus
from app.knowledge.schema import chunks
from app.knowledge.service import status
from sqlalchemy import select, text
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["download-model", "index", "status", "verify-sources", "verify-citations"],
    )
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if args.command == "download-model":
        print(json.dumps(download_model(), indent=2))
        return
    with Session(engine()) as db, db.begin():
        if args.command != "index":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        if args.command == "index":
            result = index_corpus(db, rebuild=args.rebuild)
        elif args.command == "status":
            result = status(db)
        elif args.command == "verify-sources":
            rows = documents(db)
            for meta in rows:
                validate_metadata(meta, source(meta))
            result = {"validated_versions": len(rows)}
        else:
            ids = list(db.scalars(select(chunks.c.id)))
            for identifier in ids:
                resolve(db, "kc_" + identifier)
            result = {"validated_citations": len(ids)}
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
