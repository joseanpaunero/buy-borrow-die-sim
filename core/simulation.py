"""
simulation.py — Motor principal de simulación de apalancamiento lombardo (Buy Borrow Die).

Simula mes a mes la evolución de una cartera, donde el inversor pide préstamos 
para financiar sus gastos vitales sin vender acciones, evitando impuestos.

Uso:
    from core.simulation import SimulationConfig, run_simulation
"""

from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd
import numpy as np

@dataclass
class SimulationConfig:
    capital_inicial: float = 1_000_000.0        # Capital propio del inversor (€)
    withdrawal_rate_pct: float = 0.04           # Retiro anual (%)
    withdrawal_mode: str = "fixed_initial"      # "fixed_initial" o "dynamic_current"
    inflation_margin_pct: float = 0.0           # Margen +/- sobre inflación mensual 
    tasa_interes_anual: float = 0.035           # Coste anual del préstamo fijado
    fecha_inicio: str = "2000-01"               # Período de inicio (YYYY-MM)
    duracion_anios: int = 25                    # Años de simulación (Esperanza de vida - Edad actual)
    margin_call_threshold: float = 0.65         # LTV máximo permitido (ej 65%)
    modo_interes: str = "fijo"                  # "fijo" | "variable"
    high_interest_warning_threshold: float = 0.06 # Alerta si la tasa supera este umbral (ej 6%)
    amortizacion: str = "capitalizada"          # El interés se suma a la deuda (default en BBD)
    spread_interes_variable: float = 0.0        # Spread sobre la tasa base
    capital_gains_tax_pct: float = 0.21         # Impuesto a ganancias capital (ej. 21%)

@dataclass
class MonthlyRecord:
    """Registro mensual del estado de la simulación."""
    date: pd.Timestamp
    precio_sp500: float
    activos_totales: float       
    deuda: float                 
    equity: float                
    ltv_actual: float            
    retorno_mensual: float       
    intereses_pagados: float     
    retiro_mensual: float        
    tasa_interes_anualizada: float
    inflacion_acumulada: float   
    high_interest_flag: bool     
    margin_call: bool            
    fue_liquidado: bool          
    stl_activos: float           # Baseline: activos si hubieras vendido

@dataclass
class SimulationResult:
    """Resultado completo de una simulación Buy Borrow Die."""
    config: SimulationConfig
    timeline: pd.DataFrame
    total_cash_withdrawn: float
    final_equity: float
    final_stl_equity: float
    taxes_avoided_at_death: float
    high_interest_months_count: int
    margin_calls: List[pd.Timestamp] = field(default_factory=list)
    was_wiped_out: bool = False

