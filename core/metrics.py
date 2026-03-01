"""
metrics.py — Cálculo de métricas de riesgo para simulaciones de apalancamiento.

Uso:
    from core.metrics import calculate_all_metrics
    metrics = calculate_all_metrics(timeline, config)
"""

import pandas as pd
import numpy as np
from typing import Dict, Any


def calculate_all_metrics(timeline: pd.DataFrame, capital_inicial: float,
                           rf_annual: float = 0.02) -> Dict[str, Any]:
    """
    Calcula el conjunto completo de métricas de riesgo/retorno.

    Args:
        timeline: DataFrame con columna 'equity' y 'retorno_mensual'
        capital_inicial: Capital inicial del inversor
        rf_annual: Tasa libre de riesgo anual (default 2%)

    Returns:
        Diccionario con todas las métricas calculadas.

    Example:
        >>> metrics = calculate_all_metrics(result.timeline, 100_000)
        >>> print(f"Sharpe: {metrics['sharpe_ratio']:.2f}")
    """
    equity = timeline["equity"].replace(0, np.nan).dropna()
    if len(equity) < 2:
        return _empty_metrics()

    monthly_returns = equity.pct_change().dropna()
    n_months = len(equity)
    n_years = n_months / 12

    # Retornos
    total_return = (equity.iloc[-1] / capital_inicial) - 1
    cagr = (1 + total_return) ** (1 / max(n_years, 0.1)) - 1

    # Drawdown
    rolling_max = equity.cummax()
    drawdowns = (equity - rolling_max) / rolling_max
    max_drawdown = drawdowns.min()

    # Tiempo bajo el agua (months underwater)
    underwater = (drawdowns < -0.001).sum()

    # Períodos de recuperación
    recovery_months = _calc_recovery_periods(equity)

    # Sharpe Ratio
    rf_monthly = rf_annual / 12
    excess_returns = monthly_returns - rf_monthly
    sharpe = (excess_returns.mean() / excess_returns.std() * np.sqrt(12)
              if excess_returns.std() > 0 else 0.0)

    # Sortino Ratio (solo volatilidad negativa)
    negative = monthly_returns[monthly_returns < rf_monthly]
    downside_vol = negative.std() * np.sqrt(12) if len(negative) > 1 else 0.001
    sortino = (cagr - rf_annual) / downside_vol if downside_vol > 0 else 0.0

    # Calmar Ratio
    calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else 0.0

    # VaR histórico (95% y 99%)
    var_95 = monthly_returns.quantile(0.05)
    var_99 = monthly_returns.quantile(0.01)

    # CVaR (Expected Shortfall)
    cvar_95 = monthly_returns[monthly_returns <= var_95].mean()
    cvar_99 = monthly_returns[monthly_returns <= var_99].mean()

    # Skewness y Kurtosis
    skew = monthly_returns.skew()
    kurt = monthly_returns.kurt()

    # Win Rate mensual
    win_rate = (monthly_returns > 0).mean()

    # Mejor / Peor mes
    best_month = monthly_returns.max()
    worst_month = monthly_returns.min()

    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "months_underwater": int(underwater),
        "max_recovery_months": max(recovery_months) if recovery_months else 0,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "var_95": var_95,
        "var_99": var_99,
        "cvar_95": cvar_95,
        "cvar_99": cvar_99,
        "skewness": skew,
        "excess_kurtosis": kurt,
        "win_rate_monthly": win_rate,
        "best_month": best_month,
        "worst_month": worst_month,
        "n_months": n_months,
        "n_years": n_years,
    }


def _calc_recovery_periods(equity: pd.Series) -> list:
    """Calcula la duración (en meses) de cada período de recuperación tras un drawdown."""
    rolling_max = equity.cummax()
    in_drawdown = equity < rolling_max
    recovery_periods = []
    current = 0

    for val in in_drawdown:
        if val:
            current += 1
        else:
            if current > 0:
                recovery_periods.append(current)
            current = 0

    return recovery_periods


def _empty_metrics() -> Dict[str, Any]:
    """Retorna métricas vacías cuando no hay datos suficientes."""
    return {k: 0.0 for k in [
        "total_return", "cagr", "max_drawdown", "months_underwater",
        "max_recovery_months", "sharpe_ratio", "sortino_ratio", "calmar_ratio",
        "var_95", "var_99", "cvar_95", "cvar_99", "skewness", "excess_kurtosis",
        "win_rate_monthly", "best_month", "worst_month", "n_months", "n_years"
    ]}


def format_metrics_table(metrics: dict, leverage_label: str = "") -> pd.DataFrame:
    """
    Formatea las métricas en un DataFrame legible para mostrar.
    
    Args:
        metrics: Output de calculate_all_metrics()
        leverage_label: Etiqueta de nivel de apalancamiento
        
    Returns:
        DataFrame con columnas [Métrica, Valor]
    """
    rows = [
        ("Retorno Total", f"{metrics['total_return']:.2%}"),
        ("CAGR", f"{metrics['cagr']:.2%}"),
        ("Máx. Drawdown", f"{metrics['max_drawdown']:.2%}"),
        ("Meses bajo agua", f"{metrics['months_underwater']}"),
        ("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}"),
        ("Sortino Ratio", f"{metrics['sortino_ratio']:.2f}"),
        ("Calmar Ratio", f"{metrics['calmar_ratio']:.2f}"),
        ("VaR 95% (mensual)", f"{metrics['var_95']:.2%}"),
        ("CVaR 95% (mensual)", f"{metrics['cvar_95']:.2%}"),
        ("Skewness", f"{metrics['skewness']:.2f}"),
        ("Kurtosis", f"{metrics['excess_kurtosis']:.2f}"),
        ("Win Rate mensual", f"{metrics['win_rate_monthly']:.1%}"),
        ("Mejor mes", f"{metrics['best_month']:.2%}"),
        ("Peor mes", f"{metrics['worst_month']:.2%}"),
        ("Años simulados", f"{metrics['n_years']:.1f}"),
    ]
    df = pd.DataFrame(rows, columns=["Métrica", leverage_label or "Valor"])
    return df
