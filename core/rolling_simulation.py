"""
rolling_simulation.py — Motor para ejecutar simulaciones rodantes (Rolling Backtests).
Evalúa la estrategia "Buy, Borrow, Die" iterando por todos los puntos de inicio históricos 
posibles para la duración de jubilación especificada, calculando la probabilidad empírica de éxito.
"""

import pandas as pd
from typing import Dict, List, Tuple
from core.simulation import SimulationConfig, run_simulation
from tqdm import tqdm
import copy
from joblib import Parallel, delayed

def run_rolling_simulations(base_df: pd.DataFrame, config: SimulationConfig) -> Tuple[pd.DataFrame, Dict]:
    """
    Ejecuta simulaciones iterando sobre todos los meses iniciales válidos en la historia.
    
    Args:
        base_df: DataFrame con la historia completa del mercado (SP500, tasas, inflación).
        config: Configuración base de la estrategia. La fecha_inicio se ignorará y reescribirá en cada iteración.
    
    Returns:
        Un Tuple con (DataFrame con resultados reducidos por cada cohorte, Diccionario con estadísticas globales).
    """
    
    # Ordenar por fecha por seguridad
    df = base_df.sort_values(by="Date").reset_index(drop=True)
    
    meses_totales_simulacion = config.duracion_anios * 12
    total_meses_historia = len(df)
    
    # ¿Cuántos puntos de inicio posibles tenemos donde quepa una vida entera de simulación?
    # Para ser estrictos y no falsear las cohortes más recientes que no han terminado, 
    # solo simulamos las que pueden completar la duración (ej. 1980 -> 2005 para jubilación de 25 yrs)
    # A menos que permitamos simulaciones "abiertas", que es más lioso. Vamos a coger solo las que terminan, 
    # O las que terminan en margin call.
    # Dado que nos interesa saber TODO (incluso las cohortes no terminadas pueden haber quebrado antes), 
    # vamos a simular todos los meses, pero descartamos del éxito las que "están vivas pero sin completar".
    
    # Para hacerlo más riguroso en finanzas: solo backtest de cohortes enteras.
    max_start_index = total_meses_historia - meses_totales_simulacion
    
    if max_start_index <= 0:
        raise ValueError(f"Datos insuficientes para simular periodos de {config.duracion_anios} años rodantes. Reduce los años de jubilación o usa más historia.")
        
    resultados_cohortes = []
    
    for i in tqdm(range(max_start_index + 1), desc="Calculando periodos históricos..."):
        fecha_inicio_cohorte = df.iloc[i]["Date"]
        
        # Clonamos config para aislarla
        config_cohorte = copy.deepcopy(config)
        config_cohorte.fecha_inicio = fecha_inicio_cohorte.strftime("%Y-%m-%d")
        
        # Ejecutar sobre toda la vida desde esa fecha
        res = run_simulation(config_cohorte, df)
        
        # Analizar resultado final de la cohorte
        resultados_cohortes.append({
            "Start_Date": fecha_inicio_cohorte,
            "End_Date": res.timeline["date"].iloc[-1],
            "Wiped_Out": res.was_wiped_out,
            "Months_Survived": len(res.timeline),
            "Final_Equity": res.final_equity,
            "Taxes_Avoided": res.taxes_avoided_at_death,
            "High_Interest_Months": res.high_interest_months_count,
            "Total_Withdrawn": res.total_cash_withdrawn
        })
        
    # Crear dataframe summary
    res_df = pd.DataFrame(resultados_cohortes)
    
    # ----- ESTADÍSTICAS -----
    total_cohortes = len(res_df)
    ruinas = res_df["Wiped_Out"].sum()
    exitos = total_cohortes - ruinas
    prob_exito = exitos / total_cohortes if total_cohortes > 0 else 0.0
    
    # Solo calculamos equity y taxes mediados de las cohortes que tuvieron éxito
    df_exitos = res_df[~res_df["Wiped_Out"]]
    
    stats = {
        "total_simulations": total_cohortes,
        "success_rate": prob_exito,
        "wiped_out_probability": 1.0 - prob_exito,
        "median_final_equity": df_exitos["Final_Equity"].median() if not df_exitos.empty else 0.0,
        "median_taxes_avoided": df_exitos["Taxes_Avoided"].median() if not df_exitos.empty else 0.0,
        "worst_drawdown_period": res_df.loc[res_df["Wiped_Out"], "Start_Date"].min() if ruinas > 0 else None 
    }
    
    return res_df, stats

def _eval_wr_row(base_df: pd.DataFrame, base_config: SimulationConfig, wr: float, ltv_limits: List[float], max_start_index: int) -> dict:
    row_res = {"Withdrawal_Rate": wr}
    for ltv in ltv_limits:
        cfg = copy.deepcopy(base_config)
        cfg.withdrawal_rate_pct = float(wr)
        cfg.margin_call_threshold = float(ltv)
        
        exitos = 0
        for i in range(max_start_index + 1):
            cfg.fecha_inicio = base_df.iloc[i]["Date"].strftime("%Y-%m-%d")
            res = run_simulation(cfg, base_df)
            if not res.was_wiped_out:
                exitos += 1
                
        prob = exitos / (max_start_index + 1)
        row_res[f"{int(ltv*100)}% LTV"] = prob
    return row_res

def run_viability_matrix(base_df: pd.DataFrame, base_config: SimulationConfig, 
                         withdrawal_rates: List[float], ltv_limits: List[float],
                         progress_callback=None) -> pd.DataFrame:
    """
    Ejecuta simulaciones combinadas usando procesamiento paralelo.
    """
    df = base_df.sort_values(by="Date").reset_index(drop=True)
    meses_totales = base_config.duracion_anios * 12
    max_start_index = len(df) - meses_totales
    
    if max_start_index <= 0:
        return pd.DataFrame()
        
    # Ejecutamos en paralelo por cada "Withdrawal Rate" (cada WR es un Job que calcula todos sus LTVs)
    # joblib usa todos los núcleos disponibles (-1)
    results_matrix = Parallel(n_jobs=-1)(
        delayed(_eval_wr_row)(df, base_config, wr, ltv_limits, max_start_index)
        for wr in withdrawal_rates
    )
        
    return pd.DataFrame(results_matrix)
