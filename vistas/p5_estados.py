"""P5 · Estados y recorridos (las tres personas). Sin datos de clientes.

Responde la retroalimentación del Bloque C: además del error en el login, cada
recorrido muestra sus bifurcaciones de error DENTRO del flujo de análisis, y cada
una está programada en la pantalla correspondiente.
"""
import pandas as pd
import streamlit as st

from src import auth, config as C, ui

usuario = auth.exigir_acceso("P5")
ui.cabecera("P5", usuario)

ESTILO = {
    "ok": 'style="rounded,filled" fillcolor="#e6f4e6" color="#0ca30c"',
    "error": 'style="rounded,filled" fillcolor="#fde8e8" color="#d03b3b"',
    "rec": 'style="rounded,filled" fillcolor="#fff3dc" color="#d99a00"',
    "fin": 'style="rounded,filled" fillcolor="#0ca30c" color="#0ca30c" fontcolor="white"',
    "pant": 'style="rounded,filled" fillcolor="#e3eefc" color="#2a78d6"',
}


def dot(nodos: list[tuple[str, str, str]], aristas: list[tuple], rank: str = "LR") -> str:
    """Recorridos en tres renglones: camino feliz arriba, errores en medio y recuperaciones
    abajo; las flechas de regreso al camino feliz no reacomodan el dibujo (constraint=false)."""
    tipos = {nid: tipo for nid, _, tipo in nodos}
    es_recorrido = any(t == "ok" for t in tipos.values())
    lineas = [f'digraph G {{ rankdir={"TB" if es_recorrido else rank}; bgcolor="transparent"; '
              'nodesep=0.25; ranksep=0.55; newrank=true;',
              'node [shape=box fontname="Helvetica" fontsize=13 margin="0.14,0.08" fontcolor="#0b0b0b"];',
              'edge [color="#898781" fontname="Helvetica" fontsize=11 fontcolor="#898781" arrowsize=0.7];']
    for nid, texto, tipo in nodos:
        lineas.append(f'{nid} [label="{texto}" {ESTILO[tipo]}];')
    if es_recorrido:
        for grupo in (("ok", "fin"), ("error",), ("rec",)):
            ids = [n for n, t in tipos.items() if t in grupo]
            if ids:
                lineas.append("{ rank=same; " + "; ".join(ids) + "; }")
    for a in aristas:
        origen, destino = a[0], a[1]
        attrs = []
        if len(a) > 2 and a[2]:
            attrs.append(f'label="{a[2]}"')
        if len(a) > 3 and a[3] == "punteada":
            attrs.append("style=dashed")
        if es_recorrido and tipos.get(origen) == "rec" and tipos.get(destino) in ("ok", "fin"):
            attrs += ["constraint=false", 'color="#d99a00"', "style=dashed"]
        if es_recorrido and tipos.get(origen) in ("ok", "fin") and tipos.get(destino) in ("ok", "fin"):
            attrs += ['color="#0ca30c"', "penwidth=1.6"]
        lineas.append(f"{origen} -> {destino}" + (f" [{' '.join(attrs)}]" if attrs else "") + ";")
    lineas.append("}")
    return "\n".join(lineas)


st.markdown("Verde = camino feliz · rojo = error **dentro del flujo** · ámbar = recuperación. Cada bifurcación "
            "está programada en su pantalla; la columna «Cómo verlo» del catálogo dice dónde probarla.")

tab_mapa, tab_a, tab_m, tab_l, tab_cat = st.tabs(
    ["Mapa de pantallas", "Recorrido Adrián", "Recorrido Mariana", "Recorrido Luis", "Catálogo de estados"])



def recorrido(pasos: list[tuple[str, str]], errores: list[dict]) -> None:
    """Camino feliz en una fila; debajo de cada paso, los errores que nacen ahí y su recuperación."""
    columnas = st.columns(len(pasos), gap="small")
    for i, (col, (titulo, texto)) in enumerate(zip(columnas, pasos)):
        with col:
            final = i == len(pasos) - 1
            st.success(f"**{titulo}**  \n{texto}", icon=":material/flag:" if final else None)
            for e in (e for e in errores if e["paso"] == i):
                st.error(f"**✗ {e['error']}**  \n:gray[{e['cuando']}]")
                st.warning(f"**↺ {e['rec']}**  \n↩ {e['vuelve']}")


