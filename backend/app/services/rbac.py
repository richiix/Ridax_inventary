from __future__ import annotations

import json


ROLE_PERMISSIONS: dict[str, list[str]] = {
    "Admin": [
        "dashboard:view",
        "articles:view",
        "articles:write",
        "inventory:view",
        "inventory:write",
        "sales:view",
        "sales:write",
        "purchases:view",
        "purchases:write",
        "reports:view",
        "settings:view",
        "settings:write",
        "integrations:use",
    ],
    "Gerente": [
        "dashboard:view",
        "articles:view",
        "articles:write",
        "inventory:view",
        "inventory:write",
        "sales:view",
        "sales:write",
        "purchases:view",
        "purchases:write",
        "reports:view",
        "settings:view",
        "integrations:use",
    ],
    "Vendedor": [
        "dashboard:view",
        "articles:view",
        "inventory:view",
        "sales:view",
        "sales:write",
        "integrations:use",
    ],
}


def available_permissions() -> list[str]:
    catalog: set[str] = set()
    for perms in ROLE_PERMISSIONS.values():
        catalog.update(perms)
    return sorted(catalog)


def serialize_permissions(role_name: str) -> str:
    permissions = ROLE_PERMISSIONS.get(role_name, [])
    return json.dumps(permissions)


def has_permission(permissions_raw: str, permission: str) -> bool:
    try:
        permissions = json.loads(permissions_raw)
    except json.JSONDecodeError:
        permissions = []
    return permission in permissions


def parse_permissions(permissions_raw: str) -> list[str]:
    try:
        permissions = json.loads(permissions_raw)
    except json.JSONDecodeError:
        return []
    return permissions if isinstance(permissions, list) else []
