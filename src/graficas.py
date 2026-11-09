"""Gráficas (Plotly). Cada función responde una pregunta de una persona.

Convenciones (Bloque D): marcas delgadas, rejilla tenue, un solo eje Y, color por
función (gris = referencia, azul = el caso o la serie principal, rojo = fuera de
tolerancia, siempre acompañado de texto), modo claro y oscuro con tokens propios.
"""
from __future__ import annotations

from datetime import datetime, time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src import config as C

FUENTE = '"Source Sans 3", "Source Sans Pro", system-ui, -apple-system, "Segoe UI", sans-serif'
CONFIG = {"displayModeBar": False, "responsive": True}

TOKENS = {
    "light": {
        "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9",
        "axis": "#c3c2b7", "surface": "#ffffff", "track": "#eceae4", "ref": "#b9b7af",
        "serie": "#2a78d6", "serie2": "#eb6834", "sube": "#e34948", "baja": "#2a78d6",
        "critico": "#d03b3b", "bueno": "#0ca30c", "aviso": "#e0a800", "banda": "rgba(12,163,12,0.12)",
        "seq": ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
    },
    "dark": {
        "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781", "grid": "#2c2c2a",
        "axis": "#4a4a46", "surface": "#1a1a19", "track": "#2c2c2a", "ref": "#6d6c66",
        "serie": "#3987e5", "serie2": "#d95926", "sube": "#e66767", "baja": "#3987e5",
        "critico": "#e05252", "bueno": "#0ca30c", "aviso": "#f0b400", "banda": "rgba(12,163,12,0.18)",
        "seq": ["#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#6da7ec", "#b7d3f6"],
    },
}


def tokens() -> dict:
    tipo = "light"
    try:
        tipo = st.context.theme.type or "light"
    except Exception:
        pass
    return TOKENS.get(tipo, TOKENS["light"])


def _base(fig: go.Figure, t: dict, alto: int, leyenda: bool = False) -> go.Figure:
    fig.update_layout(
        height=alto, margin=dict(l=4, r=12, t=28 if leyenda else 8, b=4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FUENTE, size=13, color=t["ink2"]),
        showlegend=leyenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(color=t["ink2"])),
        hoverlabel=dict(bgcolor=t["surface"], bordercolor=t["axis"], font=dict(color=t["ink"], family=FUENTE)),
        bargap=0.35,
    )
    fig.update_xaxes(gridcolor=t["grid"], linecolor=t["axis"], zeroline=False, tickfont=dict(color=t["muted"]),
                     automargin=True)
    fig.update_yaxes(gridcolor=t["grid"], linecolor=t["axis"], zeroline=False, tickfont=dict(color=t["ink2"]),
                     automargin=True)
    return fig


def mostrar(fig: go.Figure, key: str | None = None) -> None:
    st.plotly_chart(fig, config=CONFIG, theme=None, key=key)


# ---------------------------------------------------------------------------
# P2 · Ficha (Adrián)
# ---------------------------------------------------------------------------
def g1_barra_corte(pd_: float, corte: float, promedio: float) -> go.Figure:
    """G1: un valor contra dos referencias (corte y promedio de cartera)."""
    t = tokens()
    tope = max(C.ESCALA_PD_MAX, pd_ + 0.02)
    fig = go.Figure()
    fig.add_bar(x=[tope], y=[""], orientation="h", marker=dict(color=t["track"]), hoverinfo="skip", width=0.5)
    fig.add_bar(x=[pd_], y=[""], orientation="h", width=0.5,
                marker=dict(color=t["ink2"], cornerradius=4),
                hovertemplate=f"PD de la solicitud: {pd_:.1%}<extra></extra>")
    # Corte y promedio están a 1.5 pp: cada etiqueta va en su propio renglón para que nunca se encimen
    # ni se corten en el borde, sin importar la escala.
    for x, nombre, color, ancho, renglon in [
        (corte, f"Corte vigente {corte:.1%}*", t["ink"], 3, 1),
        (promedio, f"Media de la cartera {promedio:.1%}", t["muted"], 2, 0),
    ]:
        fig.add_shape(type="line", x0=x, x1=x, y0=-0.45, y1=0.45, line=dict(color=color, width=ancho))
        fig.add_annotation(x=x, y=1.0, yref="paper", text=f"▾ {nombre}", showarrow=False, yanchor="bottom",
                           yshift=renglon * 17, font=dict(size=12, color=color), xanchor="left", xshift=-4)
    fig.update_layout(barmode="overlay")
    _base(fig, t, 140)
    fig.update_layout(margin=dict(l=4, r=12, t=46, b=8))
    fig.update_xaxes(range=[0, tope], tickformat=".0%", showgrid=False, dtick=0.1 if tope > 0.45 else 0.05,
                     tickangle=0)
    fig.update_yaxes(showticklabels=False, showgrid=False)
    return fig


