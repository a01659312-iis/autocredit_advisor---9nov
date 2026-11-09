# AutoCredit Advisor · Dashboard en Streamlit

Tablero de riesgo de crédito automotriz para tres personas sobre el mismo dato:

| Persona | Pantalla | Decisión que habilita |
|---|---|---|
| **Adrián** · analista de crédito | P1 Bandeja · P2 Ficha | Aprobar, condicionar o rechazar una solicitud en < 5 min |
| **Mariana** · gerente de riesgo | P3 Cartera por segmento | Endurecer o relajar la política de un segmento |
| **Luis** · operación del modelo | P4 Monitor operativo | Escalar una alerta o descartarla con nota |
| Todos | P0 Inicio de sesión · P5 Estados y recorridos · P6 Gobierno de datos | Acceso, recuperación y transparencia |

## Cómo correrlo en Visual Studio Code

1. Abre la carpeta `autocredit_advisor` en VS Code (**Archivo → Abrir carpeta**). Acepta instalar las extensiones recomendadas (Python, Pylance, Debugpy).
2. Verifica que `data/Base_SAS_Equipo3.csv` exista (ya viene incluido).
3. Crea el entorno: **Terminal → Ejecutar tarea… → «Crear entorno e instalar dependencias»**, o en la terminal:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
4. Selecciona el intérprete `.venv` (**Ctrl+Shift+P → Python: Select Interpreter**).
5. Corre el tablero:
   - **F5** con la configuración «AutoCredit Advisor (Streamlit)» (permite poner breakpoints), o
   - `streamlit run app.py` en la terminal. Se abre en http://localhost:8501.
6. Pruebas: pestaña **Testing** de VS Code o `pytest` (43 pruebas: modelo, seguridad, registros y la app completa por rol).

Requiere Python 3.10 o superior y Streamlit 1.66 o superior.

### Cuentas de prueba (modo demostración)

Sin `.streamlit/secrets.toml` la app arranca en **modo demostración** y en P0 eliges una cuenta:

| Cuenta | Rol | Qué ve |
|---|---|---|
| Adrián Pérez (A-017) | analista | P1, P2, P5, P6 — solo sus 25 solicitudes |
| Sofía Reyes (A-022) | analista | Lo mismo, con otras 25 solicitudes (demuestra el filtro por ANALISTA_ID) |
| Mariana Torres | gerente | P3, P5, P6 — solo agregados |
| Luis Ramírez | operación | P4, P5, P6 — métricas y distribuciones |
| Invitado sin rol | — | «Pide acceso a tu gerente», ningún dato |

En la barra lateral, **Controles de demostración** permite simular la expiración de sesión, cambiar el escenario del monitor (drift, normal, carga atrasada, datos incompletos) y reiniciar la bitácora.

### Inicio de sesión real (OIDC)

Copia `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml`, llena `[auth]` con tu proveedor (Microsoft Entra ID o Google), da de alta los correos en `[roles]` e instala `pip install "streamlit[auth]"`. Con eso P0 usa `st.login` y la tabla correo → rol vive fuera del repositorio.

## Estructura

```
autocredit_advisor/
├── app.py                  # entrada: sesión, rol → navegación, barra lateral
├── vistas/                 # una pantalla por archivo
│   ├── p0_login.py · sin_acceso.py
│   ├── p1_bandeja.py · p2_ficha.py        # Adrián
│   ├── p3_cartera.py                      # Mariana
│   ├── p4_monitor.py                      # Luis
│   └── p5_estados.py · p6_gobierno.py     # todos
├── src/
│   ├── config.py           # umbrales, políticas y REGISTROS (filtros, controles, métricas)
│   ├── seguridad.py        # matrices persona × pantalla y persona × dato (las aplica el código)
│   ├── auth.py             # st.login / modo demo, expiración de sesión, exigir_acceso()
│   ├── datos.py            # carga, validación de esquema, segmentos
│   ├── modelo.py           # regresión logística, explicación local, enganche requerido, PSI
│   ├── simulacion.py       # lo que la base aún no trae (folios, horas, decisiones)
│   ├── servicios.py        # caché separada por rol
│   ├── almacen.py          # bitácora SQLite (decisiones, borradores, alertas)
│   ├── graficas.py         # G1–G10 en Plotly, modo claro y oscuro
│   └── ui.py               # rótulos de origen, filtros amarrados, corte activo, estados vacíos
├── tests/                  # pytest
├── data/                   # CSV (ignorado por git) y bitácora autocredit.db (se crea sola)
├── .streamlit/             # config.toml (tema y exposición) + secrets.toml.example
└── .vscode/                # launch.json (F5), tasks.json, settings.json, extensions.json
```

