"""P6 · Gobierno de datos (las tres personas). Solo metadatos, ningún registro.

Responde la retroalimentación de los Bloques E y F: la matriz persona × dato aparece
completa como tabla, y cada filtro y control muestra la decisión que cambia. Las
mismas tablas son las que el código consulta para decidir qué entrega a cada rol.
"""
import pandas as pd
import streamlit as st

from src import auth, config as C, ui
from src.seguridad import (AGREGADO, AUDITORIA, ENMASCARADO, INDIVIDUAL, OCULTO, VISIBLE, matriz_pantallas,
                           tabla_matriz_datos)

usuario = auth.exigir_acceso("P6")
ui.cabecera("P6", usuario)

tab_dato, tab_pant, tab_filtros, tab_origen, tab_auth = st.tabs(
    ["Persona × dato", "Persona × pantalla", "Filtros y controles", "Notación y datos propuestos",
     "Autenticación y exposición"])

with tab_dato:
    st.markdown("**Matriz completa persona × dato.** Incluye las 12 columnas de la base, los datos calculados, las "
                "columnas operativas propuestas y las columnas protegidas del dataset completo que no vienen en "
                "esta base. Lo que no aparece aquí se niega por defecto.")
    matriz = tabla_matriz_datos()
    grupos = ["Todos"] + list(matriz["Grupo"].unique())
    grupo = st.segmented_control("Grupo", grupos, default="Todos", required=True, key="p6_grupo",
                                 help="Solo cambia qué filas se leen; no es un filtro de datos de clientes.")
    vista = matriz if grupo == "Todos" else matriz[matriz["Grupo"] == grupo]
    personas = ["Adrián (analista)", "Mariana (gerente)", "Luis (operación)"]

    def _color(valor: str) -> str:
        return {
            INDIVIDUAL: "background-color: rgba(42,120,214,0.16)",
            AGREGADO: "background-color: rgba(12,163,12,0.14)",
            AUDITORIA: "background-color: rgba(98,80,214,0.14)",
            ENMASCARADO: "background-color: rgba(250,178,25,0.22)",
            OCULTO: "background-color: rgba(208,59,59,0.14)",
            VISIBLE: "",
        }.get(valor, "")

    orden = ["Dato"] + personas + ["Tratamiento", "Origen", "Sensibilidad", "Nota"]
    vista = vista[orden].assign(
        Origen=lambda d: d["Origen"].map(lambda o: ui.NOMBRE_ORIGEN.get(o, o)),
        Tratamiento=lambda d: d["Tratamiento"].str.capitalize()).set_index("Dato")
    # st.table muestra la matriz completa, sin scroll ni columnas ocultas.
    st.table(vista.style.map(_color, subset=personas))
    conteo = matriz[personas].apply(pd.Series.value_counts).fillna(0).astype(int)
    conteo.columns = ["Adrián", "Mariana", "Luis"]
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.markdown(
            f"- **{INDIVIDUAL}**: el valor de una solicitud concreta (solo las asignadas a su ANALISTA_ID).\n"
            f"- **{AGREGADO}**: tasas, medianas o distribuciones con al menos {C.N_MINIMO} registros.\n"
            f"- **{AUDITORIA}**: solo agregados de {C.N_MINIMO_AUDITORIA}+ registros para auditar sesgo.\n"
            f"- **{ENMASCARADO}**: se ven los últimos 4 dígitos (****0947).\n"
            f"- **{OCULTO}**: la columna no sale de la base hacia el tablero.\n"
            f"- **{VISIBLE}**: metadato del sistema, no es dato personal.\n\n"
            "**Tratamiento:** ocultar (no sale de la base) · agregar (solo tasas o distribuciones con n mínimo) · "
            "enmascarar (últimos 4 dígitos) · restringir (solo quien decide el caso) · autorizar (filtro por "
            "ANALISTA_ID en el servidor).")
    with c2:
        st.markdown("**Cuántos datos ve cada persona por nivel**")
        st.dataframe(conteo, height=260)
    st.caption("Cómo se aplica en código: `seguridad.aplicar_politica_fila()` recorta la fila que recibe la ficha de "
               "Adrián; `servicios.*` verifica `puede_agregado()` antes de entregar cualquier tasa a Mariana o Luis; "
               "la bitácora que ve Luis pasa por `enmascarar()`. Las pruebas en tests/test_seguridad.py lo verifican.")

