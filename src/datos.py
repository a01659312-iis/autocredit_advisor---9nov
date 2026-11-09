"""Carga, validación y segmentación de la base REAL."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src import config as C


class ErrorDeDatos(Exception):
    """La base no existe o no trae el esquema esperado."""


def leer_base(ruta: Path = C.RUTA_DATOS) -> pd.DataFrame:
    if not Path(ruta).exists():
        raise ErrorDeDatos(
            f"No se encontró la base en «{Path(ruta).relative_to(C.RAIZ) if Path(ruta).is_relative_to(C.RAIZ) else ruta}». "
            "Copia Base_SAS_Equipo3.csv dentro de la carpeta data/."
        )
    df = pd.read_csv(ruta)
    problemas = validar_esquema(df)
    if problemas:
        raise ErrorDeDatos("La base no trae el esquema esperado: " + "; ".join(problemas))
    return df


def validar_esquema(df: pd.DataFrame) -> list[str]:
    problemas = []
    faltan = [c for c in C.COLUMNAS_ESPERADAS if c not in df.columns]
    if faltan:
        problemas.append("faltan columnas " + ", ".join(faltan))
    if C.OBJETIVO in df.columns and not set(df[C.OBJETIVO].dropna().unique()) <= {0, 1}:
        problemas.append("DEFAULT debe ser 0/1")
    if len(df) < C.N_MINIMO:
        problemas.append(f"la base tiene menos de {C.N_MINIMO} filas")
    return problemas


def columnas_no_reguladas(df: pd.DataFrame) -> list[str]:
    """Columnas que llegaron y no están en la matriz de datos: se descartan (negar por defecto)."""
    return [c for c in df.columns if c not in C.COLUMNAS_ESPERADAS]


def cortes_terciles(serie: pd.Series) -> tuple[float, float]:
    q = serie.quantile([1 / 3, 2 / 3]).to_numpy()
    return float(q[0]), float(q[1])


def segmentar(df: pd.DataFrame, cortes_dti: tuple[float, float] | None = None) -> pd.DataFrame:
    """Agrega columnas SEG_* (CALCULADO sobre REAL)."""
    out = df.copy()
    if cortes_dti is None:
        cortes_dti = cortes_terciles(out["DEBT_TO_INCOME"])
    t1, t2 = cortes_dti
    out["SEG_DTI"] = pd.cut(out["DEBT_TO_INCOME"], [-np.inf, t1, t2, np.inf],
                            labels=C.SEGMENTOS["SEG_DTI"]["orden"]).astype(str)
    for seg in ("SEG_ENGANCHE", "SEG_PAGOS", "SEG_LTV"):
        spec = C.SEGMENTOS[seg]
        out[seg] = pd.cut(out[spec["columna"]], spec["bins"], labels=spec["orden"]).astype(str)
    out["SEG_BANCARROTA"] = out["BANKRUPTCY_FLAG"].map(C.SEGMENTOS["SEG_BANCARROTA"]["mapa"])
    return out


def aplicar_filtros(df: pd.DataFrame, filtros: dict[str, str]) -> pd.DataFrame:
    """filtros = {"F3": "Alto", ...}; "Todos" no filtra."""
    mascara = pd.Series(True, index=df.index)
    for fid, valor in filtros.items():
        if valor in (None, C.TODOS):
            continue
        col = C.FILTROS[fid]["columna"]
        mascara &= df[col] == valor
    return df[mascara]


def tasa_por_grupo(df: pd.DataFrame, filas: str, columnas: str | None = None) -> pd.DataFrame:
    """Tasa de default y n por grupo. Las celdas con n < N_MINIMO quedan sin tasa."""
    claves = [filas] + ([columnas] if columnas else [])
    g = df.groupby(claves, observed=True)[C.OBJETIVO].agg(tasa="mean", n="size").reset_index()
    g["suficiente"] = g["n"] >= C.N_MINIMO
    g.loc[~g["suficiente"], "tasa"] = np.nan
    return g


def describir_filtros(filtros: dict[str, str]) -> str:
    activos = [f"{C.FILTROS[f]['nombre']} = {v}" for f, v in filtros.items() if v not in (None, C.TODOS)]
    return " · ".join(activos) if activos else "sin filtros"


def formatear(variable: str, valor) -> str:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    tipo = C.FORMATO.get(variable, "num")
    if tipo == "pct":
        return f"{valor * 100:.1f}%"
    if tipo == "dinero":
        return f"${valor:,.0f}"
    if tipo == "int":
        return f"{int(valor)}"
    if tipo == "bandera":
        return "Sí" if int(valor) == 1 else "No"
    return f"{valor:,.2f}"
