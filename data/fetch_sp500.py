"""
fetch_sp500.py — Descarga y cachea datos históricos del S&P 500 y tasas de interés.

No requiere FRED API Key: usa yfinance para ^GSPC y ^IRX (T-bill 13 semanas) 
como proxy de la tasa libre de riesgo / coste de financiación.

Uso:
    python data/fetch_sp500.py
    from data.fetch_sp500 import get_sp500_data
"""

import os
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime
import pandas_datareader.data as web

# Ruta del CSV cacheado
DATA_DIR = Path(__file__).parent
CACHE_FILE = DATA_DIR / "sp500_monthly.csv"

# Crashes históricos conocidos (para etiquetado)
HISTORICAL_CRASHES = {
    "Great Depression": ("1929-09", "1932-06", -86.2),
    "Black Monday": ("1987-08", "1987-12", -33.5),
    "Dot-com Bubble": ("2000-03", "2002-10", -49.1),
    "GFC 2008": ("2007-10", "2009-03", -56.8),
    "COVID Crash": ("2020-02", "2020-03", -33.9),
    "Fed Rate Hikes": ("2022-01", "2022-10", -25.4),
}

def fetch_fresh_data(start: str = "1871-01-01", end: str = None) -> pd.DataFrame:
    """
    Descarga datos mensuales del S&P 500 históricos desde la base de datos oficial 
    de Robert Shiller (Universidad de Yale) que incluye Dividendos para calcular el Total Return.
    
    Returns:
        DataFrame con columnas: Date, Close, Monthly_Return, Drawdown_ATH,
        Volatility_12m, Interest_Rate, Crash_Label
    """
    print(f"📥 Descargando S&P 500 Total Return desde Robert Shiller (Yale)...")
    url = 'http://www.econ.yale.edu/~shiller/data/ie_data.xls'
    
    try:
        df_shiller = pd.read_excel(url, sheet_name='Data', skiprows=7)
        # Limpiar basuras al final de la hoja
        df_shiller = df_shiller.dropna(subset=['Date'])
        # Seleccionamos columnas: Date, P (Price), D (Dividend), Rate GS10, CPI
        df = df_shiller[['Date', 'P', 'D', 'Rate GS10', 'CPI']].copy()
        
        # Limpiar datos no numéricos
        df['P'] = pd.to_numeric(df['P'], errors='coerce')
        df['D'] = pd.to_numeric(df['D'], errors='coerce')
        df['Rate GS10'] = pd.to_numeric(df['Rate GS10'], errors='coerce')
        df['CPI'] = pd.to_numeric(df['CPI'], errors='coerce')
        df = df.dropna(subset=['P']) # Eliminamos filas sin precio
        
        # Parseo especial de fechas de Shiller (Formato YYYY.MM -> 1871.01)
        def parse_shiller_date(date_float):
            if pd.isna(date_float): return None
            date_str = str(date_float)
            year, month = date_str.split('.')
            if len(month) == 1:
                month = month + '0'
            return pd.to_datetime(f'{year}-{month}-01')
            
        df['Date'] = df['Date'].apply(parse_shiller_date)
        
        # Configurar Tasa de Interés
        df['Interest_Rate'] = df['Rate GS10'] / 100
        df['Interest_Rate'] = df['Interest_Rate'].ffill().fillna(0.04) # 4% default si falta
        
        # Computar TOTAL RETURN
        # 1. Rendimiento del Precio
        df['Price_Return'] = df['P'].pct_change()
        # 2. Rendimiento del Dividendo (Anualizado en base a 12 meses, distribuido mensual)
        df['Dividend_Yield_Monthly'] = (df['D'] / 12) / df['P'].shift(1)
        # 3. Retorno Total Mensual (Shiller History)
        df['Monthly_Return'] = df['Price_Return'] + df['Dividend_Yield_Monthly']
        df = df[['Date', 'P', 'D', 'Monthly_Return', 'Interest_Rate', 'CPI']].copy()
        
        # --- NUEVO: EMPALMAR CON YAHOO FINANCE HASTA HOY ---
        last_shiller_date = df['Date'].max()
        print(f"   Última fecha Shiller: {last_shiller_date.strftime('%Y-%m')}. Buscando cola reciente en Yahoo Finance...")
        
        try:
            # Pedimos desde 1 mes ANTES del final de shiller para poder calcular pct_change correctamente
            start_yf = (last_shiller_date - pd.DateOffset(months=1)).strftime('%Y-%m-%d')
            yf_data = yf.download(['^SP500TR', '^TNX'], start=start_yf, interval='1mo', progress=False)
            
            if not yf_data.empty and '^SP500TR' in yf_data['Close']:
                closes = yf_data['Close']
                sp500tr = closes['^SP500TR'].dropna()
                
                # Manejar TNX (interés) que a veces falla o falta en YF
                if '^TNX' in closes:
                    irx = closes['^TNX'].ffill().fillna(4.0)
                else:
                    irx = pd.Series(4.0, index=sp500tr.index)
                
                # Construir DataFrame de YF
                df_yf = pd.DataFrame({'Date': sp500tr.index})
                # Limpiar la fecha de yfinance tz-aware al primer dia del mes tz-naive
                df_yf['Date'] = df_yf['Date'].dt.tz_localize(None).dt.floor('D')
                df_yf['Date'] = df_yf['Date'].apply(lambda d: d.replace(day=1))
                
                df_yf['Monthly_Return'] = sp500tr.pct_change().values
                df_yf['Interest_Rate'] = irx.values / 100.0
                
                # Filtrar solo meses estrictamente posteriores al fin de Shiller
                df_yf = df_yf[df_yf['Date'] > last_shiller_date].copy()
                
                if not df_yf.empty:
                    print(f"   Encontrados {len(df_yf)} meses nuevos en YFinance. Fusionando...")
                    # Añadir P, D y CPI vacíos para que las columnas coincidan
                    df_yf['P'] = np.nan
                    df_yf['D'] = np.nan
                    df_yf['CPI'] = np.nan
                    df = pd.concat([df, df_yf], ignore_index=True)
        except Exception as e:
            print(f"⚠️ Aviso: Falló la descarga de YFinance para la cola reciente. Usando solo Shiller. Error: {e}")
            
        # --- CÁLCULOS GLOBALES SOBRE LA SERIE FUSIONADA ---
        df = df.sort_values('Date').reset_index(drop=True)
        
        # --- OBTENER INFLACION (CPI) ---
        print("   📥 Fusionando CPI Histórico y calculando Inflación...")
        try:
            # Descargamos CPIAUCNS desde 1913 nativamente leyendo el CSV público de FRED
            cpi_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS"
            cpi_df = pd.read_csv(cpi_url, parse_dates=['DATE'])
            cpi_df = cpi_df.rename(columns={'DATE': 'Date', 'CPIAUCNS': 'CPIAUCNS_raw'})
            cpi_df['CPIAUCNS'] = pd.to_numeric(cpi_df['CPIAUCNS_raw'], errors='coerce')
            
            cpi_df = cpi_df.set_index('Date').resample('MS').first() # Alinear al inicio de mes
            cpi_df.index.name = 'Date'
            cpi_df = cpi_df.reset_index()
            
            df = pd.merge(df, cpi_df[['Date', 'CPIAUCNS']], on='Date', how='left')
            
            # Combinar el CPI de Shiller con el FRED (para la cola final)
            df['CPI_Combined'] = df['CPI'].fillna(df['CPIAUCNS'])
            df['CPI_Combined'] = df['CPI_Combined'].ffill()
            
            df['Inflation_Rate'] = df['CPI_Combined'].pct_change(12)
            
            # Sustituir missing iniciales historicos (los primeros 12 meses antes del pct_change) 
            # extrapolando la media histórica de inflación
            media_inflacion = df['Inflation_Rate'].mean()
            df['Inflation_Rate'] = df['Inflation_Rate'].fillna(media_inflacion)
            
        except Exception as e:
            print(f"   ⚠️ Aviso: Falló la descarga de FRED. Usando solo datos CPI de Shiller. Error: {e}")
            df['CPI'] = df['CPI'].ffill()
            df['Inflation_Rate'] = df['CPI'].pct_change(12)
            media_inflacion = df['Inflation_Rate'].mean()
            df['Inflation_Rate'] = df['Inflation_Rate'].fillna(media_inflacion)
        
        # Generar "Close" sintético que refleje el crecimiento del Capital con el Total Return
        cumulative = (1 + df['Monthly_Return'].fillna(0)).cumprod()
        df['Close'] = 100 * cumulative
        
        # Filtrar por fecha de inicio solicitada (ej. 1927)
        df = df[df['Date'] >= pd.to_datetime(start)].copy()
        df.reset_index(drop=True, inplace=True)
        
        # Drawdown desde ATH (All-Time High Total Return)
        rolling_max = df["Close"].cummax()
        df["Drawdown_ATH"] = (df["Close"] - rolling_max) / rolling_max

        # Volatilidad rolling 12 meses (anualizada)
        df["Volatility_12m"] = df["Monthly_Return"].rolling(12).std() * np.sqrt(12)

        # Etiquetar crashes
        df["Crash_Label"] = ""
        for crash_name, (start_p, end_p, _) in HISTORICAL_CRASHES.items():
            mask = (df['Date'] >= pd.to_datetime(start_p)) & (df['Date'] <= pd.to_datetime(end_p))
            df.loc[mask, "Crash_Label"] = crash_name

        # Validaciones de integridad
        df.dropna(subset=["Close"], inplace=True)
        return df[['Date', 'Close', 'Monthly_Return', 'Drawdown_ATH', 'Volatility_12m', 'Interest_Rate', 'Crash_Label', 'Inflation_Rate']]
        
    except Exception as e:
        print(f"⚠️ Error colosal procesando datos de Shiller: {e}")
        raise e