def run_simulation(config: SimulationConfig, df: pd.DataFrame) -> SimulationResult:
    """
    Ejecuta la simulación de Buy, Borrow, Die.
    """
    df_period = df[df["Date"] >= pd.to_datetime(config.fecha_inicio)].copy().reset_index(drop=True)
    
    meses_totales = config.duracion_anios * 12
    if len(df_period) > meses_totales:
        df_period = df_period.iloc[:meses_totales]
        
    if len(df_period) < 2:
        raise ValueError(f"Período insuficiente desde {config.fecha_inicio}")

    activos = float(config.capital_inicial)
    deuda = 0.0
    unidades = activos / df_period.iloc[0]["Close"]

    # Sell-to-Live Baseline variables
    stl_activos = float(config.capital_inicial)
    stl_unidades = stl_activos / df_period.iloc[0]["Close"]
    stl_cost_basis = float(config.capital_inicial)
    
    retiro_anual_base = 0.0
    inflacion_acumulada = 1.0

    records = []
    margin_calls_dates = []
    total_withdrawn = 0.0
    high_int_count = 0
    was_wiped_out = False
    
    tasa_mensual_fija = config.tasa_interes_anual / 12.0

    for i, row in df_period.iterrows():
        precio = float(row["Close"])
        retorno = float(row["Monthly_Return"]) if i > 0 else 0.0
        inf_mensual = float(row.get("Inflation_Rate", 0.0))

        # 1. Configurar retiro base (anual)
        if config.withdrawal_mode == "fixed_initial":
            retiro_anual_base = config.capital_inicial * config.withdrawal_rate_pct
        else: # dynamic_current
            if i % 12 == 0:
                equity_actual = activos - deuda
                retiro_anual_base = equity_actual * config.withdrawal_rate_pct

        # 2. Ajuste por inflación anualmente
        if i > 0 and i % 12 == 0:
            inflacion_acumulada *= (1.0 + inf_mensual + config.inflation_margin_pct)

        retiro_mensual = (retiro_anual_base * inflacion_acumulada) / 12.0
        total_withdrawn += retiro_mensual

        # -----------------------------
        # ESTRATEGIA: BUY BORROW DIE
        # -----------------------------
        activos = unidades * precio
        deuda += retiro_mensual

        # Calcular tasa de interés de este mes
        if config.modo_interes == "variable" and "Interest_Rate" in row:
            tasa_mensual = (float(row["Interest_Rate"]) + config.spread_interes_variable) / 12.0
        else:
            tasa_mensual = tasa_mensual_fija

        high_interest_flag = (tasa_mensual * 12.0) > config.high_interest_warning_threshold
        if high_interest_flag:
            high_int_count += 1

        intereses = deuda * tasa_mensual
        if config.amortizacion == "capitalizada":
            deuda += intereses

        equity = activos - deuda
        ltv_actual = deuda / activos if activos > 0 else 1.0

        mc_triggered = False
        if equity <= 0 or ltv_actual > config.margin_call_threshold:
            was_wiped_out = True
            mc_triggered = True
            margin_calls_dates.append(row["Date"])

        # -----------------------------
        # ESTRATEGIA: SELL-TO-LIVE
        # -----------------------------
        stl_activos = stl_unidades * precio
        
        if stl_activos > 0:
            # Calcular % de ganancia que tiene el portfolio actualmente
            ganancia_pct = (stl_activos - stl_cost_basis) / stl_activos if stl_activos > stl_cost_basis else 0.0
            if ganancia_pct < 0: ganancia_pct = 0.0
            
            # Para sacar `retiro_mensual` neto libres de impuestos, hay que vender `retiro_bruto`.
            denom = 1.0 - (ganancia_pct * config.capital_gains_tax_pct)
            if denom <= 0.01: denom = 0.01 # Evitar division por cero (imposible con tax < 100%)
            retiro_bruto_stl = retiro_mensual / denom
            
            stl_activos -= retiro_bruto_stl
            if stl_activos < 0: 
                stl_activos = 0.0
            stl_unidades = stl_activos / precio
            
            # Reducir cost basis en la misma proporción que se ha vendido
            if stl_activos > 0:
                prop_vendida = retiro_bruto_stl / (stl_activos + retiro_bruto_stl)
                stl_cost_basis -= stl_cost_basis * prop_vendida
            else:
                stl_cost_basis = 0.0
        else:
            stl_activos = 0.0

        records.append(MonthlyRecord(
            date=row["Date"], precio_sp500=precio, activos_totales=activos,
            deuda=deuda, equity=max(equity, 0), ltv_actual=ltv_actual,
            retorno_mensual=retorno, intereses_pagados=intereses, 
            retiro_mensual=retiro_mensual, tasa_interes_anualizada=(tasa_mensual * 12.0), 
            inflacion_acumulada=inflacion_acumulada,
            high_interest_flag=high_interest_flag, margin_call=mc_triggered,
            fue_liquidado=was_wiped_out, stl_activos=stl_activos
        ))

        if was_wiped_out:
            break

    timeline = pd.DataFrame([r.__dict__ for r in records])
    
    final_equity = timeline["equity"].iloc[-1] if not was_wiped_out and not timeline.empty else 0.0
    final_stl_equity = timeline["stl_activos"].iloc[-1] if not timeline.empty else 0.0
    
    # "Plusvalía del muerto" = Die Phase = final_equity vs final_stl_equity
    # Inherit assets -> basis step-up -> 0 CGT. 
    taxes_avoided = max(final_equity - final_stl_equity, 0.0)

    return SimulationResult(
        config=config,
        timeline=timeline,
        total_cash_withdrawn=total_withdrawn,
        final_equity=final_equity,
        final_stl_equity=final_stl_equity,
        taxes_avoided_at_death=taxes_avoided,
        high_interest_months_count=high_int_count,
        margin_calls=margin_calls_dates,
        was_wiped_out=was_wiped_out
    )