with tab_mapa:
    st.graphviz_chart(dot(
        [("P0", "P0 · Inicio de sesión\\nlas tres personas", "pant"),
         ("SR", "Correo sin rol\\n«Pide acceso a tu gerente»\\nningún dato", "error"),
         ("P1", "P1 · Bandeja\\nAdrián · ¿qué atiendo primero?", "pant"),
         ("P2", "P2 · Ficha\\nAdrián · aprobar / condicionar / rechazar", "pant"),
         ("P3", "P3 · Cartera\\nMariana · endurecer o relajar", "pant"),
         ("P4", "P4 · Monitor\\nLuis · escalar o descartar", "pant"),
         ("P56", "P5 · Estados y recorridos\\nP6 · Gobierno de datos\\ntodos", "pant"),
         ("BIT", "Bitácora de decisiones\\n(SQLite)", "rec")],
        [("P0", "SR", "sin rol"), ("P0", "P1", "analista"), ("P1", "P2", "abre folio"),
         ("P2", "P1", "guarda → siguiente"), ("P0", "P3", "gerente"), ("P0", "P4", "operación"),
         ("P2", "BIT", "decisión + motivo"), ("BIT", "P4", "acuerdo\\nmodelo–analista"),
         ("P0", "P56", "cualquier rol", "punteada")],
        rank="TB",
    ), width="content")
    st.caption("Revisión de huecos: cada persona tiene al menos una pantalla y ninguna pantalla queda sin persona. "
               "La bitácora conecta la decisión de Adrián con lo que vigila Luis.")

with tab_a:
    st.markdown("**Tarea crítica:** resolver una solicitud en menos de 5 minutos y registrar el motivo si "
                "contradice al modelo. Verde = camino feliz; debajo de cada paso, en rojo, el error que puede "
                "ocurrir ahí y, en ámbar, cómo se recupera.")
    recorrido(
        [("1 · Inicia sesión", "P0, cuenta institucional"), ("2 · Bandeja (P1)", "Pendientes, orden por PD"),
         ("3 · Abre la ficha (P2)", "Calidad del dato al abrir"), ("4 · Lee G1, G2, G3", "PD vs corte y por qué"),
         ("5 · Decide y valida", "Revisa vs. media; valida y confirma antes de registrar"),
         ("Decisión registrada", "Abre la siguiente")],
        [
            {"paso": 0, "error": "Correo sin rol", "cuando": "al autenticarse",
             "rec": "«Pide acceso a tu gerente», ningún dato", "vuelve": "fin de sesión"},
            {"paso": 1, "error": "Filtros sin resultados o bandeja vacía", "cuando": "F1 / F2",
             "rec": "Estado vacío con causa + Restablecer", "vuelve": "paso 2"},
            {"paso": 1, "error": "La gerencia cambió el corte de un segmento", "cuando": "Mariana publica en P3",
             "rec": "🔔 Aviso con «corte 15% → 12%» y cada folio «aprobar → condicionar»", "vuelve": "paso 2"},
            {"paso": 2, "error": "Falta un dato clave (PD con valor imputado)", "cuando": "SAVINGS_BALANCE o DTI vacíos",
             "rec": "Aprobar bloqueado; «Pedir documento» → En espera", "vuelve": "paso 4 con la PD recalculada"},
            {"paso": 2, "error": "Dato fuera del rango de entrenamiento", "cuando": "p. ej., LTV 112% (máx. visto 100%)",
             "rec": "Sin recomendación; motivo obligatorio o pedir avalúo", "vuelve": "paso 5"},
            {"paso": 2, "error": "Folio que no es suyo", "cuando": "enlace o sesión ajena",
             "rec": "Bloqueo sin mostrar datos", "vuelve": "paso 2, su bandeja"},
            {"paso": 3, "error": "Sesión expira a mitad de la lectura", "cuando": "30 min sin actividad",
             "rec": "P0 y regreso a la misma solicitud con su borrador", "vuelve": "paso 4"},
            {"paso": 4, "error": "Contradice al modelo sin motivo", "cuando": "al validar",
             "rec": "No se registra; lista lo que falta", "vuelve": "paso 5"},
        ])
    st.caption("Los errores del paso 3 salen de la base: 3 solicitudes SIMULADAS de la bandeja llegan sin "
               "SAVINGS_BALANCE o DTI, o con un LTV mayor al máximo que vio el modelo.")

