import numpy as np
import pandas as pd

from src import config as C, datos
from src.modelo import curva_corte, enganche_requerido, evaluar, psi


def test_desempeno_minimo(modelo):
    assert modelo.metricas["auc"] >= C.AUC_MINIMO
    assert abs(modelo.holdout["PD"].mean() - modelo.tasa_base) < 0.01  # calibrado en promedio


def test_tasa_base_real(base):
    assert len(base) == 80_000
    assert round(base[C.OBJETIVO].mean(), 4) == 0.1348


def test_dato_faltante_bloquea_aprobar(modelo):
    fila = modelo.holdout.iloc[0][C.VARIABLES_MODELO].to_dict()
    fila["SAVINGS_BALANCE"] = np.nan
    ev = evaluar(modelo, fila)
    assert ev.pd is not None and "SAVINGS_BALANCE" in ev.imputados
    assert ev.bloquea_aprobar and ev.calidad == "Incompleto"


def test_fuera_de_rango_sin_recomendacion(modelo):
    fila = modelo.holdout.iloc[0][C.VARIABLES_MODELO].to_dict()
    fila["LOAN_TO_VALUE"] = 1.12
    ev = evaluar(modelo, fila)
    assert ev.sugerencia == "Revisión manual" and ev.calidad == "Fuera de rango"


def test_dato_invalido(modelo):
    fila = modelo.holdout.iloc[0][C.VARIABLES_MODELO].to_dict()
    fila["DOWN_PAYMENT_PCT"] = 1.5
    ev = evaluar(modelo, fila)
    assert ev.pd is None and ev.calidad == "Dato inválido"


def test_enganche_requerido_baja_del_corte(modelo):
    hold = modelo.holdout
    caso = hold[(hold["PD"] > 0.16) & (hold["PD"] < 0.20)].iloc[0][C.VARIABLES_MODELO].to_dict()
    req, pd_cond = enganche_requerido(modelo, caso)
    assert req is not None and req > caso["DOWN_PAYMENT_PCT"] and pd_cond < C.CORTE_PD


def test_contribuciones_explican_el_caso(modelo):
    fila = modelo.holdout.iloc[3][C.VARIABLES_MODELO].to_dict()
    ev = evaluar(modelo, fila)
    assert len(ev.contribuciones) == len(C.VARIABLES_MODELO)
    assert ev.contribuciones["delta_pp"].abs().is_monotonic_decreasing


def test_psi(modelo):
    base = modelo.entrenamiento["DEBT_TO_INCOME"].to_numpy()
    assert psi(base, base) < 0.01
    assert psi(base, base + 0.12) > C.UMBRAL_PSI_ALERTA


def test_curva_monotona(modelo):
    c = curva_corte(modelo.holdout["PD"], modelo.holdout[C.OBJETIVO])
    assert c["aprobacion"].is_monotonic_increasing
    fila = c.iloc[(c["corte"] - C.CORTE_PD).abs().argmin()]
    assert C.BANDA_APROBACION[0] <= fila["aprobacion"] <= C.BANDA_APROBACION[1]


def test_regla_de_muestra_minima(base):
    seg = datos.segmentar(base)
    vacio = datos.aplicar_filtros(seg, {"F3": "Bajo", "F4": "< 4%", "F5": "3 o más", "F6": "Con bancarrota"})
    assert len(vacio) == 0
    tabla = datos.tasa_por_grupo(datos.aplicar_filtros(seg, {"F6": "Con bancarrota"}), "SEG_DTI", "SEG_ENGANCHE")
    chicas = tabla[tabla["n"] < C.N_MINIMO]
    assert len(chicas) and chicas["tasa"].isna().all()
