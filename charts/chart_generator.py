"""
chart_generator.py — Generador de gráficos interactivos para BBD.
"""

import plotly.graph_objects as go
import pandas as pd
import numpy as np
from core.simulation import SimulationResult
from charts.export import COLORS, setup_plotly_theme

def plot_sp500_history(df: pd.DataFrame, log_scale: bool = True) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], mode="lines", name="S&P 500", line=dict(color=COLORS["accent_blue"], width=2)))
    fig.update_layout(title="Histórico del S&P 500", yaxis_type="log" if log_scale else "linear")
    return fig

def self_color_rgbs(hex_color: str) -> str:
    hex_color = hex_color.lstrip('#')
    return ','.join(str(int(hex_color[i:i+2], 16)) for i in (0, 2, 4))

def plot_comparative_performance(result: SimulationResult) -> go.Figure:
    """GRÁFICO: Buy Borrow Die Net Equity vs Sell-to-Live."""
    timeline = result.timeline
    
    fig = go.Figure()

    # Sell-to-Live
    fig.add_trace(go.Scatter(
        x=timeline["date"], y=timeline["stl_activos"],
        mode="lines", name="Vender para Vivir (Neto Venta)",
        line=dict(color=COLORS["text_secondary"], width=2, dash="dot")
    ))
    
    # Buy Borrow Die Net Worth
    fig.add_trace(go.Scatter(
        x=timeline["date"], y=timeline["equity"],
        mode="lines", name="Buy Borrow Die (Net Worth)",
        line=dict(color=COLORS["accent_green"], width=3)
    ))

    mc_dates = timeline[timeline["margin_call"]]["date"]
    mc_values = timeline["equity"][timeline["margin_call"]]
    if not mc_dates.empty:
        fig.add_trace(go.Scatter(x=mc_dates, y=mc_values, mode="markers", name="Margin Call Ruina", marker=dict(color=COLORS["accent_red"], size=12, symbol="x")))

    fig.update_layout(
        title="Patrimonio Neto: BBD vs Venta Clásica",
        yaxis_title="Capital del Inversor (€)",
        yaxis_type="log",
        hovermode="x unified"
    )
    return fig

def plot_lombard_anatomy(result: SimulationResult) -> go.Figure:
    """GRÁFICO: Activos totales creciendo, y la Deuda creciendo como área apilada."""
    timeline = result.timeline
    
    fig = go.Figure()
    # Deuda (rojo)
    fig.add_trace(go.Scatter(
        x=timeline["date"], y=timeline["deuda"],
        mode="lines", name="Deuda Pendiente (Préstamo)",
        stackgroup="one",
        line=dict(color=COLORS["accent_red"], width=0),
        fillcolor=f"rgba({self_color_rgbs(COLORS['accent_red'])}, 0.5)"
    ))
    # Equity (azul)
    fig.add_trace(go.Scatter(
        x=timeline["date"], y=timeline["equity"],
        mode="lines", name="Equity Líquido (Herencia)",
        stackgroup="one",
        line=dict(color=COLORS["accent_blue"], width=0),
        fillcolor=f"rgba({self_color_rgbs(COLORS['accent_blue'])}, 0.7)"
    ))
    # Activos totales (línea de total)
    fig.add_trace(go.Scatter(
        x=timeline["date"], y=timeline["activos_totales"],
        mode="lines", name="Activos Totales Depositados",
        line=dict(color=COLORS["text_primary"], width=2)
    ))

    fig.update_layout(
        title="Anatomía de la Posición BBD",
        yaxis_title="Dólares ($)",
        hovermode="x unified"
    )
    return fig


def plot_drawdown_comparison(result: SimulationResult) -> go.Figure:
    timeline = result.timeline
    
    # Drawdown net worth actuals
    equity_max = timeline["equity"].cummax()
    bbd_dd = (timeline["equity"] - equity_max) / equity_max.replace(0, np.nan)
    
    stl_max = timeline["stl_activos"].cummax()
    stl_dd = (timeline["stl_activos"] - stl_max) / stl_max.replace(0, np.nan)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=timeline["date"], y=stl_dd,
        mode="lines", name="Drawdown Tradicional (Vender)",
        fill="tozeroy",
        line=dict(color=COLORS["text_secondary"], width=1),
        fillcolor="rgba(179,179,183,0.3)"
    ))

    fig.add_trace(go.Scatter(
        x=timeline["date"], y=bbd_dd,
        mode="lines", name="Drawdown Pánico (BBD)",
        fill="tozeroy",
        line=dict(color=COLORS["accent_red"], width=2),
        fillcolor=f"rgba({self_color_rgbs(COLORS['accent_red'])}, 0.5)"
    ))

    fig.update_layout(
        title="Impacto del Deuda en las Caídas del Mercado",
        yaxis_title="Caída desde Pico (%)",
        yaxis_tickformat=".0%",
        hovermode="x unified"
    )
    return fig

def plot_rolling_success(res_df: pd.DataFrame, initial_capital: float) -> go.Figure:
    fig = go.Figure()

    # Separar en exitos y fracasos
    df_success = res_df[~res_df["Wiped_Out"]]
    df_fail = res_df[res_df["Wiped_Out"]]

    fig.add_trace(go.Bar(
        x=df_success["Start_Date"], y=df_success["Final_Equity"],
        name="Éxito (Herencia Intacta)", marker_color=COLORS["accent_green"]
    ))
    
    # Para los fracasos (margin call), dibujamos una barra pequeña roja o la mostramos en 0.
    # Mostrar The equity at failure es 0, let's plot a red bar at capital_inicial * 0.1 to just show a red tick
    if not df_fail.empty:
        fig.add_trace(go.Bar(
            x=df_fail["Start_Date"], y=[initial_capital * 0.05] * len(df_fail),
            name="Ruina (Margin Call)", marker_color=COLORS["accent_red"],
            hoverinfo="x+name"
        ))

    fig.add_hline(y=initial_capital, line_dash="solid", line_color=COLORS["text_secondary"], annotation_text="Break Even Inicial")

    fig.update_layout(
        title="Patrimonio Final por Año de Inicio de Jubilación",
        yaxis_title="Herencia Generada ($)",
        yaxis_type="log",
        barmode="group",
        hovermode="x unified"
    )
    return fig

def plot_viability_heatmap(df_matrix: pd.DataFrame) -> go.Figure:
    """GRÁFICO: Mapa de Calor 2D (Tasa Retiro vs LTV)."""
    df = df_matrix.set_index("Withdrawal_Rate")
    
    z = df.values
    x = df.columns.tolist()
    y = [f"{rate:.1%}" for rate in df.index]

    fig = go.Figure(data=go.Heatmap(
        z=z, x=x, y=y,
        colorscale="RdYlGn",
        zmin=0.0, zmax=1.0,
        hovertemplate="LTV Máximo: %{x}<br>Tasa de Retiro: %{y}<br>Probabilidad Éxito: %{z:.1%}<extra></extra>",
        text=[[f"{val:.0%}" for val in row] for row in z],
        texttemplate="%{text}",
        textfont={"size": 12}
    ))
    
    fig.update_layout(
        title="Matriz de Vida Muerte (Stress Test Combinado)",
        xaxis_title="Maximum LTV Permitido por el Broker",
        yaxis_title="Tasa de Retiro Inicial (%)"
    )
    return fig