## Cómo se atendió la retroalimentación

| Bloque | Observación | Qué hace ahora el tablero |
|---|---|---|
| **C** (−1) | Solo había error en el login; faltaba un recorrido de error dentro del flujo de análisis | Cada flujo tiene errores **dentro del análisis**, programados y probados: en P2, dato faltante (Aprobar bloqueado → «Pedir documento» → llega el documento → PD recalculada), dato fuera del rango de entrenamiento (sin recomendación, motivo obligatorio), dato imposible (no se calcula PD), contradecir al modelo sin motivo (no se guarda), folio ajeno (bloqueo sin datos) y sesión expirada (regresa a la misma solicitud con su borrador). En P3, corte vacío, n < 30 y curva sin sustento. En P4, datos viejos, ventana vacía y escalar/descartar sin nota. P5 muestra los tres recorridos con cada bifurcación y un catálogo con «cómo verlo». |
| **E** (−1) | No todos los filtros se amarraban a la decisión de una persona | Todo filtro (F1–F7) **y todo control de vista** (C1–C3) sale de un registro en `config.py` con persona, decisión y valor por defecto. Debajo de cada widget se lee «↳ Mariana decide: …». `tests/test_registros.py` falla si alguno queda sin persona o decisión, o si la persona no puede ver esa pantalla. P6 lista filtros, controles y filtros descartados con su razón. |
| **F** (−1) | La matriz persona × dato sensible no aparecía completa como tabla | P6 muestra la **matriz completa** (32 datos × 3 personas + tratamiento): las 12 columnas de la base, los calculados, las columnas operativas propuestas y las protegidas que no vienen en esta base. Esa misma tabla es la que consulta el código: `aplicar_politica_fila()` recorta lo que recibe la ficha, `servicios` verifica el nivel antes de entregar agregados y lo no listado se niega por defecto. |

## Segunda ronda de recomendaciones (formato, layout, semáforo y lógica)

