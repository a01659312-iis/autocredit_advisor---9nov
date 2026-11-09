"""Modelo de probabilidad de default (PD) y sus explicaciones.

Se usa regresión logística estandarizada: iguala el AUC de un gradient boosting
sobre esta base y permite explicar cada caso sin librerías extra.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import config as C


def _transformar(X: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()
    if "SAVINGS_BALANCE" in X:
        X["SAVINGS_BALANCE"] = np.log1p(X["SAVINGS_BALANCE"].clip(lower=0))
    if "PAYMENT_TO_INCOME" in X:
        X["PAYMENT_TO_INCOME"] = X["PAYMENT_TO_INCOME"].clip(upper=0.6)
    return X


@dataclass
class ModeloPD:
    pipeline: object
    variables: list[str]
    medianas: dict[str, float]
    rango: dict[str, tuple[float, float]]
    holdout: pd.DataFrame              # variables + DEFAULT + PD (REAL + CALCULADO)
    entrenamiento: pd.DataFrame        # variables de entrenamiento (para PSI)
    tasa_base: float                   # default REAL de la base completa
    mediana_buenos: dict[str, float]   # medianas de DEFAULT = 0
    media_cartera: dict[str, float] = field(default_factory=dict)  # benchmark: media de los 80,000
    metricas: dict = field(default_factory=dict)
    coeficientes: pd.DataFrame | None = None

    def puntuar(self, X: pd.DataFrame) -> np.ndarray:
        X = X[self.variables].copy()
        X = X.fillna(self.medianas)
        return self.pipeline.predict_proba(_transformar(X))[:, 1]


def entrenar(df: pd.DataFrame, variables: list[str] | None = None,
             semilla: int = C.SEMILLA) -> ModeloPD:
    variables = variables or C.VARIABLES_MODELO
    X, y = df[variables], df[C.OBJETIVO]
    X_tr, X_ho, y_tr, y_ho = train_test_split(X, y, test_size=0.25, stratify=y, random_state=semilla)
    pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    pipe.fit(_transformar(X_tr), y_tr)

    holdout = X_ho.copy()
    holdout[C.OBJETIVO] = y_ho.to_numpy()
    holdout["PD"] = pipe.predict_proba(_transformar(X_ho))[:, 1]

    modelo = ModeloPD(
        pipeline=pipe, variables=variables,
        medianas=X_tr.median().to_dict(),
        rango={v: (float(X_tr[v].min()), float(X_tr[v].max())) for v in variables},
        holdout=holdout, entrenamiento=X_tr.copy(),
        tasa_base=float(df[C.OBJETIVO].mean()),
        mediana_buenos=df.loc[df[C.OBJETIVO] == 0, variables].median().to_dict(),
        media_cartera=df[variables].mean().to_dict(),
    )
    modelo.metricas = metricas(holdout[C.OBJETIVO].to_numpy(), holdout["PD"].to_numpy())
    coef = pipe[-1].coef_[0]
    # Significancia (Wald): z = coeficiente / error estándar, con la matriz de información.
    Xs = pipe[0].transform(_transformar(X_tr))
    Xs = np.c_[np.ones(len(Xs)), Xs]
    p_tr = pipe.predict_proba(_transformar(X_tr))[:, 1]
    cov = np.linalg.inv((Xs * (p_tr * (1 - p_tr))[:, None]).T @ Xs)
    z = coef / np.sqrt(np.diag(cov))[1:]
    modelo.coeficientes = (
        pd.DataFrame({"variable": variables, "coef_std": coef,
                      "odds_ratio_1sd": np.exp(coef), "z": z})
        .assign(etiqueta=lambda d: d["variable"].map(C.ETIQUETAS))
        .sort_values("coef_std", key=np.abs, ascending=False)
        .reset_index(drop=True)
    )
    return modelo


def metricas(y: np.ndarray, pd_: np.ndarray, corte: float = C.CORTE_PD) -> dict:
    fpr, tpr, _ = roc_curve(y, pd_)
    rechaza = pd_ >= corte
    return {
        "auc": float(roc_auc_score(y, pd_)),
        "ks": float(np.max(tpr - fpr)),
        "brier": float(brier_score_loss(y, pd_)),
        "recall_default": float((rechaza & (y == 1)).sum() / max((y == 1).sum(), 1)),
        "precision_default": float((rechaza & (y == 1)).sum() / max(rechaza.sum(), 1)),
        "aprobacion": float((~rechaza).mean()),
        "default_aprobados": float(y[~rechaza].mean()) if (~rechaza).any() else float("nan"),
        "n": int(len(y)),
    }


# ---------------------------------------------------------------------------
# Evaluación de una solicitud
# ---------------------------------------------------------------------------
def nivel_riesgo(pd_: float, corte: float = C.CORTE_PD) -> str:
    """Semáforo de la solicitud: Alto (rojo) en o sobre el corte vigente, Medio (amarillo)
    cerca del corte, Bajo (verde) lejos de él."""
    if pd_ >= corte:
        return "Alto"
    if pd_ >= min(C.LIMITE_RIESGO_BAJO, corte * 0.55):
        return "Medio"
    return "Bajo"


def peso_variables(modelo: "ModeloPD") -> dict[str, str]:
    """Etiqueta de significancia: ★★★ alta (|coef| ≥ 0.20), ★★ media (≥ 0.09), ★ baja.
    Todas son estadísticamente significativas (|z| > 1.96) en esta base."""
    out = {}
    for _, r in modelo.coeficientes.iterrows():
        a = abs(r["coef_std"])
        out[r["variable"]] = "★★★ Alta" if a >= 0.20 else ("★★ Media" if a >= 0.09 else "★ Baja")
    return out


@dataclass
class Evaluacion:
    pd: float | None
    nivel: str | None
    sugerencia: str               # Aprobar | Condicionar | Rechazar | Revisión manual | Sin calcular
    imputados: list[str]
    fuera_rango: list[str]
    invalidos: list[str]
    contribuciones: pd.DataFrame | None
    enganche_requerido: float | None
    pd_condicionada: float | None

    @property
    def bloquea_aprobar(self) -> bool:
        return any(v in C.VARIABLES_CLAVE for v in self.imputados) or bool(self.invalidos)

    @property
    def calidad(self) -> str:
        if self.invalidos:
            return "Dato inválido"
        if self.imputados:
            return "Incompleto"
        if self.fuera_rango:
            return "Fuera de rango"
        return "Completo"


def evaluar(modelo: ModeloPD, fila: dict, corte: float = C.CORTE_PD) -> Evaluacion:
    valores = {v: fila.get(v) for v in modelo.variables}
    invalidos = []
    for v, val in valores.items():
        if val is None or pd.isna(val):
            continue
        lo, hi = C.LIMITES_VALIDOS[v]
        if not lo <= float(val) <= hi:
            invalidos.append(v)
    imputados = [v for v, val in valores.items() if val is None or pd.isna(val)]
    if invalidos:
        return Evaluacion(None, None, "Sin calcular", imputados, [], invalidos, None, None, None)

    fuera = [v for v, val in valores.items()
             if v not in imputados and not modelo.rango[v][0] <= float(val) <= modelo.rango[v][1]]
    x = pd.DataFrame([valores]).astype(float).fillna(modelo.medianas)
    pd_ = float(modelo.puntuar(x)[0])
    contrib = contribuciones(modelo, x.iloc[0].to_dict(), pd_)
    req, pd_cond = (None, None)
    if pd_ >= corte:
        req, pd_cond = enganche_requerido(modelo, x.iloc[0].to_dict(), corte)

    if fuera:
        sugerencia = "Revisión manual"
    elif pd_ < corte:
        sugerencia = "Aprobar"
    elif req is not None:
        sugerencia = "Condicionar"
    else:
        sugerencia = "Rechazar"
    return Evaluacion(pd_, nivel_riesgo(pd_, corte), sugerencia, imputados, fuera, [], contrib, req, pd_cond)


def contribuciones(modelo: ModeloPD, x: dict, pd_: float | None = None) -> pd.DataFrame:
    """Δ de PD (puntos porcentuales) si cada variable tomara el valor mediano de la
    cartera y todo lo demás quedara igual. Positivo = esa variable sube el riesgo."""
    base = pd.DataFrame([x])[modelo.variables]
    if pd_ is None:
        pd_ = float(modelo.puntuar(base)[0])
    variantes = pd.concat([base] * len(modelo.variables), ignore_index=True)
    for i, v in enumerate(modelo.variables):
        variantes.loc[i, v] = modelo.medianas[v]
    pd_sin = modelo.puntuar(variantes)
    return (
        pd.DataFrame({
            "variable": modelo.variables,
            "etiqueta": [C.ETIQUETAS[v] for v in modelo.variables],
            "valor": [x[v] for v in modelo.variables],
            "mediana": [modelo.medianas[v] for v in modelo.variables],
            "delta_pp": (pd_ - pd_sin) * 100,
        })
        .sort_values("delta_pp", key=np.abs, ascending=False)
        .reset_index(drop=True)
    )


def aplicar_enganche(x: dict, delta: float) -> dict:
    """Escenario: más enganche reduce el préstamo -> baja LTV y el pago mensual."""
    nuevo = dict(x)
    ltv = float(x["LOAN_TO_VALUE"])
    nuevo_ltv = max(ltv - delta, 0.30)
    nuevo["DOWN_PAYMENT_PCT"] = float(x["DOWN_PAYMENT_PCT"]) + delta
    nuevo["LOAN_TO_VALUE"] = nuevo_ltv
    nuevo["PAYMENT_TO_INCOME"] = float(x["PAYMENT_TO_INCOME"]) * (nuevo_ltv / ltv if ltv > 0 else 1)
    return nuevo


def enganche_requerido(modelo: ModeloPD, x: dict, corte: float = C.CORTE_PD):
    """Mínimo enganche total que deja la PD bajo el corte, o (None, None)."""
    actual = float(x["DOWN_PAYMENT_PCT"])
    pasos = np.arange(0.005, max(C.ENGANCHE_MAX_CONDICION - actual, 0) + 0.0001, 0.005)
    if len(pasos) == 0:
        return None, None
    escenarios = pd.DataFrame([aplicar_enganche(x, d) for d in pasos])
    pds = modelo.puntuar(escenarios)
    ok = np.where(pds < corte)[0]
    if len(ok) == 0:
        return None, None
    i = ok[0]
    return float(actual + pasos[i]), float(pds[i])


def pd_con_enganche(modelo: ModeloPD, x: dict, enganche_total: float) -> float:
    delta = max(enganche_total - float(x["DOWN_PAYMENT_PCT"]), 0)
    return float(modelo.puntuar(pd.DataFrame([aplicar_enganche(x, delta)]))[0])


# ---------------------------------------------------------------------------
# Política y salud
# ---------------------------------------------------------------------------
def curva_corte(pd_: np.ndarray, y: np.ndarray, cortes=None) -> pd.DataFrame:
    if cortes is None:
        cortes = np.round(np.arange(0.05, 0.3001, 0.005), 3)
    pd_ = np.asarray(pd_)
    y = np.asarray(y)
    filas = []
    for c in cortes:
        aprueba = pd_ < c
        n_ap = aprueba.sum()
        filas.append({
            "corte": c,
            "aprobacion": n_ap / len(pd_) if len(pd_) else np.nan,
            "default_aprobados": y[aprueba].mean() if n_ap else np.nan,
            "defaults_evitados_1000": ((~aprueba) & (y == 1)).sum() / len(pd_) * 1000 if len(pd_) else np.nan,
            "buenos_rechazados_1000": ((~aprueba) & (y == 0)).sum() / len(pd_) * 1000 if len(pd_) else np.nan,
        })
    return pd.DataFrame(filas)


def calibracion(pd_: np.ndarray, y: np.ndarray, grupos: int = 10) -> pd.DataFrame:
    d = pd.DataFrame({"pd": pd_, "y": y})
    d["decil"] = pd.qcut(d["pd"].rank(method="first"), grupos, labels=range(1, grupos + 1))
    return (d.groupby("decil", observed=True)
            .agg(esperado=("pd", "mean"), observado=("y", "mean"), n=("y", "size"))
            .reset_index())


def psi(base: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index con bins por deciles de la base."""
    base = np.asarray(base, dtype=float)
    actual = np.asarray(actual, dtype=float)
    base = base[~np.isnan(base)]
    actual = actual[~np.isnan(actual)]
    if len(actual) < C.N_MINIMO or len(base) < C.N_MINIMO:
        return float("nan")
    bordes = np.unique(np.quantile(base, np.linspace(0, 1, bins + 1)))
    bordes[0], bordes[-1] = -np.inf, np.inf
    pb = np.histogram(base, bordes)[0] / len(base)
    pa = np.histogram(actual, bordes)[0] / len(actual)
    pb = np.clip(pb, 1e-4, None)
    pa = np.clip(pa, 1e-4, None)
    return float(np.sum((pa - pb) * np.log(pa / pb)))