def g2_contribuciones(contrib: pd.DataFrame, formatear) -> go.Figure:
    """G2: barras divergentes, qué sube o baja el riesgo de ESTE caso."""
    t = tokens()
    d = contrib.iloc[::-1].copy()
    d["texto"] = [f"{e} = {formatear(v, val)}" for e, v, val in zip(d["etiqueta"], d["variable"], d["valor"])]
    colores = [t["sube"] if x > 0 else t["baja"] for x in d["delta_pp"]]
    top = set(contrib["variable"].head(4))
    etiquetas = [f"{x:+.1f} pp" if v in top else "" for x, v in zip(d["delta_pp"], d["variable"])]
    fig = go.Figure(go.Bar(
        x=d["delta_pp"], y=d["texto"], orientation="h", marker=dict(color=colores, cornerradius=3),
        text=etiquetas, textposition="outside", textfont=dict(color=t["ink2"], size=12), cliponaxis=False,
        customdata=np.stack([d["mediana"].map(lambda m: m)], axis=-1),
        hovertemplate="%{y}<br>Δ PD frente a un valor típico: %{x:+.2f} pp<extra></extra>",
    ))
    lim = max(abs(d["delta_pp"]).max() * 1.35, 1)
    fig.add_vline(x=0, line=dict(color=t["ink"], width=1.5))
    _base(fig, t, 340)
    fig.update_xaxes(range=[-lim, lim], title=dict(text="← baja el riesgo · Δ PD (pp) · sube el riesgo →",
                                                    font=dict(size=12, color=t["muted"])))
    fig.update_yaxes(showgrid=False)
    return fig


def g3_pareadas(variables: list[str], cliente: list[float], media: list[float],
                buenos: list[float]) -> go.Figure:
    """G3: el solicitante contra la media de la cartera (benchmark) y contra el buen pagador."""
    t = tokens()
    etiquetas = [C.ETIQUETAS[v] for v in variables][::-1]
    fig = go.Figure()
    fig.add_bar(y=etiquetas, x=buenos[::-1], orientation="h", name="Buen pagador (mediana, incumplimiento = 0)*",
                marker=dict(color=t["track"], cornerradius=3),
                hovertemplate="%{y}: %{x:.1%}<extra>Buen pagador</extra>")
    fig.add_bar(y=etiquetas, x=media[::-1], orientation="h", name="Media de la cartera",
                marker=dict(color=t["ref"], cornerradius=3),
                hovertemplate="%{y}: %{x:.1%}<extra>Media de la cartera</extra>")
    fig.add_bar(y=etiquetas, x=cliente[::-1], orientation="h", name="Esta solicitud",
                marker=dict(color=t["serie"], cornerradius=3),
                hovertemplate="%{y}: %{x:.1%}<extra>Solicitud</extra>")
    _base(fig, t, 330, leyenda=True)
    fig.update_layout(barmode="group", bargap=0.28, bargroupgap=0.06, legend=dict(traceorder="reversed"))
    fig.update_xaxes(tickformat=".0%", rangemode="tozero")
    fig.update_yaxes(showgrid=False)
    return fig