| Recomendación | Qué hace ahora el tablero |
|---|---|
| **Asteriscos con nota al pie** | Sin marca = dato real · `*` = dato propio (PD, segmentos, cortes) · `**` = dato simulado (folio, fecha, estado). Cada pantalla termina con un pie que explica las marcas que usa. |
| **Menos mayúsculas** | «DEFAULT», «SIMULADO», «APROBAR», etc. pasaron a minúsculas normales («incumplimiento», «simulado», «aprobar»). Los nombres de columna de la base solo aparecen en la matriz de gobierno. |
| **Menos scroll, filtros y botones arriba** | KPIs y filtros en la parte superior; en P1 el botón «Abrir la de mayor prioridad» va junto a los filtros; en P2 la decisión está a la derecha, a la altura del riesgo; en P4 ventana y frescura comparten renglón y los semáforos van antes que las alertas. El amarre de filtros ocupa un solo renglón (la decisión completa está en ⓘ). |
| **Descentrar el «default»** | P3 abre con la entidad («Cartera completa: 80,000 créditos» o el nombre del segmento); el incumplimiento es una métrica más. |
| **Cajas para el proceso** | P2 muestra los 4 pasos (validar datos → revisar riesgo → decidir → validar y registrar) en cajas con su estado; P5 muestra los recorridos en cajas. |
| **Simplificar 2+ dimensiones** | P3 muestra una dimensión a la vez (C1); el cruce DTI × otra dimensión quedó en un desplegable «Cruce avanzado». |
| **Semáforo verde / amarillo / rojo** | Nivel de riesgo 🟢🟡🔴 en la bandeja, la ficha y la partición; segmentos 🟢 ≤ 15% · 🟡 15–20% · 🔴 > 20%; P4 con estado «advertencia» (amarillo) cerca del borde de la banda. Siempre ícono + texto. |
| **Íconos de tendencia y de estado** | ▲/▼ frente a la media de la cartera y frente a ayer; ⏳ pendiente · 📄 en espera · ✅ resuelta; ✅ aprobar · 🟠 condicionar · ❌ rechazar; 🔔 cambio de política. |
| **Primero validar, luego registrar** | «Validar decisión» revisa decisión, motivo y consistencia; solo después aparece «Confirmar y registrar» en un diálogo con el resumen. Mariana también confirma antes de publicar un corte. |
| **Benchmark contra la media** | La ficha compara PD, DTI, PTI, LTV, enganche y uso revolvente contra la media de los 80,000 créditos, con ▲/▼ y 🔴/🟢 según si la diferencia sube o baja el riesgo. G3 agrega la barra de la media. La bandeja muestra la PD vs. la media. |
| **Alerta al analista por cambio de segmento** | Mariana publica un corte para un segmento (p. ej. DTI alto 15% → 12%). Adrián ve 🔔 en su bandeja con «el corte cambió de 15.0% → 12.0%» y cada folio cuya sugerencia cambió («aprobar → condicionar»); la ficha también lo avisa. La reversión también notifica. |
| **Cartera: incumplimiento, alto y bajo riesgo** | P3 muestra cuántos clientes cayeron en incumplimiento al cierre de la base (10,783, 13.5%) y la partición alto/bajo riesgo con % de créditos y % del incumplimiento (el alto riesgo es 30.8% de los créditos y concentra 66.3% del incumplimiento). |
| **Variables significativas** | Columna «Peso en el modelo» (★★★ alta · ★★ media · ★ baja) en el expediente y en Salud del modelo, con significancia z. Las más significativas: uso de crédito revolvente, DTI, enganche y pagos fallidos. |

## Mejoras adicionales que encontramos

- **Datos reales, no supuestos.** El PDF describía 100,000 × 83 columnas; `Base_SAS_Equipo3.csv` trae **80,000 × 12** (default 13.48%, sin nulos). Se quitaron los elementos que no existen en la base (score de crédito, tipo de vehículo, situación laboral) y se reemplazaron por segmentos reales (DTI, enganche, pagos fallidos, bancarrota, LTV).
- **Modelo real de PD.** Regresión logística (AUC 0.777 en un 25% que el modelo no vio, igual que un gradient boosting). Con eso G1, G2, G4 y **G7 dejan de ser SIMULADOS** y pasan a CALCULADOS.
- **Equidad.** `FINANCIAL_LITERACY_SCORE` se excluye del modelo: puede ser proxy socioeconómico, no se puede comprobar con un documento y solo aporta ~0.0015 de AUC (la ficha del modelo muestra la diferencia en vivo).
- **«Condicionar» con número.** La ficha calcula el enganche mínimo que deja la PD bajo el corte y deja ajustarlo (control C3).
- **Bitácora que conecta personas.** La decisión de Adrián se guarda en SQLite y alimenta el acuerdo modelo–analista que vigila Luis (con folio enmascarado). Las alertas escaladas o descartadas quedan con nota para el siguiente turno.
- **Salud del modelo** (revisión mensual): AUC, KS, recall al corte, calibración esperado vs. observado por decil.
- **Tiempo por decisión** medido contra la meta de 5 min.
- **Exposición:** tracebacks ocultos, exportación nativa de tablas desactivada, la única descarga es la propuesta agregada de Mariana, caché separada por rol, `.gitignore` para CSV, bitácora y secretos.
- **Accesibilidad:** modo claro y oscuro, estados con ícono + texto (nunca solo color), «Ver como tabla» en las gráficas clave, un solo eje Y por gráfica.

## Rótulos de origen

Cada gráfica lleva **REAL** (columna de la base), **CALCULADO** (derivado de la base o del modelo), **SIMULADO** (dato propuesto que la base aún no trae) o **POLÍTICA** (umbral del equipo). Lo simulado siempre se construye con filas REAL del holdout y es determinista por fecha, así que cada recarga muestra los mismos números.
