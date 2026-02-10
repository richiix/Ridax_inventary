from __future__ import annotations

import re

import httpx


BCV_URL = "https://www.bcv.org.ve/"


async def fetch_ves_rate_from_bcv() -> float:
    html = ""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(BCV_URL)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError:
        async with httpx.AsyncClient(timeout=15, verify=False) as insecure_client:
            response = await insecure_client.get(BCV_URL)
            response.raise_for_status()
            html = response.text

    patterns = [
        r"USD\s*</strong>\s*<span[^>]*>\s*([0-9\.,]+)",
        r"D[oó]lar\s*BCV[^0-9]*([0-9\.,]+)",
        r"id=['\"]dolar['\"][^>]*>\s*([0-9\.,]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            rate = _parse_decimal(match.group(1))
            if rate > 0:
                return rate

    raise ValueError("No se pudo extraer tasa USD/VES desde BCV")


def _parse_decimal(value: str) -> float:
    cleaned = value.strip().replace(" ", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    return round(float(cleaned), 6)