from datetime import datetime
def get_sp500_data(force_refresh: bool = False) -> pd.DataFrame:
    """
    Retorna datos cacheados del S&P 500. Descarga si no existen o force_refresh=True.
    Además, verifica inteligentemente si el mes actual es superior al de la caché para actualizar.

    Args:
        force_refresh: Si True, ignora el cache y vuelve a descargar.

    Returns:
        DataFrame mensuales con toda la historia disponible.
    """
    if not force_refresh and CACHE_FILE.exists():
        df = pd.read_csv(CACHE_FILE, parse_dates=["Date"])
        
        last_date = df['Date'].max()
        today = datetime.today()
        
        # Si la caché tiene datos pre-mes actual, bajamos para ver si hay una nueva vela
        if last_date.year < today.year or (last_date.year == today.year and last_date.month < today.month):
            print(f"🔄 Caché antigua ({last_date.strftime('%Y-%m')}). Buscando nuevo mes de Yahoo Finance...")
            try:
                new_df = fetch_fresh_data()
                new_df.to_csv(CACHE_FILE, index=False)
                print(f"✅ Datos actualizados y guardados en {CACHE_FILE} ({len(new_df)} filas)")
                return new_df
            except Exception as e:
                print(f"⚠️ Falló actualización automática, usando caché actual. Error: {e}")
                return df
                
        print(f"✅ Cargando datos desde cache (actualizados): {CACHE_FILE}")
        return df

    print(f"📥 Forzando descarga limpia de toda la historia...")
    df = fetch_fresh_data()
    df.to_csv(CACHE_FILE, index=False)
    print(f"✅ Datos guardados en {CACHE_FILE} ({len(df)} filas)")
    return df


def get_crash_periods() -> dict:
    """Retorna el diccionario de crashes históricos con sus períodos y caídas."""
    return HISTORICAL_CRASHES


if __name__ == "__main__":
    df = get_sp500_data(force_refresh=True)
    print(f"\n📊 Resumen de datos:")
    print(f"   Período: {df['Date'].min().strftime('%Y-%m')} → {df['Date'].max().strftime('%Y-%m')}")
    print(f"   Meses totales: {len(df)}")
    print(f"   Precio actual: ${df['Close'].iloc[-1]:,.2f}")
    print(f"   Tasa interés media: {df['Interest_Rate'].mean():.2%}")
    print(f"\n{df.tail()}")