with tab_pant:
    st.markdown("**Matriz persona × pantalla.** La navegación solo muestra lo permitido y cada pantalla vuelve a "
                "verificar el rol antes de cargar datos.")
    st.dataframe(matriz_pantallas(), hide_index=True)
    st.markdown("**Menor privilegio: lo que cada persona NO ve**")
    a, m, l = st.columns(3)
    with a, st.container(border=True):
        st.markdown("**Adrián · analista**\n\nVe solo las solicitudes de su ANALISTA_ID con su expediente.\n\n"
                    "No ve: cartera, monitor, casos de otros analistas, incumplimiento histórico, "
                    "FINANCIAL_LITERACY_SCORE ni variables protegidas.")
    with m, st.container(border=True):
        st.markdown(f"**Mariana · gerente**\n\nVe tasas, conteos y curvas por segmento (n ≥ {C.N_MINIMO}).\n\n"
                    "No ve: ningún cliente individual, ningún folio, contribuciones de un caso ni variables "
                    "protegidas. Su exportación solo trae agregados.")
    with l, st.container(border=True):
        st.markdown(f"**Luis · operación**\n\nVe métricas del sistema y distribuciones agregadas; auditoría de sesgo "
                    f"solo con n ≥ {C.N_MINIMO_AUDITORIA}.\n\nNo ve: expedientes ni decisiones identificables "
                    "(folio enmascarado, sin analista y sin texto libre).")

with tab_filtros:
    st.markdown("**Cada filtro y cada control está amarrado a una persona y a la decisión que cambia.** "
                "La prueba tests/test_registros.py falla si alguno queda sin persona o sin decisión.")
    filtros = pd.DataFrame([{"ID": fid, "Filtro": f["nombre"], "Pantalla": f["pantalla"], "Persona": f["persona"],
                             "Decisión que cambia": f["decision"],
                             "Por defecto": ", ".join(f["defecto"]) if isinstance(f["defecto"], list) else f["defecto"],
                             "Origen": f["origen"]} for fid, f in C.FILTROS.items()])
    st.dataframe(filtros, hide_index=True, column_config={"Decisión que cambia": st.column_config.TextColumn(width="large")})
    st.markdown("**Controles de vista** (no filtran registros, pero cambian lo que la persona compara)")
    controles = pd.DataFrame([{"ID": cid, "Control": c["nombre"], "Pantalla": c["pantalla"], "Persona": c["persona"],
                               "Decisión que cambia": c["decision"], "Por defecto": str(c["defecto"]),
                               "Origen": c["origen"]} for cid, c in C.CONTROLES.items()])
    st.dataframe(controles, hide_index=True, column_config={"Decisión que cambia": st.column_config.TextColumn(width="large")})
    st.markdown("**Filtros descartados y por qué**")
    st.dataframe(pd.DataFrame(C.FILTROS_DESCARTADOS, columns=["Campo", "Razón"]), hide_index=True)
    st.markdown(f"**Corte activo visible:** siempre arriba de las gráficas, en una línea, con n real y botón "
                f"Restablecer. **Selección vacía:** KPI en «—» (no 0%) y botón «Quitar último filtro». "
                f"**Muestra chica:** n < {C.N_MINIMO} se pinta gris con «muestra insuficiente».")