# ---------------------------------------------------------------------------
# P3 · Cartera (Mariana)
# ---------------------------------------------------------------------------
def g5_mapa_calor(tabla: pd.DataFrame, filas: list[str], columnas: list[str], fila_col: str,
                  col_col: str, tolerancia: float) -> go.Figure:
    """G5: tasa de default por celda; borde rojo = supera tolerancia; gris = n < 30."""
    t = tokens()
    z = np.full((len(filas), len(columnas)), np.nan)
    textos = [["" for _ in columnas] for _ in filas]
    fig = go.Figure()
    formas, anotaciones = [], []
    zmax = 0.45
    for i, f in enumerate(filas):
        for j, c in enumerate(columnas):
            celda = tabla[(tabla[fila_col] == f) & (tabla[col_col] == c)]
            n = int(celda["n"].iloc[0]) if len(celda) else 0
            if n >= C.N_MINIMO:
                tasa = float(celda["tasa"].iloc[0])
                z[i, j] = tasa
                # La escala es la misma en ambos modos: el texto se elige por el tono de la celda.
                color_txt = "#ffffff" if tasa / zmax > 0.42 else "#0b0b0b"
                anotaciones.append(dict(x=j, y=i, text=f"<b>{tasa:.1%}</b><br>n = {n:,}", showarrow=False,
                                        font=dict(color=color_txt, size=13)))
                if tasa > tolerancia:
                    formas.append(dict(type="rect", x0=j - 0.47, x1=j + 0.47, y0=i - 0.45, y1=i + 0.45,
                                       line=dict(color=t["critico"], width=3)))
                textos[i][j] = f"{f} · {c}<br>Incumplimiento: {tasa:.1%}<br>n = {n:,}" + (
                    "<br><b>Supera la tolerancia</b>" if tasa > tolerancia else "")
            else:
                formas.append(dict(type="rect", x0=j - 0.5, x1=j + 0.5, y0=i - 0.5, y1=i + 0.5,
                                   fillcolor=t["track"], line=dict(color=t["surface"], width=2), layer="below"))
                msg = "sin créditos" if n == 0 else f"muestra<br>insuficiente<br>(n = {n})"
                anotaciones.append(dict(x=j, y=i, text=msg, showarrow=False, font=dict(color=t["muted"], size=12)))
                textos[i][j] = f"{f} · {c}<br>n = {n}: sin tasa (regla n ≥ {C.N_MINIMO})"
    escala = [[k / (len(t["seq"]) - 1), col] for k, col in enumerate(TOKENS["light"]["seq"])]
    fig.add_heatmap(z=z, x=columnas, y=filas, colorscale=escala, zmin=0, zmax=zmax, xgap=3, ygap=3,
                    text=textos, hovertemplate="%{text}<extra></extra>", showscale=True,
                    colorbar=dict(title=dict(text="Incumplimiento", side="right"), tickformat=".0%", thickness=10,
                                  outlinewidth=0, tickfont=dict(color=t["muted"])))
    _base(fig, t, 110 + 92 * len(filas))
    fig.update_layout(shapes=formas, annotations=anotaciones)
    fig.update_xaxes(side="top", showgrid=False, tickfont=dict(color=t["ink2"], size=13))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=13))
    return fig


def g6_barras_grupo(tabla: pd.DataFrame, col: str, orden: list[str], tolerancia: float,
                    referencia: float | None = None) -> go.Figure:
    """G6: incumplimiento por grupo con semáforo (verde ≤ 15%, amarillo 15–20%, rojo > 20%),
    flecha ▲/▼ frente a la cartera y gris si n < 30. El texto siempre acompaña al color."""
    t = tokens()
    d = tabla.set_index(col).reindex(orden).reset_index()
    d["n"] = d["n"].fillna(0).astype(int)
    colores, valores, textos = [], [], []
    for _, r in d.iterrows():
        if r["n"] < C.N_MINIMO:
            colores.append(t["track"])
            valores.append(0.004)
            textos.append(f"muestra insuficiente (n = {r['n']})")
            continue
        tasa = r["tasa"]
        if tasa > tolerancia:
            colores.append(t["critico"]); estado = "🔴 fuera"
        elif tasa > C.AMARILLO_SEGMENTO:
            colores.append(t["aviso"]); estado = "🟡 advertencia"
        else:
            colores.append(t["bueno"]); estado = "🟢"
        valores.append(tasa)
        tendencia = ""
        if referencia is not None:
            dif = (tasa - referencia) * 100
            tendencia = f"  {'▲' if dif > 0.05 else '▼' if dif < -0.05 else '＝'} {dif:+.1f} pp"
        textos.append(f"{tasa:.1%}{tendencia}  {estado}")
    ylab = [f"{g}  (n = {n:,})" for g, n in zip(d[col], d["n"])]
    fig = go.Figure(go.Bar(x=valores, y=ylab, orientation="h", marker=dict(color=colores, cornerradius=4),
                           text=textos, textposition="outside", cliponaxis=False,
                           textfont=dict(color=t["ink2"], size=12),
                           hovertemplate="%{y}<br>%{text}<extra></extra>"))
    fig.add_vline(x=tolerancia, line=dict(color=t["critico"], width=1.5, dash="dot"))
    fig.add_annotation(x=tolerancia, y=1.0, yref="paper", yanchor="bottom", text=f"tolerancia {tolerancia:.0%}",
                       showarrow=False, font=dict(size=12, color=t["critico"]))
    if referencia is not None:
        fig.add_vline(x=referencia, line=dict(color=t["muted"], width=1.5))
        fig.add_annotation(x=referencia, y=1.0, yref="paper", yanchor="bottom", xanchor="right",
                           text=f"cartera {referencia:.1%}", showarrow=False, font=dict(size=12, color=t["muted"]))
    _base(fig, t, 64 + 46 * len(orden))
    fig.update_layout(margin=dict(l=4, r=12, t=24, b=4))
    tope = d["tasa"].max() if d["tasa"].notna().any() else 0
    fig.update_xaxes(tickformat=".0%", range=[0, max(0.5, tope * 1.9)])
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


