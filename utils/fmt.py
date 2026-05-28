"""utils/fmt.py — Formatação brasileira"""
from datetime import datetime

def datahora_br(v) -> str:
    if not v: return "—"
    if isinstance(v, str):
        try: v = datetime.strptime(v[:19].replace("T"," "), "%Y-%m-%d %H:%M:%S")
        except: return v[:16].replace("T"," ")
    return v.strftime("%d/%m/%Y %H:%M")

def numero_br(v, dec=0) -> str:
    if v is None: return "—"
    try:
        s = f"{float(v):,.{dec}f}"
        return s.replace(",","X").replace(".",",").replace("X",".")
    except: return str(v)

def qtd_br(v) -> str:
    if v is None: return "—"
    try:
        f = float(v)
        if f == int(f): return numero_br(int(f), 0)
        s = numero_br(f, 3)
        if "," in s: s = s.rstrip("0").rstrip(",")
        return s
    except: return str(v)

def moeda_br(v) -> str:
    return f"R$ {numero_br(v, 2)}" if v is not None else "—"