with tab_origen:
    c1, c2 = st.columns([1, 1.6])
    with c1:
        st.markdown("**Notación en títulos, métricas y columnas**")
        for marca_, titulo, texto in (
            ("sin marca", "Dato real", "Columna tal cual de Base_SAS_Equipo3.csv (80,000 créditos)."),
            ("\\*", "Dato propio", "Lo calcula el equipo con la base: PD del modelo, segmentos, categorías de "
                                 "riesgo, cortes y bandas de política."),
            ("\\*\\*", "Dato simulado", "La base aún no lo trae (folio, fecha, estado, decisión); se genera a "
                                         "partir de filas reales para demostrar la pantalla."),
        ):
            with st.container(border=True):
                st.markdown(f"**{marca_} · {titulo}**")
                st.caption(texto)
        st.caption("Regla: si un elemento mezcla orígenes, lleva la marca más fuerte. Cada pantalla termina con un "
                   "pie que explica las marcas que usa. Se evita el texto en mayúsculas para no competir con los "
                   "nombres de variables y secciones.")
    with c2:
        st.markdown("**Datos que proponemos agregar** (hoy son simulados\\*\\*)")
        st.dataframe(pd.DataFrame([
            ("FOLIO / LOAN_ID", "Identificador", "Bandeja, ficha, bitácora", "Adrián"),
            ("ANALISTA_ID", "Identificador", "P1 muestra solo lo asignado", "Adrián"),
            ("FECHA_SOLICITUD", "Fecha-hora", "G8 y ventana de tiempo F7", "Luis"),
            ("ESTADO_SOLICITUD", "Categoría (3)", "Filtro F1 · «En espera»", "Adrián"),
            ("DECISION_ANALISTA", "Categoría (3)", "G8, G10 · acuerdo modelo–analista (ya se registra en la bitácora)", "Luis"),
            ("MOTIVO_OVERRIDE", "Catálogo + texto", "Auditoría de overrides", "Luis · Mariana"),
            ("FECHA_CARGA", "Fecha-hora", "Frescura de datos (P4)", "Luis"),
        ], columns=["Dato", "Tipo", "Qué habilita", "Persona"]), hide_index=True)
        st.markdown("**Base real usada:** `Base_SAS_Equipo3.csv` · 80,000 créditos × 12 columnas · 10,783 en "
                    "incumplimiento (13.48%) · sin nulos. El PDF del prototipo describía 100,000 × 83; esta versión "
                    "usa solo lo que trae la base y marca como simulado\\*\\* lo demás.")
        st.markdown(f"**Modelo:** regresión logística estandarizada ({C.VERSION_MODELO}), 75% entrenamiento / 25% "
                    f"holdout estratificado, {len(C.VARIABLES_MODELO)} variables. Excluida: FINANCIAL_LITERACY_SCORE.")

with tab_auth:
    a, b = st.columns(2)
    with a, st.container(border=True):
        st.markdown("**Autenticación · ¿quién eres?**")
        st.markdown("- `st.login` con OIDC (Google o Microsoft) usando la cuenta institucional.\n"
                    "- Sin sesión válida no se carga ningún dato.\n"
                    f"- La sesión se cierra tras {C.SESION_TIMEOUT_MIN} min sin actividad y regresa a la persona a "
                    "su solicitud con el borrador guardado.\n"
                    "- Sin `[auth]` en secrets, la app arranca en modo demostración con cuentas de prueba.")
    with b, st.container(border=True):
        st.markdown("**Autorización · ¿qué puedes ver?**")
        st.markdown("- Tabla correo → rol en `.streamlit/secrets.toml` (fuera del repositorio).\n"
                    "- El rol decide pantallas (persona × pantalla) y columnas (persona × dato).\n"
                    "- Filtro por ANALISTA_ID en el servidor: lo ajeno nunca llega al navegador.\n"
                    "- La caché recibe el rol como argumento: no se mezclan resultados entre roles.")
    with st.container(border=True):
        st.markdown("**Superficie de exposición y limitaciones declaradas**")
        st.markdown("- **URL pública:** sin sesión no se muestra nada.\n"
                    "- **Repositorio:** `.gitignore` excluye el CSV, la bitácora SQLite y `secrets.toml`.\n"
                    "- **Descargas:** se desactiva la exportación nativa de tablas (`disableDataExport`); la única "
                    "descarga es la propuesta de Mariana, solo con agregados.\n"
                    "- **Errores:** `showErrorDetails = \"none\"` oculta tracebacks con rutas o datos.\n"
                    "- **Limitación:** Streamlit no trae roles; la autorización es código propio y un error ahí "
                    "expone datos (por eso hay pruebas). MFA depende del proveedor. Con datos reales conviene un "
                    "servidor propio en lugar de Community Cloud.")
