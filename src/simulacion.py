"""Datos SIMULADOS para lo que la base aún no trae (folios, fechas, decisiones).

Regla: lo simulado siempre se construye a partir de filas REAL del holdout y se
rotula SIMULADO en pantalla. Todo es determinista por fecha y escenario, para que
cada recarga de la página muestre los mismos números.
"""
from __future__ import annotations

import zlib
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src import config as C
from src.modelo import ModeloPD, evaluar

ANALISTAS = ["A-017", "A-022"]

ESCENARIOS = {
    "drift": "Drift en DTI y sobre-aprobación desde las 10:00",
    "normal": "Operación normal",
    "atrasada": "Carga atrasada (sin datos nuevos hace 135 min)",
    "nulos": "Carga con datos incompletos desde las 11:00",
}


def _semilla(*partes) -> int:
    return zlib.crc32("|".join(map(str, partes)).encode())


# ---------------------------------------------------------------------------
# Reloj operativo
# ---------------------------------------------------------------------------
def ahora_local() -> datetime:
    return datetime.now(ZoneInfo(C.ZONA_HORARIA)).replace(tzinfo=None)


def reloj_operativo(ahora: datetime | None = None) -> tuple[datetime, str | None]:
    """Hora del monitor dentro de la jornada 08:00–18:00 y una nota si se ajustó."""
    ahora = ahora or ahora_local()
    inicio = datetime.combine(ahora.date(), time(8, 15))
    cierre = datetime.combine(ahora.date(), time(18, 0))
    if ahora < inicio:
        ayer = datetime.combine(ahora.date() - timedelta(days=1), time(18, 0))
        return ayer, f"Antes de la jornada ({ahora:%H:%M}): se muestra el cierre de ayer a las 18:00."
    if ahora > cierre:
        return cierre, f"Jornada cerrada ({ahora:%H:%M}): se muestra el día hasta su cierre a las 18:00."
    return ahora, None


# ---------------------------------------------------------------------------
# Bandeja de solicitudes (P1/P2)
# ---------------------------------------------------------------------------
def folio_de(indice: int) -> str:
    return f"AC-26{int(indice):06d}"


def cola_base(modelo: ModeloPD, analista_id: str, n: int = 25) -> tuple[pd.DataFrame, dict]:
    """Solicitudes asignadas a un analista: variables REAL de filas del holdout
    (sin DEFAULT), con folio, hora y casos de excepción SIMULADOS."""
    hold = modelo.holdout
    k = ANALISTAS.index(analista_id) if analista_id in ANALISTAS else len(ANALISTAS)
    pool = hold.index[(np.arange(len(hold)) % (len(ANALISTAS) + 1)) == k]
    rng = np.random.default_rng(_semilla("cola", analista_id))
    elegidos = rng.choice(pool, n, replace=False)
    cola = hold.loc[elegidos, modelo.variables].copy()
    cola.insert(0, "FOLIO", [folio_de(i) for i in elegidos])
    cola["RECIBIDA_MIN"] = rng.integers(8, 330, n)
    cola["ANALISTA_ID"] = analista_id
    cola = cola.reset_index(drop=True)

    # Casos de excepción (SIMULADO) elegidos entre PD medias/altas para que se vean.
    pd_orig = hold.loc[elegidos, "PD"].to_numpy()
    candidatos = [i for i in np.argsort(-pd_orig) if 0.10 <= pd_orig[i] <= 0.30]
    candidatos = (candidatos + list(range(n)))[:3]
    originales: dict[str, dict] = {}
    excepciones = [("SAVINGS_BALANCE", np.nan), ("DEBT_TO_INCOME", np.nan), ("LOAN_TO_VALUE", 1.12)]
    for pos, (var, valor) in zip(candidatos, excepciones):
        folio = cola.at[pos, "FOLIO"]
        originales[folio] = {var: float(cola.at[pos, var])}
        cola.at[pos, var] = valor
    return cola, originales


