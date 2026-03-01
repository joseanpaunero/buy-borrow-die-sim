"""
export.py — Configuración de estilos y exportación de gráficos orientada a YouTube.

Establece una paleta de colores premium (tema dark) y funciones de exportación 
a PNG/SVG de alta resolución para usar en contenido en video.
"""

import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path

# Paleta YouTube Premium Dark
COLORS = {
    "bg_main": "#121212",        # Fondo oscuro puro
    "bg_paper": "#1E1E2E",       # Fondo de cajas/paneles
    "text_primary": "#FFFFFF",   # Texto principal
    "text_secondary": "#B3B3B7", # Texto secundario (ejes, grid)
    "accent_green": "#00D084",   # Ganancias / Supervivencia
    "accent_red": "#FF4757",     # Pérdidas / Margin Call / Crashes
    "accent_blue": "#2F86EB",    # Información neutra / Equity Line
    "accent_yellow": "#FFC107",  # Alertas
    "accent_gray": "#3E3E4E",    # Elementos inactivos / Colateral
}

# Configurar el template global de Plotly
def setup_plotly_theme():
    """Configura el tema oscuro personalizado para Plotly."""
    custom_template = go.layout.Template(
        layout=go.Layout(
            plot_bgcolor=COLORS["bg_main"],
            paper_bgcolor=COLORS["bg_main"],
            font=dict(
                family="Inter, Roboto, sans-serif",
                color=COLORS["text_primary"],
                size=14
            ),
            title=dict(
                font=dict(size=24, color=COLORS["text_primary"]),
                x=0.05,
                xanchor="left"
            ),
            xaxis=dict(
                gridcolor=COLORS["accent_gray"],
                linecolor=COLORS["accent_gray"],
                zerolinecolor=COLORS["accent_gray"],
                tickfont=dict(color=COLORS["text_secondary"]),
                title=dict(font=dict(color=COLORS["text_secondary"])),
                showgrid=False
            ),
            yaxis=dict(
                gridcolor=COLORS["accent_gray"],
                linecolor=COLORS["accent_gray"],
                zerolinecolor=COLORS["accent_gray"],
                tickfont=dict(color=COLORS["text_secondary"]),
                title=dict(font=dict(color=COLORS["text_secondary"])),
                gridwidth=0.5
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                font=dict(color=COLORS["text_secondary"]),
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=60, r=40, t=80, b=60)
        )
    )
    pio.templates["youtube_dark"] = custom_template
    pio.templates.default = "youtube_dark"

# Inicializar el tema al importar este módulo
setup_plotly_theme()


def export_figure(fig: go.Figure, filename: str, output_dir: str = "exports", resolution: str = "1080p"):
    """
    Exporta una figura de Plotly a imagen estática (PNG).
    Requiere el paquete `kaleido` instalado.
    
    Args:
        fig: Figura de Plotly.
        filename: Nombre del archivo de salida (ej. "grafico_1").
        output_dir: Directorio donde guardar.
        resolution: "1080p" (1920x1080) o "1440p" (2560x1440).
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Resoluciones estándar para YouTube
    sizes = {
        "1080p": {"width": 1920, "height": 1080, "scale": 2},
        "1440p": {"width": 2560, "height": 1440, "scale": 2},
    }
    size = sizes.get(resolution, sizes["1080p"])
    
    # Añadir marca de agua sutil
    fig_copy = go.Figure(fig)
    fig_copy.add_annotation(
        text="👉 Lombard Leverage Simulator",
        x=0.01, y=0.01,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(color=COLORS["text_secondary"], size=12, family="Inter"),
        xanchor="left", yanchor="bottom",
        opacity=0.5
    )
    
    filepath = Path(output_dir) / f"{filename}.png"
    
    print(f"🎬 Exportando {filepath} a resolución {size['width']}x{size['height']}...")
    try:
        fig_copy.write_image(
            str(filepath), 
            width=size["width"], 
            height=size["height"], 
            scale=size["scale"]
        )
        print("✅ Exportación exitosa.")
    except ValueError as e:
        print(f"❌ Error al exportar. ¿Está instalado 'kaleido'? Error: {e}")
        print("   -> pip install -U kaleido")
