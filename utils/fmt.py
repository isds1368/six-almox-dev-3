"""utils/fmt.py — Formatação padrão brasileiro"""
from datetime import datetime


def datahora_br(value) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.strptime(value[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value[:16].replace("T", " ")
    return value.strftime("%d/%m/%Y %H:%M")


def data_br(value) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return str(value)
    return value.strftime("%d/%m/%Y")


def numero_br(value, dec: int = 0) -> str:
    if value is None:
        return "—"
    try:
        s = f"{float(value):,.{dec}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value)


def qtd_br(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
        if v == int(v):
            return numero_br(int(v), 0)
        s = numero_br(v, 3)
        # Remove zeros desnecessários
        if "," in s:
            s = s.rstrip("0").rstrip(",")
        return s
    except Exception:
        return str(value)


def moeda_br(value) -> str:
    if value is None:
        return "—"
    return f"R$ {numero_br(value, 2)}"
