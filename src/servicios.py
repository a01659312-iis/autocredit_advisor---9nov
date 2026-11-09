"""Capa de servicio con caché. Cada función que entrega datos recibe el rol, de modo
que la caché queda separada por rol y nunca se mezclan resultados (Bloque F)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import almacen, config as C, datos, seguridad, simulacion
from src.modelo import ModeloPD, entrenar


@st.cache_data(show_spinner=False)
def _base_cruda() -> pd.DataFrame:
    return datos.leer_base()


@st.cache_resource(show_spinner="Entrenando el modelo de PD con la base REAL…")
def modelo() -> ModeloPD:
    return entrenar(_base_cruda())


@st.cache_resource(show_spinner=False)
def auc_con_variable_excluida() -> float:
    variables = C.VARIABLES_MODELO + list(C.EXCLUIDAS_DEL_MODELO)
    return entrenar(_base_cruda(), variables=variables).metricas["auc"]


def estado_datos() -> tuple[bool, str]:
    try:
        _base_cruda()
        return True, ""
    except datos.ErrorDeDatos as e:
        return False, str(e)


# --- Mariana: solo agregados -------------------------------------------------
@st.cache_data(show_spinner=False)
def _base_segmentada() -> pd.DataFrame:
    return datos.segmentar(_base_cruda())


@st.cache_data(show_spinner=False)
def cortes_dti() -> tuple[float, float]:
    return datos.cortes_terciles(_base_cruda()["DEBT_TO_INCOME"])


def _exigir(rol: str, dato: str) -> None:
    if not seguridad.puede_agregado(rol, dato):
        raise PermissionError(f"El rol {rol} no puede recibir {dato}.")


@st.cache_data(show_spinner=False)
def resumen_corte(rol: str, filtros: tuple) -> dict:
    _exigir(rol, "DEFAULT")
    df = datos.aplicar_filtros(_base_segmentada(), dict(filtros))
    return {"n": int(len(df)), "total": int(len(_base_segmentada())),
            "tasa": float(df[C.OBJETIVO].mean()) if len(df) else float("nan")}


@st.cache_data(show_spinner=False)
def tasa_cruzada(rol: str, filtros: tuple, filas: str, columnas: str | None) -> pd.DataFrame:
    _exigir(rol, "SEGMENTOS (DTI, enganche, pagos, LTV)")
    df = datos.aplicar_filtros(_base_segmentada(), dict(filtros))
    return datos.tasa_por_grupo(df, filas, columnas)


@st.cache_data(show_spinner=False)
def curva_politica(rol: str, filtros: tuple) -> tuple[pd.DataFrame, int]:
    """Curva corte vs aprobación sobre el holdout del segmento (PD CALCULADO)."""
    _exigir(rol, "PD_MODELO")
    from src.modelo import curva_corte
    m = modelo()
    hold = datos.segmentar(m.holdout, cortes_dti())
    sub = datos.aplicar_filtros(hold, dict(filtros))
    if len(sub) < C.N_MINIMO:
        return pd.DataFrame(), int(len(sub))
    return curva_corte(sub["PD"].to_numpy(), sub[C.OBJETIVO].to_numpy()), int(len(sub))


# --- Adrián: solo sus casos ---------------------------------------------------
@st.cache_data(show_spinner=False)
def _cola_evaluada(analista_id: str) -> tuple[pd.DataFrame, dict]:
    m = modelo()
    cola, originales = simulacion.cola_base(m, analista_id)
    return cola, originales


@st.cache_data(show_spinner=False)
def _evaluar_cola(analista_id: str, documentos: tuple, politicas_json: str) -> pd.DataFrame:
    """Evalúa cada solicitud con el corte de su segmento. Se cachea por analista, documentos
    recibidos y políticas activas: cuando la gerencia publica un corte, se recalcula sola."""
    import json
    from src import politica
    from src.modelo import evaluar

    m = modelo()
    cola, originales = _cola_evaluada(analista_id)
    cola = cola.copy()
    for folio in set(documentos) & set(originales):
        for var, valor in originales[folio].items():
            cola.loc[cola["FOLIO"] == folio, var] = valor
    activas = pd.DataFrame(json.loads(politicas_json))
    seg = politica.segmentar_cola(cola, cortes_dti())
    filas = []
    for i, r in cola.iterrows():
        fila_seg = seg.loc[i].to_dict()
        corte, pol = politica.corte_de(fila_seg, activas) if len(activas) else (C.CORTE_PD, None)
        ev = evaluar(m, r.to_dict(), corte=corte)
        base = evaluar(m, r.to_dict(), corte=C.CORTE_PD) if pol else ev
        filas.append({"FOLIO": r["FOLIO"], "PD": ev.pd, "NIVEL": ev.nivel, "CALIDAD": ev.calidad,
                      "SUGERENCIA": ev.sugerencia, "CORTE": corte,
                      "POLITICA_ID": int(pol["id"]) if pol else None,
                      "SUGERENCIA_GENERAL": base.sugerencia,
                      "SEGMENTO": " · ".join(str(fila_seg[c]) for c in ("SEG_DTI", "SEG_ENGANCHE"))})
    return cola.merge(pd.DataFrame(filas), on="FOLIO")


def _politicas_json() -> str:
    activas = almacen.politicas(solo_activas=True)
    return activas.to_json(orient="records", force_ascii=False) if len(activas) else "[]"


def cola_analista(usuario: seguridad.Usuario) -> tuple[pd.DataFrame, dict]:
    """Cola del analista con estados, documentos y cortes de política al día.
    Filtra por ANALISTA_ID en el servidor."""
    if usuario.rol != "analista" or not usuario.analista_id:
        raise PermissionError("Solo un analista con ANALISTA_ID recibe solicitudes.")
    _, originales = _cola_evaluada(usuario.analista_id)
    docs = tuple(sorted(almacen.documentos_recibidos() & set(originales)))
    cola = _evaluar_cola(usuario.analista_id, docs, _politicas_json()).copy()
    est = almacen.estados(usuario.analista_id)
    cola["ESTADO_SOLICITUD"] = cola["FOLIO"].map(est).fillna("Pendiente")
    cola = cola[cola["ANALISTA_ID"] == usuario.analista_id]
    columnas = ["FOLIO", "RECIBIDA_MIN", "PD", "NIVEL", "CALIDAD", "SUGERENCIA", "ESTADO_SOLICITUD", "CORTE",
                "POLITICA_ID", "SUGERENCIA_GENERAL", "SEGMENTO"] + \
        seguridad.columnas_individuales(usuario.rol, C.VARIABLES_MODELO)
    return cola[columnas], originales


def avisos_politica(usuario: seguridad.Usuario, cola: pd.DataFrame) -> list[dict]:
    """Cambios de corte publicados por la gerencia que el analista no ha visto, con las
    solicitudes de SU bandeja cuya sugerencia cambió (antes → ahora)."""
    from src import politica
    from src.modelo import evaluar

    todas = almacen.politicas(solo_activas=False)
    if todas.empty:
        return []
    vistos = almacen.avisos_vistos(usuario.email)
    nuevas = todas[~todas["id"].isin(vistos)]
    if nuevas.empty:
        return []
    m = modelo()
    seg = politica.segmentar_cola(cola, cortes_dti())
    pendientes = cola["ESTADO_SOLICITUD"] != "Resuelta hoy"
    avisos = []
    for _, pol in nuevas.sort_values("id").iterrows():
        cambios = []
        for i, r in cola[pendientes].iterrows():
            if not politica.coincide(pol["segmento"], seg.loc[i].to_dict()):
                continue
            antes = evaluar(m, r.to_dict(), corte=float(pol["corte_anterior"]))
            ahora = evaluar(m, r.to_dict(), corte=float(pol["corte_nuevo"]))
            if antes.sugerencia != ahora.sugerencia:
                cambios.append({"folio": r["FOLIO"], "pd": ahora.pd, "antes": antes.sugerencia,
                                "ahora": ahora.sugerencia})
        avisos.append({"id": int(pol["id"]), "autor": pol["autor"], "hora": pol["ts"][11:16],
                       "segmento": politica.describir(pol["segmento"]), "antes": float(pol["corte_anterior"]),
                       "ahora": float(pol["corte_nuevo"]), "cambios": cambios,
                       "revertida": str(pol["descripcion"]).endswith("(revertido)")})
    return avisos


# --- Mariana: partición de la cartera por riesgo --------------------------------
@st.cache_data(show_spinner=False)
def _base_con_pd() -> pd.DataFrame:
    """PD del modelo para los 80,000 créditos (dato propio) junto a sus segmentos."""
    b = _base_segmentada().copy()
    b["PD"] = modelo().puntuar(b)
    return b


@st.cache_data(show_spinner=False)
def particion_riesgo(rol: str, filtros: tuple, corte: float) -> pd.DataFrame:
    """Alto riesgo (PD ≥ corte) vs bajo riesgo, con cuántos cayeron en incumplimiento."""
    _exigir(rol, "PD_MODELO")
    _exigir(rol, "DEFAULT")
    b = datos.aplicar_filtros(_base_con_pd(), dict(filtros))
    total = len(b)
    total_inc = int(b[C.OBJETIVO].sum())
    filas = []
    for nombre, mask in (("Alto riesgo", b["PD"] >= corte), ("Bajo riesgo", b["PD"] < corte)):
        sub = b[mask]
        inc = int(sub[C.OBJETIVO].sum())
        filas.append({"Categoría": nombre, "Créditos": len(sub),
                      "% de la cartera": len(sub) / total if total else float("nan"),
                      "En incumplimiento": inc,
                      "% de la categoría en incumplimiento": inc / len(sub) if len(sub) else float("nan"),
                      "% del incumplimiento total": inc / total_inc if total_inc else float("nan")})
    return pd.DataFrame(filas)


# --- Luis: métricas y distribuciones agregadas --------------------------------
@st.cache_data(show_spinner=False)
def flujo_monitor(rol: str, escenario: str, reloj_iso: str) -> pd.DataFrame:
    _exigir(rol, "PSI y calibración")
    from datetime import datetime
    return simulacion.flujo(modelo(), escenario, datetime.fromisoformat(reloj_iso))


def distribucion_entrenamiento(rol: str, variable: str):
    _exigir(rol, variable)
    return modelo().entrenamiento[variable].to_numpy()