def g7_tradeoff(curva: pd.DataFrame, corte_actual: float, corte_prop: float) -> go.Figure:
    """G7: dos medidas en dos paneles con el mismo eje X (nunca doble eje Y)."""
    t = tokens()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=("Tasa de aprobación", "Incumplimiento esperado entre aprobados"))
    fig.add_scatter(x=curva["corte"], y=curva["aprobacion"], mode="lines", line=dict(color=t["serie"], width=2),
                    hovertemplate="Corte %{x:.1%}: aprobación %{y:.1%}<extra></extra>", row=1, col=1)
    fig.add_scatter(x=curva["corte"], y=curva["default_aprobados"], mode="lines",
                    line=dict(color=t["serie2"], width=2),
                    hovertemplate="Corte %{x:.1%}: incumplimiento en aprobados %{y:.1%}<extra></extra>", row=2, col=1)
    for x, nombre, color, dash in [(corte_actual, "actual", t["muted"], "dot"), (corte_prop, "propuesto", t["ink"], "solid")]:
        fig.add_vline(x=x, line=dict(color=color, width=1.5, dash=dash))
    fig.add_annotation(x=corte_prop, y=1.08, yref="paper", text=f"propuesto {corte_prop:.1%}", showarrow=False,
                       font=dict(size=12, color=t["ink"]), xanchor="left")
    if abs(corte_prop - corte_actual) > 0.004:
        fig.add_annotation(x=corte_actual, y=1.08, yref="paper", text=f"actual {corte_actual:.0%}", showarrow=False,
                           font=dict(size=12, color=t["muted"]), xanchor="right")
    _base(fig, t, 360)
    fig.update_layout(margin=dict(l=4, r=12, t=40, b=4))
    for anot in fig.layout.annotations:
        if anot.text in ("Tasa de aprobación", "Incumplimiento esperado entre aprobados"):
            anot.font = dict(size=12, color=t["ink2"])
            anot.x = 0
            anot.xanchor = "left"
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(tickformat=".0%", row=2, col=1, title=dict(text="Corte de PD", font=dict(size=12, color=t["muted"])))
    return fig


# ---------------------------------------------------------------------------
# P4 · Monitor (Luis)
# ---------------------------------------------------------------------------
def g8_linea_banda(serie: pd.DataFrame, banda: tuple[float, float], dia, gris: bool = False) -> go.Figure:
    """G8: aprobación móvil de la última hora contra su banda esperada."""
    t = tokens()
    fig = go.Figure()
    x0, x1 = datetime.combine(dia, time(8, 0)), datetime.combine(dia, time(18, 0))
    fig.add_shape(type="rect", x0=x0, x1=x1, y0=banda[0], y1=banda[1], fillcolor=t["banda"], line_width=0, layer="below")
    fig.add_annotation(x=x0, y=banda[1], text=f"banda {banda[0]:.0%}–{banda[1]:.0%}", showarrow=False,
                       xanchor="left", yanchor="bottom", font=dict(size=11, color=t["muted"]))
    if not serie.empty:
        color = t["muted"] if gris else t["serie"]
        fig.add_scatter(x=serie["ts"], y=serie["aprobacion"], mode="lines", line=dict(color=color, width=2),
                        hovertemplate="%{x|%H:%M}: %{y:.1%}<extra>Aprobación (última hora)</extra>")
        fuera = serie[(serie["aprobacion"] < banda[0]) | (serie["aprobacion"] > banda[1])]
        if not fuera.empty and not gris:
            fig.add_scatter(x=fuera["ts"], y=fuera["aprobacion"], mode="markers",
                            marker=dict(color=t["critico"], size=8, line=dict(color=t["surface"], width=2)),
                            hovertemplate="%{x|%H:%M}: %{y:.1%} fuera de banda<extra></extra>")
            primera = fuera["ts"].iloc[0]
            fig.add_vline(x=primera, line=dict(color=t["critico"], width=1, dash="dot"))
            fig.add_annotation(x=0, xref="paper", y=1.0, yref="paper", yanchor="bottom", xanchor="left",
                               text=f"▲ fuera de banda desde {primera:%H:%M}", showarrow=False,
                               font=dict(size=12, color=t["critico"]))
    _base(fig, t, 280)
    fig.update_layout(margin=dict(l=4, r=12, t=26, b=4))
    fig.update_xaxes(range=[x0, x1], tickformat="%H:%M", dtick=2 * 3600 * 1000)
    lo = min(0.4, (serie["aprobacion"].min() - 0.05) if not serie.empty else 0.4)
    hi = max(0.95, (serie["aprobacion"].max() + 0.05) if not serie.empty else 0.95)
    fig.update_yaxes(tickformat=".0%", range=[lo, hi])
    return fig


