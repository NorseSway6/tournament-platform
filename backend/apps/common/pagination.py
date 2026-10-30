from typing import Any


def paginate(queryset, page: int, page_size: int) -> dict[str, Any]:
    total = queryset.count()
    return {
        "items": list(queryset[(page - 1) * page_size : page * page_size]),
        "total": total,
        "page": page,
        "page_size": page_size,
    }
