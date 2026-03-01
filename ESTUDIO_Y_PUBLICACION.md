# Estudio Exhaustivo: Simulador Buy, Borrow, Die

Este documento presenta una auditoría analítica y técnica del ecosistema de scripts para el simulador **Buy, Borrow, Die (BBD)**, junto con una guía paso a paso para publicarlo de manera gratuita en la web.

---

## 1. Análisis de los Scripts y Estructura del Proyecto

El proyecto está diseñado de forma modular, separando la adquisición de datos, el motor lógico de simulación, la generación de métricas matemáticas y la interfaz visual. 

A continuación, se detalla la función de los scripts confirmados como operativos y fundamentales para la aplicación:

### Motor y Lógica Core (`/core/`)
- **`simulation.py`**: Es el **corazón del proyecto**. Contiene la clase `SimulationConfig` que define los parámetros del préstamo (LTV, tasa de interés, inflación, margen libre de impuestos) y la función `run_simulation()` que itera mes a mes la historia del mercado cruzando el crecimiento de los activos frente a la deuda acumulada. Determina si el inversor sobrevive o sufre un *Margin Call*.
- **`rolling_simulation.py`**: Motor de *backtesting*. Utiliza procesamiento en paralelo (`joblib`) para iterar simulaciones sobre todos los puntos de inicio históricos posibles en la historia americana. Genera las matrices de éxito que validan empíricamente el modelo o advierten sobre el riesgo de ruina.
- **`metrics.py`**: Módulo matemático analítico. Extrae la línea temporal generada y computa ratios profesionales como *Sharpe*, *Sortino*, *Calmar*, Máximo Drawdown y Tasa de Éxito (*Win Rate*). 

### Visualización y Dashboard (`/charts/` y Raíz)
- **`app.py`**: El dashboard interactivo de Streamlit. Une todos los módulos, captura los inputs del usuario desde la interfaz web (edad, capital, margen LTV) y repinta los gráficos en tiempo real.
- **`chart_generator.py`**: Emplea `plotly.graph_objects` para generar figuras interactivas. Traza mapas de calor (heatmap) para el test de estrés global, gráficas subacuáticas para drawdowns interconectando el capital apalancado frente a la estrategia de venta pura ("Sell-To-Live").
- **`export.py`**: Define una paleta de colores consistente "Premium Dark" y controla una función genérica que permite exportar capturas de estos gráficos en alta resolución.

### Datos Históricos (`/data/`)
- **`fetch_sp500.py`**: Un oráculo de datos sofisticado. Descarga e hibrida los datos del **S&P 500 Total Return** de la Universidad de Yale (Robert Shiller) desde 1871 con los datos modernos y actuales de **Yahoo Finance** y métricas de IPC de la base oficial oficial (FRED). Cachea la información en un CSV local (`sp500_monthly.csv`) para que el simulador funcione súper rápido.

> **Scripts Eliminados (Limpieza):**  
> Durante el estudio se auditaron y **borraron** los scripts `export_youtube.py` y `report_generator.py` debido a que presentaban código obsoleto que hacía referencia a variables antiguas (`leverage_ratio`, `fecha_fin`) incompatibles con la arquitectura moderna centrada en "años de jubilación" y tasas de retiro mensual de la configuración actual.

---

## 2. Cómo Publicar el Estudio y el Simulador Online GRATIS

Actualmente tienes un simulador potentísimo y visual desarrollado en **Streamlit**. La vía más profesional, estable y 100% gratuita para publicar tanto tu app como tu estudio consiste en usar **GitHub** y **Streamlit Community Cloud**.

Sigue estos 3 simples pasos:

### Paso 1: Sube el proyecto a GitHub
1. Crea una cuenta gratuita en [GitHub.com](https://github.com/).
2. Instala la herramienta "Git" en tu ordenador si no la tienes, o usa GitHub Desktop.
3. Crea un nuevo repositorio en GitHub llamado, por ejemplo, `buy-borrow-die-sim`.
4. Sube todos los archivos de tu carpeta `c:\Adirect\buy-borrow-die\` a ese repositorio (asegúrate de incluir el archivo `requirements.txt`, es muy importante).

### Paso 2: Despliega en Streamlit Community Cloud
1. Entra a [share.streamlit.io](https://share.streamlit.io/) e inicia sesión vinculando tu cuenta de GitHub de forma gratuita.
2. Haz clic en **"New app"** (Nueva aplicación).
3. Selecciona tu repositorio recién creado (`buy-borrow-die-sim`), asegúrate de que la rama (*branch*) es `main` (o `master`), y en **Main file path** (Ruta del archivo principal) escribe `app.py`.
4. Haz clic en **Deploy!** (Desplegar).

En un un minuto, Streamlit instalará las librerías de `requirements.txt` y te proporcionará una URL pública (ej. `https://buy-borrow-die.streamlit.app`) que puedes enviar a cualquier inversor en el mundo. ¡Ya estará online!

### Paso 3: Publica también este mismo Estudio
Dado que el formato del panel admite texto Markdown de manera nativa, puedes:
1. Copiar y pegar el texto de este mismo apartado (Estudio Exhaustivo) y añadirlo directamente creando una nueva pestaña (tab) dentro de `app.py`.  
   Ejemplo conceptual para tu código actual:  
   ```python
   # Al final o principio de los tabs en app.py
   st.markdown("---")
   st.markdown("## Estudio del Proyecto")
   with open("ESTUDIO_Y_PUBLICACION.md", "r", encoding="utf-8") as f:
       st.markdown(f.read())
   ```
2. **Opcional (Blog Gratuito):** Si prefieres que este estudio sea un artículo escrito estándar, puedes copiar el contenido Markdown a herramientas para blogs gratuitos como **Medium.com**, **Hashnode** o activar **GitHub Pages** en tu mismo repositorio para convertir este documento Markdown en una web clásica.
