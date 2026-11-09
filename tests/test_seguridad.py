"""Bloque F: la matriz persona × dato es completa y el código la aplica."""
import pandas as pd

from src import config as C, seguridad as S, simulacion


def test_matriz_cubre_todas_las_columnas_de_la_base(base):
    datos_en_matriz = {f["dato"] for f in S.MATRIZ_DATOS}
    assert set(base.columns) <= datos_en_matriz


def test_matriz_tiene_las_tres_personas_en_cada_fila():
    tabla = S.tabla_matriz_datos()
    for col in ("Adrián (analista)", "Mariana (gerente)", "Luis (operación)", "Tratamiento"):
        assert tabla[col].notna().all()
        assert (tabla[col] != "").all()


def test_variables_protegidas_ocultas_para_adrian_y_mariana():
    for dato in ("RACE_ETH", "GENDER", "PRIMARY_LANGUAGE", "AGE / AGE_BAND", "MEDICAL_DEBT_FLAG"):
        assert S.nivel_acceso("analista", dato) == S.OCULTO
        assert S.nivel_acceso("gerente", dato) == S.OCULTO


def test_lo_desconocido_se_niega_por_defecto():
    assert S.nivel_acceso("analista", "COLUMNA_NUEVA") == S.OCULTO
    assert S.aplicar_politica_fila("analista", {"COLUMNA_NUEVA": 1}) == {}


def test_la_ficha_no_recibe_default_ni_score_excluido(base):
    fila = base.iloc[0].to_dict()
    recortada = S.aplicar_politica_fila("analista", fila)
    assert "DEFAULT" not in recortada
    assert "FINANCIAL_LITERACY_SCORE" not in recortada
    assert set(C.VARIABLES_MODELO) <= set(recortada)


def test_mariana_no_recibe_datos_individuales():
    assert S.columnas_individuales("gerente", C.COLUMNAS_ESPERADAS) == []
    assert S.nivel_acceso("gerente", "LOAN_ID / FOLIO") == S.OCULTO


def test_luis_ve_folio_enmascarado():
    assert S.nivel_acceso("operacion", "LOAN_ID / FOLIO") == S.ENMASCARADO
    assert S.enmascarar("AC-26012345") == "****2345"


def test_matriz_pantallas():
    assert S.puede_ver("analista", "P1") and not S.puede_ver("analista", "P3")
    assert S.puede_ver("gerente", "P3") and not S.puede_ver("gerente", "P2")
    assert S.puede_ver("operacion", "P4") and not S.puede_ver("operacion", "P1")
    assert not S.puede_ver(None, "P5")


def test_colas_de_analistas_no_se_cruzan(modelo):
    a, _ = simulacion.cola_base(modelo, "A-017")
    b, _ = simulacion.cola_base(modelo, "A-022")
    assert not set(a["FOLIO"]) & set(b["FOLIO"])
    assert "DEFAULT" not in a.columns and "PD" not in a.columns
