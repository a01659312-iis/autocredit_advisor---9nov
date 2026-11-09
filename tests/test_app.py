"""Pruebas de humo de la app completa por rol (streamlit.testing)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src import almacen

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _app(email=None):
    at = AppTest.from_file(APP, default_timeout=120)
    if email:
        at.session_state["demo_email"] = email
    return at.run()


def _titulos(at):
    return [t.value for t in at.title]


def test_sin_sesion_muestra_solo_login():
    at = _app()
    assert not at.exception
    assert "AutoCredit Advisor" in _titulos(at)
    assert not at.dataframe


def test_sin_rol_no_muestra_datos():
    at = _app("invitado@autocredit.mx")
    assert not at.exception
    assert "Pide acceso a tu gerente" in _titulos(at)
    assert not at.dataframe and not at.metric


@pytest.mark.parametrize("email,pagina,titulo", [
    ("adrian.perez@autocredit.mx", None, "Bandeja de solicitudes"),
    ("mariana.torres@autocredit.mx", None, "Cartera por segmento"),
    ("luis.ramirez@autocredit.mx", None, "Monitor operativo"),
    ("adrian.perez@autocredit.mx", "vistas/p5_estados.py", "Estados y recorridos"),
    ("luis.ramirez@autocredit.mx", "vistas/p6_gobierno.py", "Gobierno de datos"),
])
def test_pantallas_por_rol(email, pagina, titulo):
    at = _app(email)
    if pagina:
        at.switch_page(pagina).run()
    assert not at.exception, at.exception
    assert titulo in _titulos(at)


def test_ficha_con_folio_y_error_de_motivo():
    at = _app("adrian.perez@autocredit.mx")
    at.switch_page("vistas/p2_ficha.py")
    at.session_state["folio_actual"] = "AC-26052549"  # PD alta en la cola de A-017
    at.run()
    assert not at.exception, at.exception
    # Aprobar un caso sobre el corte sin motivo: no se guarda.
    at.segmented_control(key="dec_AC-26052549").set_value("Aprobar").run()
    validar = next(b for b in at.button if b.label.startswith("Validar decisión"))
    validar.click().run()
    assert any("No se registró" in e.value for e in at.error)
    assert almacen.decisiones().empty
    # Con motivo pasa la validación, pero NO se registra hasta confirmar en el diálogo.
    at.selectbox(key="mot_AC-26052549").set_value("Garantía o aval adicional").run()
    next(b for b in at.button if b.label.startswith("Validar decisión")).click().run()
    assert not at.exception, at.exception
    assert almacen.decisiones().empty
    # Validación aprobada: aparece el diálogo de confirmación y todavía no hay registro.
    assert any(b.label.startswith("Confirmar y registrar") for b in at.button)
    # (El clic dentro del diálogo se ejecuta como fragmento; se verifica en el navegador.)


def test_folio_ajeno_bloqueado():
    at = _app("sofia.reyes@autocredit.mx")
    at.switch_page("vistas/p2_ficha.py")
    at.session_state["folio_actual"] = "AC-26052549"  # pertenece a A-017
    at.run()
    assert not at.exception
    assert any("no está asignada" in e.value for e in at.error)
    assert not at.dataframe


def test_mariana_corte_vacio():
    at = _app("mariana.torres@autocredit.mx")
    for k, v in {"p3_F3": "Bajo", "p3_F4": "< 4%", "p3_F5": "3 o más", "p3_F6": "Con bancarrota"}.items():
        at.selectbox(key=k).set_value(v)
    at.run()
    assert not at.exception, at.exception
    assert any("Ningún crédito cumple" in m.value for m in at.markdown)


@pytest.mark.parametrize("escenario", ["drift", "normal", "atrasada", "nulos"])
def test_monitor_escenarios(escenario):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["demo_email"] = "luis.ramirez@autocredit.mx"
    at.session_state["escenario"] = escenario
    at.run()
    assert not at.exception, at.exception


def test_dato_faltante_bloquea_y_se_recupera_con_documento():
    folio = "AC-26073750"  # llegó sin SAVINGS_BALANCE (SIMULADO)
    at = _app("adrian.perez@autocredit.mx")
    at.switch_page("vistas/p2_ficha.py")
    at.session_state["folio_actual"] = folio
    at.run()
    assert not at.exception, at.exception
    assert any("llegó sin" in w.value for w in at.warning)
    assert at.segmented_control(key=f"dec_{folio}").options == ["Rechazar"]
    next(b for b in at.button if b.label.startswith("Simular que llegó")).click().run()
    assert not at.exception, at.exception
    assert not any("llegó sin" in w.value for w in at.warning)
    assert at.segmented_control(key=f"dec_{folio}").options == ["Aprobar", "Condicionar", "Rechazar"]


def test_sesion_expirada_regresa_a_la_misma_solicitud():
    folio = "AC-26055874"
    at = _app("adrian.perez@autocredit.mx")
    at.switch_page("vistas/p2_ficha.py")
    at.session_state["folio_actual"] = folio
    at.run()
    at.segmented_control(key=f"dec_{folio}").set_value("Rechazar").run()  # borrador guardado
    at.session_state["forzar_expiracion"] = True
    at.run()
    assert not at.exception, at.exception
    assert "AutoCredit Advisor" in _titulos(at)  # volvió a P0
    at.session_state["demo_email"] = "adrian.perez@autocredit.mx"
    at.run()
    assert not at.exception, at.exception
    assert "Ficha de solicitud" in _titulos(at)
    assert at.session_state["folio_actual"] == folio
    assert at.segmented_control(key=f"dec_{folio}").value == "Rechazar"


def test_cambio_de_politica_notifica_al_analista():
    """Mariana publica un corte más estricto para DTI alto y Adrián recibe el aviso con los folios que cambian."""
    almacen.publicar_politica({"F3": "Alto"}, "Endeudamiento (DTI) = Alto", 0.15, 0.10, 26499, "M. Torres")
    at = _app("adrian.perez@autocredit.mx")
    assert not at.exception, at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "La gerencia cambió" in textos and "15.0% → 10.0%" in textos
    next(b for b in at.button if b.label == "Entendido").click().run()
    assert not any("La gerencia cambió" in m.value for m in at.markdown)


def test_mariana_publica_corte():
    at = _app("mariana.torres@autocredit.mx")
    at.selectbox(key="p3_F3").set_value("Alto").run()
    assert not at.exception, at.exception
    slider = next(s for s in at.slider if s.key.startswith("p3_c2_"))
    slider.set_value(12.0).run()
    next(b for b in at.button if b.label.startswith("Publicar este corte")).click().run()
    assert any(b.label.startswith("Confirmar y publicar") for b in at.button)
    assert almacen.politicas().empty  # nada se registra sin confirmar
