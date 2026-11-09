"""Cortes de PD por segmento publicados por la gerencia y su efecto en la bandeja.

Regla: a cada solicitud se le aplica la política activa más reciente cuyo segmento
coincide con el suyo; si ninguna coincide, el corte general (config.CORTE_PD).
"""
from __future__ import annotations

import pandas as pd

from src import config as C, datos

FILTRO_A_SEGMENTO = {"F3": "SEG_DTI", "F4": "SEG_ENGANCHE", "F5": "SEG_PAGOS", "F6": "SEG_BANCARROTA"}


def segmento_activo(filtros: dict) -> dict:
    """Solo los filtros con un valor distinto de «Todos» definen el segmento."""
    return {f: v for f, v in filtros.items() if v not in (None, C.TODOS)}


def coincide(segmento: dict, fila_seg: dict) -> bool:
    return all(fila_seg.get(FILTRO_A_SEGMENTO[f]) == v for f, v in segmento.items())


def corte_de(fila_seg: dict, activas: pd.DataFrame) -> tuple[float, dict | None]:
    """Corte vigente para una solicitud ya segmentada y la política que lo define."""
    for _, pol in activas.sort_values("id", ascending=False).iterrows():
        if coincide(pol["segmento"], fila_seg):
            return float(pol["corte_nuevo"]), pol.to_dict()
    return C.CORTE_PD, None


def corte_vigente_segmento(segmento: dict, activas: pd.DataFrame) -> float:
    """Corte que hoy aplica exactamente a ese segmento (para «corte anterior»)."""
    for _, pol in activas.sort_values("id", ascending=False).iterrows():
        if pol["segmento"] == segmento:
            return float(pol["corte_nuevo"])
    return C.CORTE_PD


def segmentar_cola(cola: pd.DataFrame, cortes_dti: tuple[float, float]) -> pd.DataFrame:
    """Segmentos de cada solicitud. Un dato faltante se segmenta con la mediana imputada."""
    return datos.segmentar(cola, cortes_dti)


def describir(segmento: dict) -> str:
    if not segmento:
        return "toda la cartera"
    return " · ".join(f"{C.FILTROS[f]['nombre']} = {v}" for f, v in segmento.items())