def evaluar_cola(modelo: ModeloPD, cola: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for _, r in cola.iterrows():
        ev = evaluar(modelo, r.to_dict())
        filas.append({"FOLIO": r["FOLIO"], "PD": ev.pd, "NIVEL": ev.nivel, "CALIDAD": ev.calidad,
                      "SUGERENCIA": ev.sugerencia})
    return cola.merge(pd.DataFrame(filas), on="FOLIO")


def texto_hace(minutos: float) -> str:
    minutos = int(minutos)
    if minutos < 60:
        return f"hace {minutos} min"
    h, m = divmod(minutos, 60)
    return f"hace {h} h {m:02d} min" if m else f"hace {h} h"


# ---------------------------------------------------------------------------
# Flujo de solicitudes para el monitor (P4)
# ---------------------------------------------------------------------------
def ultima_carga(reloj: datetime, escenario: str) -> datetime:
    redondeo = reloj - timedelta(minutes=reloj.minute % C.REFRESCO_MIN, seconds=reloj.second,
                                 microseconds=reloj.microsecond)
    if escenario == "atrasada":
        return reloj - timedelta(minutes=135)
    return redondeo


def flujo(modelo: ModeloPD, escenario: str, reloj: datetime, dias: int = 7) -> pd.DataFrame:
    """Solicitudes de los últimos `dias` días: filas REAL del holdout con hora,
    decisión del analista y, según escenario, drift o faltantes (SIMULADO)."""
    hold = modelo.holdout.reset_index(drop=True)
    z_dti = ((hold["DEBT_TO_INCOME"] - hold["DEBT_TO_INCOME"].mean()) / hold["DEBT_TO_INCOME"].std()).to_numpy()
    peso_drift = np.exp(0.8 * z_dti)
    peso_drift /= peso_drift.sum()
    corte_carga = ultima_carga(reloj, escenario)
    bloques = []
    for d in range(dias - 1, -1, -1):
        dia = reloj.date() - timedelta(days=d)
        hoy = d == 0
        rng = np.random.default_rng(_semilla("flujo", dia.isoformat(), escenario if hoy else "normal"))
        inicio = datetime.combine(dia, time(8, 0))
        fin = min(corte_carga, datetime.combine(dia, time(18, 0))) if hoy else datetime.combine(dia, time(18, 0))
        t = inicio
        while t < fin:
            n = rng.poisson(12)
            drift_activo = hoy and escenario == "drift" and t >= datetime.combine(dia, time(10, 0))
            p = peso_drift if drift_activo else None
            idx = rng.choice(len(hold), n, p=p)
            b = hold.loc[idx, C.VARIABLES_DRIFT + ["PD"]].copy()
            b["ts"] = [t + timedelta(minutes=float(m)) for m in rng.uniform(0, C.REFRESCO_MIN, n)]
            modelo_aprueba = b["PD"].to_numpy() < C.CORTE_PD
            u = rng.uniform(size=n)
            prob_override = 0.72 if drift_activo else 0.06
            analista_aprueba = np.where(modelo_aprueba, u < 0.95, u < prob_override)
            b["modelo_aprueba"] = modelo_aprueba
            b["analista_aprueba"] = analista_aprueba
            nulos_activo = hoy and escenario == "nulos" and t >= datetime.combine(dia, time(11, 0))
            b["incompleto"] = rng.uniform(size=n) < (0.08 if nulos_activo else 0.004)
            bloques.append(b)
            t += timedelta(minutes=C.REFRESCO_MIN)
    out = pd.concat(bloques, ignore_index=True)
    out["dia"] = out["ts"].dt.date
    out["categoria"] = np.select(
        [out["modelo_aprueba"] == out["analista_aprueba"], out["analista_aprueba"]],
        ["Coincide con el modelo", "Aprueba lo que el modelo rechaza"],
        default="Rechaza lo que el modelo aprueba",
    )
    return out.sort_values("ts").reset_index(drop=True)


def recortar_ventana(f: pd.DataFrame, ventana: str, reloj: datetime) -> pd.DataFrame:
    if ventana == "Última hora":
        return f[f["ts"] > reloj - timedelta(hours=1)]
    if ventana == "Hoy":
        return f[f["dia"] == reloj.date()]
    return f


def ventana_anterior(f: pd.DataFrame, ventana: str, reloj: datetime) -> pd.DataFrame:
    """Periodo de comparación para el Δ: la hora previa o el día previo."""
    if ventana == "Última hora":
        return f[(f["ts"] > reloj - timedelta(hours=2)) & (f["ts"] <= reloj - timedelta(hours=1))]
    if ventana == "Hoy":
        return f[f["dia"] == reloj.date() - timedelta(days=1)]
    return f[f["dia"] < reloj.date()]


def serie_aprobacion(f: pd.DataFrame, dia: date) -> pd.DataFrame:
    d = f[f["dia"] == dia].copy()
    if d.empty:
        return pd.DataFrame(columns=["ts", "aprobacion", "n"])
    d["bloque"] = d["ts"].dt.floor(f"{C.REFRESCO_MIN}min")
    g = d.groupby("bloque").agg(aprobadas=("analista_aprueba", "sum"), n=("analista_aprueba", "size"))
    g["acum_ap"] = g["aprobadas"].cumsum()
    g["acum_n"] = g["n"].cumsum()
    # Aprobación móvil de la última hora (4 bloques) para que la línea no tiemble.
    g["aprobacion"] = g["aprobadas"].rolling(4, min_periods=1).sum() / g["n"].rolling(4, min_periods=1).sum()
    return g.reset_index().rename(columns={"bloque": "ts"})
