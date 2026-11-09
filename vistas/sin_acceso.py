"""Correo autenticado pero sin rol: se identifica a la persona y no se muestra ningún dato."""
import streamlit as st

from src import auth

usuario = auth.usuario_actual()
_, centro, _ = st.columns([1, 1.4, 1])
with centro:
    st.space("large")
    st.title("Pide acceso a tu gerente")
    with st.container(border=True):
        st.markdown(f"Iniciaste sesión como **{usuario.email if usuario else ''}**, pero ese correo no tiene "
                    "un rol asignado (analista, gerente u operación).")
        st.markdown("Por eso no se carga **ningún dato**: autenticarte dice quién eres; el rol decide qué "
                    "puedes ver. Tu gerente puede darte de alta en la tabla de roles.")
        st.button("Cerrar sesión", on_click=auth.salir, type="primary", icon=":material/logout:")
