from sqlalchemy import func, select


def page(db, model, limit, offset, filters=()):
    total = db.scalar(select(func.count()).select_from(model).where(*filters))
    items = db.scalars(
        select(model).where(*filters).order_by(model.id).limit(limit).offset(offset)
    ).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}