with tab_m:
    st.markdown("**Tarea crítica:** hallar el segmento que supera la tolerancia de 20% de default y estimar cuánta "
                "aprobación se pierde al endurecer.")
    recorrido(
        [("1 · Inicia sesión", "Su rol abre P3"), ("2 · Ve la cartera", "80,000 créditos · alto vs bajo riesgo"),
         ("3 · Filtra (F3–F6)", "Ve n y % del corte activo"), ("4 · Una dimensión a la vez", "🔴 grupo > 20% (DTI alto)"),
         ("5 · Mueve el corte (C2)", "Aprobación vs incumplimiento"),
         ("Publica el corte", "Confirma; los analistas reciben aviso")],
        [
            {"paso": 2, "error": "Los filtros dejan 0 créditos", "cuando": "corte vacío",
             "rec": "KPI «—» y el filtro culpable + Quitar último filtro", "vuelve": "paso 3, último corte con datos"},
            {"paso": 2, "error": "Quedan menos de 30 créditos", "cuando": "corte chico",
             "rec": "«Muestra insuficiente», sin tasa", "vuelve": "paso 3"},
            {"paso": 3, "error": "Una celda con n < 30", "cuando": "cruce muy fino",
             "rec": "Celda gris «muestra insuficiente»", "vuelve": "paso 4"},
            {"paso": 4, "error": "El segmento tiene < 30 casos en el holdout", "cuando": "curva sin sustento",
             "rec": "G7 vacía y exportación bloqueada", "vuelve": "paso 3, ampliar el segmento"},
        ])
    st.caption("Al combinar filtros el denominador se encoge: solo 469 créditos tienen antecedente de bancarrota y "
               "156 de ellos están en DTI Bajo; un filtro más deja una tasa sin sustento o una pantalla vacía.")

with tab_l:
    st.markdown("**Tarea crítica:** detectar en menos de 1 hora que una métrica salió de su banda y escalar.")
    recorrido(
        [("1 · Monitor abierto", "P4, refresco cada 15 min"), ("2 · Semáforos", "Cada métrica vs su banda"),
         ("3 · Frescura", "Hora de la última carga visible"), ("4 · Alerta arriba", "Ordenada por gravedad"),
         ("5 · Escala o descarta", "Siempre con nota"), ("Alerta cerrada", "Responsable, hora y nota")],
        [
            {"paso": 1, "error": "La ventana aún no tiene cargas", "cuando": "primera hora del día",
             "rec": "Estado vacío + «Ver hoy»", "vuelve": "paso 2"},
            {"paso": 1, "error": "AUC < 0.75 en la revisión mensual", "cuando": "pestaña Salud del modelo",
             "rec": "Semáforo rojo → recalibrar o reentrenar", "vuelve": "paso 2"},
            {"paso": 2, "error": "> 120 min sin carga: todo se vería «normal»", "cuando": "la carga no llegó",
             "rec": "Banner, KPIs en gris, alertas suspendidas; Reintentar / Avisar a TI", "vuelve": "paso 2 al llegar la carga"},
            {"paso": 3, "error": "Falsa alarma (estacional)", "cuando": "fin de mes, quincena",
             "rec": "Descartar con nota visible al siguiente turno", "vuelve": "alerta cerrada"},
            {"paso": 4, "error": "Escalar o descartar sin nota", "cuando": "al confirmar",
             "rec": "No se guarda; pide la nota", "vuelve": "paso 5"},
        ])
    st.caption("Para quien vigila, el peor error es un tablero congelado que se ve normal: por eso los datos viejos se "
               "pintan en gris y nunca se presentan como actuales.")

