"""
app.py — Dashboard Interactivo en Streamlit. Buy, Borrow, Die.
Ejecutar con: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from data.fetch_sp500 import get_sp500_data
from core.simulation import SimulationConfig, run_simulation
from core.metrics import calculate_all_metrics, format_metrics_table
from core.rolling_simulation import run_rolling_simulations, run_viability_matrix
import numpy as np
import os
import json
import time

from charts.chart_generator import (
    plot_sp500_history, plot_comparative_performance, 
    plot_lombard_anatomy, plot_drawdown_comparison,
    plot_rolling_success, plot_viability_heatmap
)

# ======= CONFIGURACIÓN DE PÁGINA =======
st.set_page_config(
    page_title="Buy, Borrow, Die Simulator",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

SAVE_DIR = "saved_maps"
os.makedirs(SAVE_DIR, exist_ok=True)

if "viability_maps_history" not in st.session_state:
    st.session_state.viability_maps_history = []
    
    # Cargar mapas guardados en disco de sesiones anteriores
    for f in sorted(os.listdir(SAVE_DIR), reverse=True): # Los más recientes primero
        if f.endswith('.json'):
            try:
                with open(os.path.join(SAVE_DIR, f), 'r') as file:
                    data = json.load(file)
                    df_matrix = pd.DataFrame(data['df'])
                    fig = plot_viability_heatmap(df_matrix)
                    st.session_state.viability_maps_history.append({
                        "id": f,
                        "desc": data['desc'],
                        "fig": fig
                    })
            except Exception:
                pass

# ======= CARGA DE DATOS =======
@st.cache_data
def load_data():
    return get_sp500_data()

try:
    df_sp500 = load_data()
except Exception as e:
    st.error(f"Error cargando los datos de base: {str(e)}")
    st.stop()


# ======= BARRA LATERAL (CONTROLES) =======
st.sidebar.title("⚙️ Parámetros BBD")

with st.sidebar.expander("👤 Perfil Vital", expanded=True):
    edad_actual = st.number_input("Edad Actual", min_value=18, max_value=100, value=45, step=1)
    esperanza_vida = st.number_input("Esperanza de Vida", min_value=edad_actual+5, max_value=120, value=85, step=1)
    duracion = esperanza_vida - edad_actual
    st.caption(f"La simulación durará exactamente **{duracion} años** o hasta la ruina.")

with st.sidebar.expander("💸 Extracción y Capital", expanded=True):
    capital = st.number_input("Capital Inicial ($)", min_value=100_000, max_value=50_000_000, value=1_000_000, step=100_000)
    
    retiro_pct = st.slider("Tasa de Retiro Anual Inicial (%)", min_value=0.5, max_value=15.0, value=3.5, step=0.1) / 100.0
    st.markdown(f"**Retiro el Año 1:** ${(capital * retiro_pct):,.0f}")
    
    retiro_modo = st.selectbox("Modalidad de Extracción", 
                               ["Fija (Sobre capital inicial)", "Dinámica (% sobre capital actual)"])
    modo_str = "fixed_initial" if "Fija" in retiro_modo else "dynamic_current"
    
    inflacion_margen = st.slider("Margen Personal s/ Inflación Real (%)", min_value=-5.0, max_value=5.0, value=0.5, step=0.5,
                                  help="En cada año simulado, el coste de vida subirá lo que subió el IPC (CPI Histórico) ese año MÁS este margen. (Ej. 0.0% usa la inflación exacta).") / 100.0

with st.sidebar.expander("🏦 Condiciones de Deuda y Alertas", expanded=False):
    broker_preset = st.selectbox(
        "Perfil de Broker / LTV", 
        ["Interactive Brokers (Reg T)", "Futuros S&P", "Personalizado"],
        index=1
    )
    is_ibkr = "Interactive Brokers" in broker_preset
    is_futuros = "Futuros S&P" in broker_preset
    is_custom = "Personalizado" in broker_preset

    # Futuros S&P = 80% LTV, IBKR = 75% LTV (25% Maintenance Margin)
    def_ltv = 80 if is_futuros else (75 if is_ibkr else 85)
    ltv_lender = st.slider("Umbral de Margin Call (LTV %)", min_value=30, max_value=100, value=def_ltv, step=5, disabled=not is_custom) / 100.0

    interest_mode = st.selectbox("Modo de Interés", ["fijo", "variable (T-Bill)"], index=1)
    spread_var = 0.0
    tasa_fija = 0.04
    if interest_mode == "fijo":
        tasa_fija = st.slider("Tasa de Interés Anual Fija (%)", min_value=0.0, max_value=15.0, value=3.5, step=0.1) / 100.0
    else:
        spread_var = st.number_input("Spread sobre Tasa Base (%)", min_value=0.0, max_value=10.0, value=0.0, step=0.25, help="Benchmark (T-Bill) + Spread (ej. en IBKR)") / 100.0

    alerta_interes = st.slider("Alerta Intereses Altos (%)", min_value=2.0, max_value=15.0, value=6.0, step=0.5, help="Pintaremos de naranja/rojo los períodos si el coste de la deuda superó este porcentaje tóxico.") / 100.0

with st.sidebar.expander("⏱️ Período Histórico", expanded=True):
    min_date = df_sp500["Date"].min().to_pydatetime()
    max_date = df_sp500["Date"].max().to_pydatetime()
    
    historias = {
        "Selección Libre": min_date,
        "Pánico de 1907": datetime(1907, 10, 1),
        "1ª Guerra Mundial (1914)": datetime(1914, 7, 1),
        "Felices Años 20 (1920)": datetime(1920, 1, 1),
        "Gran Depresión (1929)": datetime(1929, 8, 1),
        "2ª Guerra Mundial (1939)": datetime(1939, 9, 1),
        "Post 2ª Guerra Mundial (1946)": datetime(1946, 1, 1),
        "Creación del S&P 500 (1957)": datetime(1957, 3, 4),
        "Creación del NASDAQ (1971)": datetime(1971, 2, 8),
        "Fin Bretton Woods - Patrón Oro (1971)": datetime(1971, 8, 1),
        "Era Reagan - Bull Market (1981)": datetime(1981, 1, 1),
        "Pre-Lunes Negro (1987)": datetime(1987, 8, 1),
        "Guerra del Golfo (1990)": datetime(1990, 8, 1),
        "Nacimiento del Euro (1999)": datetime(1999, 1, 1),
        "Post Burbuja Dot-Com (2000)": datetime(2000, 1, 1),
        "Quiebra Lehman Brothers (2008)": datetime(2008, 9, 1),
        "Post Crisis Financiera (2009)": datetime(2009, 3, 1),
        "Pandemia COVID-19 (2020)": datetime(2020, 2, 1)
    }

    if "sidebar_epoch_picker" not in st.session_state:
        st.session_state.sidebar_epoch_picker = "Creación del S&P 500 (1957)"

    epoca_seleccionada = st.selectbox(
        "Épocas Históricas Rápidas", 
        options=list(historias.keys()), 
        key="sidebar_epoch_picker"
    )

    if epoca_seleccionada != "Selección Libre":
        default_start = historias[epoca_seleccionada]
        if default_start < min_date:
            default_start = min_date
    else:
        default_start = min_date

    start_date = st.date_input("Fecha de Inicio de la Jubilación / Estrategia", value=default_start, min_value=min_date, max_value=max_date)

# ======= EJECUCIÓN SIMULACIÓN =======
config = SimulationConfig(
    capital_inicial=capital,
    withdrawal_rate_pct=retiro_pct,
    withdrawal_mode=modo_str,
    inflation_margin_pct=inflacion_margen,
    tasa_interes_anual=tasa_fija,
    fecha_inicio=start_date.strftime("%Y-%m-%d"),
    duracion_anios=duracion,
    margin_call_threshold=ltv_lender,
    modo_interes="fijo" if interest_mode == "fijo" else "variable",
    high_interest_warning_threshold=alerta_interes,
    amortizacion="capitalizada", # Siempre acumulamos la deuda
    spread_interes_variable=spread_var,
    capital_gains_tax_pct=0.25 # Impuestos por tramos estimando un 25% para retiros notables
)

result = run_simulation(config, df_sp500)
metrics = calculate_all_metrics(result.timeline, capital)

# ======= PANEL PRINCIPAL =======
st.title("💸 Buy, Borrow, Die Simulator")
st.markdown("*¿Qué pasa si nunca vendes tus acciones, y en su lugar pides prestado contra ellas para vivir, dejando el problema a tus herederos?*")

with st.expander("📚 **Fuentes de Datos y Documentación**", expanded=False):
    st.markdown("""
    Todos los cálculos se realizan utilizando **datos históricos reales** para dotar a la simulación de la máxima fidelidad posible:
    - **S&P 500 Total Return:** Los precios y dividendos bursátiles históricos provienen de la [base de datos oficial de Robert Shiller (Yale)](http://www.econ.yale.edu/~shiller/data.htm), empalmados con Yahoo Finance para abarcar desde 1871 hasta el último mes de cierre. **Rendimientos calculados asumiendo reinversión total de dividendos**.
    - **Inflación (IPC/CPI):** Histórico de pérdida de poder adquisitivo utilizando el Consumer Price Index americano. Desde 1871 hasta 1913 recogido por estimaciones oficiales de Shiller, y desde 1913 en adelante medido empíricamente por la [Reserva Federal (FRED `CPIAUCNS`)](https://fred.stlouisfed.org/series/CPIAUCNS).
    - **Tipos de Interés:** Rendimiento de los Bonos a 10 Años de Shiller para datos antiguos, y extrapolado como proxy general de costes de financiación (T-Bill) desde Yahoo Finance para la modernidad.
    """)

# Resumen de Header
col1, col2, col3, col4, col5 = st.columns(5)

if result.was_wiped_out:
    col1.error("💥 QUEBRADO (Margin Call)")
    col2.metric("Años vividos antes de ruina", f"{(len(result.timeline)/12):.1f} años")
    col3.metric("Rentabilidad Inversión (CAGR)", f"{metrics['cagr']:.1%}", help="Retorno anualizado de la cartera incluyendo dividendos")
    st.error("⚠️ **RUINA TOTAL:** El banco ejecutó tus garantías porque tu deuda sobrepasó el LTV máximo permitido. No llegaste a heredar ni a fallecer con la cartera intacta.")
else:
    col1.success("✨ ESTRATEGIA COMPLETADA (Muerte)")
    col2.metric("Rentabilidad Inversión (CAGR)", f"{metrics['cagr']:.1%}", help="Retorno anualizado de la cartera incluyendo dividendos")
    col3.metric("Retiro Vitalicio (Cash Sacado)", f"${result.total_cash_withdrawn:,.0f}")
    
    col4.metric("Herencia Libre de Impuestos", f"${result.final_equity:,.0f}", 
                help="Lo que heredan limpiamente tus hijos = Valor Activos - Deuda a pagar.")
    col5.metric("Plusvalía del Muerto", f"${result.taxes_avoided_at_death:,.0f}",
                delta=f"vs Venta Tradicional" if result.taxes_avoided_at_death > 0 else f"Peor que Vender", 
                help="Ahorro vs haber vendido sistemáticamente para vivir pagando un 25% de ganancias sobre la plusvalía latente.")

if result.high_interest_months_count > 0:
    st.warning(f"🌡️ **Alerta de estrés de tasas:** Durante **{result.high_interest_months_count} meses** (un {result.high_interest_months_count/len(result.timeline):.0%}% de tu jubilación), el coste del préstamo superó tu umbral de dolor del {alerta_interes:.1%}. ¡La deuda capitalizó a ritmos peligrosos!")

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Evolución del Patrimonio", "💵 Anatomía Préstamo",
    "🔍 Historial Mensual", "🗓️ Simulaciones Históricas",
    "🧭 Mapa de Viabilidad"
])

with tab1:
    st.markdown("### Rendimiento Histórico: Buy&Borrow vs Sell-to-Live")
    st.plotly_chart(plot_comparative_performance(result), use_container_width=True)
    
    st.markdown("### Drawdowns de Capital")
    st.plotly_chart(plot_drawdown_comparison(result), use_container_width=True)

with tab2:
    st.markdown(f"### Desglose de Activos y Deuda ({duracion} años simulados)")
    st.plotly_chart(plot_lombard_anatomy(result), use_container_width=True)
    
    st.markdown("### Métricas Técnicas Adicionales")
    # Limpiamos métricas innecesarias de leverage, usamos table formatter original
    df_m = format_metrics_table(metrics, "Valor")
    st.dataframe(df_m.head(8), hide_index=True)

with tab3:
    st.markdown("### Historial Completo (Mes a Mes)")
    view_df = result.timeline[["date", "precio_sp500", "activos_totales", "deuda", "equity", "ltv_actual", "retiro_mensual", "tasa_interes_anualizada", "high_interest_flag", "stl_activos"]].copy()
    view_df.set_index("date", inplace=True)
    
    def color_high_interest(val):
        color = '#ff9999' if val else ''
        return f'background-color: {color}'
        
    st.dataframe(view_df.style.map(color_high_interest, subset=['high_interest_flag']).format({
        "precio_sp500": "${:,.2f}",
        "activos_totales": "${:,.0f}",
        "deuda": "${:,.0f}",
        "equity": "${:,.0f}",
        "retiro_mensual": "${:,.0f}",
        "ltv_actual": "{:.2%}",
        "tasa_interes_anualizada": "{:.2%}",
        "stl_activos": "${:,.0f}"
    }), height=500)

with tab4:
    st.markdown("### Probabilidades de Éxito Reales (Historia Americana Completa)")
    st.markdown(f"Pone a prueba tu plan exacto de jubilaciones de **{duracion} años**. Viaja al pasado, y simula qué habría pasado si te hubieras jubilado en 1871, luego en 1872, y así hasta probar todos los meses de la historia que hayan terminado.")
    
    if st.button("🚀 Ejecutar Todas las Jubilaciones Posibles", type="primary"):
        with st.spinner(f"Viajando en el tiempo para simular {duracion} años de BBD constantemente..."):
            res_df, stats = run_rolling_simulations(df_sp500, config)
            
            # Gráfico de resultados (Final Equity vs Start Date)
            st.plotly_chart(plot_rolling_success(res_df, capital), use_container_width=True)
            
            # Métricas
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Probabilidad de Éxito", f"{stats['success_rate']:.1%}", help=f"Porcentaje de veces que se aguantaron los {duracion} años sin un Margin Call.")
            c2.metric("Nº de Vidas Simuladas", f"{stats['total_simulations']}")
            c3.metric("Herencia Intacta Mediana", f"${stats['median_final_equity']:,.0f}")
            c4.metric("Ahorro Muerte Mediano", f"${stats['median_taxes_avoided']:,.0f}")
            
            if stats['success_rate'] < 0.95:
                st.error(f"❌ **Plan Arriesgado:** Esta estrategia de retiros solo sobrevivió a la historia el {stats['success_rate']:.1%} de las veces. Considera bajar el porcentaje de extracción inicial.")
            else:
                st.success(f"✅ **Plan Muy Sólido:** Has simulado las Guerras Mundiales, hiperinflación, crack del 29 y el plan aguantó un enorme {stats['success_rate']:.1%} de las veces.")

with tab5:
    st.markdown("### 🧭 Mapa de Viabilidad (Stress Test Global)")
    st.markdown(f"Genera una matriz cruzando distintas Tasas de Retiro contra Límites de Margin Call. Calcula la probabilidad de éxito de TODAS las cohortes históricas para cada casilla. **Esta matriz refleja tu configuración actual de {duracion} años de esperanza de vida.**")
    
    colA, colB = st.columns(2)
    with colA:
        wr_min = st.number_input("Retiro Mínimo (%)", value=2.0, step=0.5, format="%.1f")
        wr_max = st.number_input("Retiro Máximo (%)", value=6.0, step=0.5, format="%.1f")
        wr_step = st.number_input("Salto Retiro (%)", value=0.5, step=0.1, format="%.1f")
    with colB:
        ltv_min = st.number_input("LTV Mínimo (%)", value=50, step=10)
        ltv_max = st.number_input("LTV Máximo (%)", value=90, step=10)
        ltv_step = st.number_input("Salto LTV (%)", value=10, step=5)
        
    @st.cache_data(show_spinner=False)
    def cached_viability_matrix(base_df, wrs_tuple, ltvs_tuple, duration_years, inf_margen,
                                int_mode, t_fija, spread):
        # We pass all relevant config parameters to ensure cache invalidates correctly
        cfg = SimulationConfig(
            duracion_anios=duration_years,
            inflation_margin_pct=inf_margen,
            modo_interes="fijo" if int_mode == "fijo" else "variable",
            tasa_interes_anual=t_fija,
            spread_interes_variable=spread,
            amortizacion="capitalizada",
            capital_gains_tax_pct=0.25
        )
        return run_viability_matrix(base_df, cfg, list(wrs_tuple), list(ltvs_tuple))

    if st.button("🗺️ Generar Mapa de Calor", type="primary"):
        wrs = np.arange(wr_min, wr_max + 0.001, wr_step) / 100.0
        ltvs = np.arange(ltv_min, ltv_max + 0.001, ltv_step) / 100.0
        
        with st.spinner("Calculando en paralelo miles de vidas bursátiles... (se guardará en memoria caché)"):
            # Pasamos convertidos a tuple para que streamlit lo pueda hashear facilmente
            df_matrix = cached_viability_matrix(
                df_sp500, tuple(wrs), tuple(ltvs), duracion, inflacion_margen, interest_mode, tasa_fija, spread_var
            )
            
            fig = plot_viability_heatmap(df_matrix)
            
            config_desc = f"Vida: {duracion}a | Inf+{inflacion_margen:.1%} | Interés: {interest_mode}"
            
            # Save to disk
            timestamp = int(time.time())
            filename = f"map_{timestamp}.json"
            filepath = os.path.join(SAVE_DIR, filename)
            
            with open(filepath, 'w') as f:
                json.dump({
                    "desc": config_desc,
                    "df": df_matrix.to_dict(orient="records")
                }, f)
            
            # Save to history memory
            st.session_state.viability_maps_history.insert(0, {
                "id": filename,
                "desc": config_desc,
                "fig": fig
            })
            
    if len(st.session_state.viability_maps_history) > 0:
        st.markdown("---")
        st.markdown("### 🗂️ Historial de Mapas Generados")
        
        # Al tener historial, el más reciente es el index 0
        for i, item in enumerate(st.session_state.viability_maps_history):
            with st.expander(f"📌 {item.get('desc', 'Mapa guardado')} ", expanded=(i == 0)):
                st.plotly_chart(item["fig"], use_container_width=True, key=f"hist_chart_{i}")
        
        if st.columns([1,2,1])[1].button("🗑️ Borrar Historial de Mapas", use_container_width=True):
            for item in st.session_state.viability_maps_history:
                try:
                    os.remove(os.path.join(SAVE_DIR, item["id"]))
                except:
                    pass
            st.session_state.viability_maps_history = []
            st.rerun()