def g9_histogramas(base: np.ndarray, actual: np.ndarray, variable: str, psi_valor: float, gris: bool = False) -> go.Figure:
    """G9: distribución de entrenamiento vs. ventana actual, mismos bins."""
    t = tokens()
    tope = float(np.nanquantile(base, 0.995))
    bordes = np.linspace(0, tope, 11)
    bordes[-1] = np.inf
    pb = np.histogram(base[~np.isnan(base)], bordes)[0]
    pa = np.histogram(actual[~np.isnan(actual)], bordes)[0]
    pb = pb / max(pb.sum(), 1)
    pa = pa / max(pa.sum(), 1)
    paso = tope / 10
    centros = [bordes[i] + paso / 2 for i in range(10)]
    rangos = [f"{bordes[i]:.0%}–{bordes[i + 1]:.0%}" if np.isfinite(bordes[i + 1]) else f"≥ {bordes[i]:.0%}"
              for i in range(10)]
    fig = go.Figure()
    fig.add_bar(x=centros, y=pb, name="Entrenamiento (base real)", marker=dict(color=t["ref"], cornerradius=3),
                customdata=rangos, hovertemplate="%{customdata}: %{y:.1%}<extra>Entrenamiento</extra>")
    fig.add_bar(x=centros, y=pa, name="Ventana actual**",
                marker=dict(color=t["muted"] if gris else t["serie"], cornerradius=3),
                customdata=rangos, hovertemplate="%{customdata}: %{y:.1%}<extra>Ventana actual</extra>")
    _base(fig, t, 280, leyenda=True)
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.06)
    fig.update_yaxes(tickformat=".0%", title=dict(text="% de solicitudes", font=dict(size=12, color=t["muted"])))
    fig.update_xaxes(title=dict(text=C.ETIQUETAS[variable] + " (último bin abierto)", font=dict(size=12, color=t["muted"])),
                     tickformat=".0%", tickangle=0, nticks=6)
    return fig


CATEGORIAS_ACUERDO = ["Coincide con el modelo", "Aprueba lo que el modelo rechaza", "Rechaza lo que el modelo aprueba"]


def g10_apiladas(tabla: pd.DataFrame) -> go.Figure:
    """G10: parte-todo por día alineado en la misma escala (100%)."""
    t = tokens()
    colores = {CATEGORIAS_ACUERDO[0]: t["ref"], CATEGORIAS_ACUERDO[1]: t["sube"], CATEGORIAS_ACUERDO[2]: t["baja"]}
    fig = go.Figure()
    for cat in CATEGORIAS_ACUERDO:
        fig.add_bar(y=tabla["dia_txt"], x=tabla[cat], orientation="h", name=cat,
                    marker=dict(color=colores[cat], line=dict(color=t["surface"], width=2)),
                    hovertemplate="%{y}: %{x:.1%}<extra>" + cat + "</extra>")
    _base(fig, t, 90 + 36 * len(tabla), leyenda=True)
    fig.update_layout(barmode="stack", bargap=0.3, legend=dict(font=dict(size=12)))
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


def calibracion(tabla: pd.DataFrame) -> go.Figure:
    t = tokens()
    fig = go.Figure()
    fig.add_bar(x=tabla["decil"].astype(str), y=tabla["esperado"], name="Esperado (PD media)*",
                marker=dict(color=t["ref"], cornerradius=3), hovertemplate="Decil %{x}: %{y:.1%}<extra>Esperado</extra>")
    fig.add_bar(x=tabla["decil"].astype(str), y=tabla["observado"], name="Observado (incumplimiento real)",
                marker=dict(color=t["serie"], cornerradius=3), hovertemplate="Decil %{x}: %{y:.1%}<extra>Observado</extra>")
    _base(fig, t, 280, leyenda=True)
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.06)
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(title=dict(text="Decil de PD (1 = menor riesgo)", font=dict(size=12, color=t["muted"])))
    return fig