with tab_cat:
    catalogo = pd.DataFrame([
        ("Sin rol asignado", "P0 · todos", "Correo autenticado sin fila en la tabla de roles",
         "«Pide acceso a tu gerente»; ningún dato", "Cerrar sesión y pedir alta", "Cuenta «Invitado sin rol»"),
        ("Sesión expirada", "Todas", f"{C.SESION_TIMEOUT_MIN} min sin actividad",
         "Aviso en P0", "Al entrar regresa a la misma pantalla y folio con su borrador",
         "Controles de demostración → Simular expiración"),
        ("Dato clave faltante", "P2 · Adrián", "SAVINGS_BALANCE o DTI vacíos (se imputa la mediana)",
         "Aviso ámbar; solo «Rechazar» disponible", "Pedir documento → En espera → llega → PD recalculada",
         "Bandeja de Adrián: filas «Incompleto»"),
        ("Dato fuera de rango", "P2 · Adrián", "Valor fuera del mínimo–máximo de entrenamiento",
         "Sin recomendación del modelo; motivo obligatorio", "Pedir avalúo o decidir con motivo",
         "Bandeja de Adrián: fila «Fuera de rango»"),
        ("Dato imposible", "P2 · Adrián", "Valor fuera de los límites válidos (p. ej., enganche > 100%)",
         "No se calcula PD", "Pedir documento o rechazar con motivo", "Prueba unitaria test_dato_invalido"),
        ("Decisión sin motivo", "P2 · Adrián", "Contradice al modelo y no hay motivo",
         "No se guarda; lista de lo que falta", "Elegir motivo del catálogo", "Aprobar un caso con PD ≥ 15% sin motivo"),
        ("Folio ajeno", "P2 · Adrián", "Folio que no está en su ANALISTA_ID", "Bloqueo sin datos",
         "Volver a su bandeja", "Prueba test_folio_ajeno"),
        ("Bandeja vacía / sin coincidencias", "P1 · Adrián", "Filtros F1/F2 sin resultados",
         "Estado vacío con causa", "Restablecer o ver «En espera»", "F2 sin niveles"),
        ("Corte vacío", "P3 · Mariana", "Combinación de filtros con 0 créditos",
         "KPI «—» (no 0%) y filtro culpable", "Quitar último filtro / Restablecer",
         "DTI Bajo + Enganche < 4% + 3 o más pagos + Con bancarrota"),
        ("Muestra insuficiente", "P3 · Mariana", f"n < {C.N_MINIMO} en el corte, celda o barra",
         "Gris con «muestra insuficiente»", "Quitar último filtro", "Filtro F6 = Con bancarrota + C1 Enganche"),
        ("Curva sin sustento", "P3 · Mariana", f"Menos de {C.N_MINIMO} casos del segmento en el holdout",
         "G7 vacía; no se exporta", "Ampliar el segmento", "Segmentos muy pequeños"),
        ("Datos viejos", "P4 · Luis", f"> {C.FRESCURA_ROJO_MIN} min sin carga",
         "Banner rojo, KPIs grises, alertas suspendidas", "Reintentar / Avisar a TI",
         "Escenario «Carga atrasada»"),
        ("Datos incompletos en la carga", "P4 · Luis", f"> {C.UMBRAL_INCOMPLETOS:.0%} de solicitudes incompletas",
         "Alerta ordenada por gravedad", "Escalar: incidente de datos", "Escenario «Carga con datos incompletos»"),
        ("Drift / aprobación fuera de banda", "P4 · Luis", "PSI > 0.25 o aprobación fuera de 55–75%",
         "Alertas arriba con acción sugerida", "Escalar o descartar con nota", "Escenario «Drift en DTI»"),
        ("Base ausente o inválida", "Todas", "Falta el CSV o columnas esperadas", "Mensaje sin traceback",
         "Colocar el CSV en data/ y Reintentar", "Renombrar el CSV"),
    ], columns=["Estado", "Pantalla · persona", "Disparador", "Qué ve la persona", "Recuperación", "Cómo verlo"])
    st.dataframe(catalogo, hide_index=True, height=560)
    st.caption("Estos estados se diseñaron antes de programar: cada filtro, carga o dato faltante tiene una pantalla "
               "definida en lugar de una gráfica vacía.")
