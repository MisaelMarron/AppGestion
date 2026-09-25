"""
generar_pdf_guia.py
===================
Genera un documento PDF formal, profesional y de alta calidad técnica con la
Guía Completa de Sustentación y Exposición de OperaStock.
"""
import os, sys
from pathlib import Path

# ── Forzar salida UTF-8 en Windows ──
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_PATH = BASE_DIR / "Guia_Sustentacion_OperaStock.pdf"

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "OperaStock — Guía de Sustentación Técnica")
            self.drawRightString(612 - 54, 750, "Machine Learning & Supply Chain")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 744, 612 - 54, 744)

        # Footer
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 45, 612 - 54, 45)
        self.drawString(54, 32, "Confidencial / Uso Académico — OperaStock 2026")
        self.drawRightString(612 - 54, 32, f"Página {self._pageNumber} de {page_count}")
        self.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#0F172A")
    accent_blue = colors.HexColor("#1D4ED8")
    dark_gray = colors.HexColor("#334155")

    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#475569"),
        spaceAfter=14,
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=accent_blue,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=primary_color,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=dark_gray,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.8,
        leading=12.5,
        textColor=dark_gray,
        leftIndent=12,
        spaceAfter=3,
    )

    formula_style = ParagraphStyle(
        'FormulaText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=2,
        spaceAfter=4,
    )

    box_style = ParagraphStyle(
        'BoxText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
    )

    story = []

    # ── HEADER & TITLE ──
    story.append(Paragraph("📘 GUÍA DE SUSTENTACIÓN TÉCNICA: OPERASTOCK", title_style))
    story.append(Paragraph("<b>Sistema de Gestión de Inventarios, Producción y Aprovisionamiento Predictivo</b><br/>Arquitectura de Modelos de Machine Learning, Series Temporales y Logística Operativa", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=accent_blue, spaceBefore=0, spaceAfter=12))

    # ── 1. RESUMEN EJECUTIVO ──
    story.append(Paragraph("1. Resumen Ejecutivo y Problema de Negocio", h1_style))
    story.append(Paragraph(
        "En la industria de manufactura de alimentos (galletas, panadería), la gestión de inventario enfrenta dos problemas críticos: "
        "<b>(a) Quiebre de Stock (Stockout):</b> la falta de una sola materia prima paraliza hornos y líneas de empaque; "
        "<b>(b) Sobre-stock:</b> el exceso de compras inmoviliza capital de trabajo y eleva el riesgo de merma por caducidad.",
        body_style
    ))
    story.append(Paragraph(
        "<b>OperaStock</b> resuelve esta disyuntiva integrando la producción en tiempo real con un <b>motor predictivo multimodelo</b> que evalúa 4 algoritmos en paralelo, proyecta la demanda a 60 días y genera sugerencias automáticas de compra ajustadas a las restricciones de los proveedores.",
        body_style
    ))

    # ── 2. LOS 4 MODELOS PREDICTIVOS: FUNDAMENTO TÉCNICO ──
    story.append(Spacer(1, 4))
    story.append(Paragraph("2. Los 4 Modelos Predictivos: Fundamento Técnico", h1_style))
    story.append(Paragraph(
        "El sistema divide el historial de consumo diario cronológicamente (<b>80% Entrenamiento / 20% Validación Holdout</b>). "
        "Cada algoritmo es evaluado contra datos reales no vistos y el sistema selecciona automáticamente al que minimice el error cuadrático medio (<b>RMSE</b>).",
        body_style
    ))

    models_data = [
        [
            Paragraph("<b>Modelo / Algoritmo</b>", body_style),
            Paragraph("<b>Fundamento y Ecuación Clave</b>", body_style),
            Paragraph("<b>Ventaja Operativa</b>", body_style),
        ],
        [
            Paragraph("<b>1. Promedio Móvil</b><br/>(Baseline)", body_style),
            Paragraph("Media aritmética de ventana deslizante de <i>k=7</i> días:<br/><b>ŷ<sub>t+1</sub> = (1/k) ∑ y<sub>t-i</sub></b>", body_style),
            Paragraph("Línea base ultra rápida; sirve de contraste para validar que los modelos avanzados agreguen valor real.", body_style),
        ],
        [
            Paragraph("<b>2. Holt-Winters</b><br/>(Suavizado Exp. Triple)", body_style),
            Paragraph("Descompone la demanda en Nivel (L<sub>t</sub>), Tendencia (b<sub>t</sub>) y Estacionalidad semanal (S<sub>t</sub>):<br/><b>ŷ<sub>t+h</sub> = L<sub>t</sub> + h·b<sub>t</sub> + S<sub>t+h-m</sub></b> (m=7)", body_style),
            Paragraph("Captura patrones de consumo semanales (ej. picos de producción viernes/sábado) y tendencias de crecimiento.", body_style),
        ],
        [
            Paragraph("<b>3. SARIMA</b><br/>(Seasonal ARIMA)", body_style),
            Paragraph("Modelo estocástico autoregresivo integrado: <b>(1,1,1)×(1,0,1)<sub>7</sub></b>.<br/>Modela autocorrelación temporal y estacionalidad de 7 días con diferenciación.", body_style),
            Paragraph("Altamente robusto para variaciones cíclicas de demanda continua y correlaciones seriales.", body_style),
        ],
        [
            Paragraph("<b>4. Random Forest</b><br/>(Machine Learning)", body_style),
            Paragraph("Ensamble de 100 árboles de decisión con <i>Feature Engineering</i>:<br/>• Lags (1, 7, 14, 30 días)<br/>• Promedios y desviación rodante<br/>• Factores calendáricos (día, mes, semana)", body_style),
            Paragraph("Detecta relaciones no lineales complejas, interacciones entre días del mes y picos sin asumir normalidad.", body_style),
        ],
    ]

    t_models = Table(models_data, colWidths=[120, 230, 154])
    t_models.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('TEXTCOLOR', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_models)

    # ── 3. EXPLICACIÓN EN PALABRAS SENCILLAS (CÓMO PIENSA CADA MODELO) ──
    story.append(Spacer(1, 8))
    story.append(Paragraph("3. ¿Cómo Piensa Cada Modelo y Qué Datos Toma? (Explicación Intuitiva)", h1_style))
    story.append(Paragraph(
        "Para responder con claridad y seguridad ante preguntas conceptuales, así razona cada algoritmo en palabras directas:",
        body_style
    ))

    intuitive_data = [
        [
            Paragraph("<b>Algoritmo</b>", body_style),
            Paragraph("<b>¿Qué datos mira exactamente?</b>", body_style),
            Paragraph("<b>Lógica de cálculo (Cómo piensa)</b>", body_style),
            Paragraph("<b>¿Por qué y cuándo gana?</b>", body_style),
        ],
        [
            Paragraph("<b>1. Promedio Móvil</b>", body_style),
            Paragraph("Únicamente los últimos <b>7 días</b> de consumo.", body_style),
            Paragraph("<i>«Suma lo consumido en los últimos 7 días y lo divide entre 7. Asume que todos los días siguientes se usará esa misma cantidad fija.»</i>", body_style),
            Paragraph("Gana en insumos de <b>consumo plano y constante</b> que casi no varían (ej. Sal o colorantes estándar).", body_style),
        ],
        [
            Paragraph("<b>2. Holt-Winters</b>", body_style),
            Paragraph("Todo el historial, dando <b>más peso a las últimas semanas</b> y agrupando en ciclos semanales de 7 días (lun a dom).", body_style),
            Paragraph("<i>«Descompone: Nivel (promedio reciente) + Tendencia (si el negocio crece o baja) + Factor del día (ej. viernes y sábado +40% de demanda, lunes -20%).»</i>", body_style),
            Paragraph("Gana en insumos con <b>picos de fin de semana muy marcados</b> y ritmos semanales claros (ej. Azúcar, Cacao, Mantequilla).", body_style),
        ],
        [
            Paragraph("<b>3. SARIMA</b>", body_style),
            Paragraph("Secuencia histórica completa buscando <b>ondas y autocorrelación</b> (cómo hoy depende de ayer y de la semana pasada).", body_style),
            Paragraph("<i>«Calcula la 'memoria' del consumo y corrige sus errores pasados: si subestimó un miércoles previo, ajusta hacia arriba el siguiente miércoles.»</i>", body_style),
            Paragraph("Gana en insumos de <b>alto volumen y consumo ondulante</b> continuo (ej. Harina de Trigo, Leche en polvo, Miel).", body_style),
        ],
        [
            Paragraph("<b>4. Random Forest</b>", body_style),
            Paragraph("Transforma fechas en pistas:<br/>• Lags: 1, 7, 14, 30 días<br/>• Promedios rodantes<br/>• Día de semana, quincena y mes", body_style),
            Paragraph("<i>«Crea 100 árboles de decisión independientes que hacen preguntas lógicas cruzadas y promedian sus 100 respuestas para dar la cifra final.»</i>", body_style),
            Paragraph("Gana en insumos con <b>comportamientos complejos y no lineales</b> (picos por quincenas o patrones que no siguen fórmulas simples).", body_style),
        ],
    ]

    t_intuitive = Table(intuitive_data, colWidths=[90, 130, 154, 130])
    t_intuitive.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
        ('TEXTCOLOR', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BFDBFE")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_intuitive)

    # ── 4. MÉTRICAS DE VALIDACIÓN ──
    story.append(Spacer(1, 6))
    story.append(Paragraph("4. Métricas de Precisión y Selección Automática", h1_style))
    
    metrics_data = [
        [
            Paragraph("<b>Métrica</b>", body_style),
            Paragraph("<b>Fórmula Matemática</b>", body_style),
            Paragraph("<b>Interpretación en Planta</b>", body_style),
        ],
        [
            Paragraph("<b>MAE</b><br/>(Error Medio Absoluto)", body_style),
            Paragraph("MAE = (1/n) ∑ |y<sub>t</sub> − ŷ<sub>t</sub>|", formula_style),
            Paragraph("Magnitud promedio en kilos en que se equivoca el pronóstico respecto a la realidad.", body_style),
        ],
        [
            Paragraph("<b>RMSE</b><br/>(Raíz Error Cuadrático)", body_style),
            Paragraph("RMSE = √[ (1/n) ∑ (y<sub>t</sub> − ŷ<sub>t</sub>)² ]", formula_style),
            Paragraph("Penaliza desviaciones severas. <b>Es el criterio principal de selección automática</b>.", body_style),
        ],
        [
            Paragraph("<b>MAPE</b><br/>(Error Porcentual)", body_style),
            Paragraph("MAPE = (100%/n) ∑ |(y<sub>t</sub> − ŷ<sub>t</sub>) / y<sub>t</sub>|", formula_style),
            Paragraph("Porcentaje de error relativo al volumen total consumido.", body_style),
        ],
    ]
    t_metrics = Table(metrics_data, colWidths=[120, 200, 184])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_metrics)

    # ── 5. FÓRMULAS DE APROVISIONAMIENTO LOGÍSTICO ──
    story.append(Spacer(1, 6))
    story.append(Paragraph("5. Fórmulas de Cadena de Suministro y Gestión de Inventarios", h1_style))
    story.append(Paragraph("Con la demanda proyectada por el mejor modelo (d<sub>1</sub>, d<sub>2</sub>, ..., d<sub>60</sub>), el sistema calcula:", body_style))

    formulas_content = [
        Paragraph("<b>A. Stock de Seguridad (SS - Safety Stock):</b><br/>"
                  "<b>SS = Z · σ<sub>d</sub> · √(LT)</b><br/>"
                  "• <b>Z:</b> Coeficiente del nivel de servicio (Z ≈ 1.645 para 95% de confiabilidad).<br/>"
                  "• <b>σ<sub>d</sub>:</b> Desviación estándar del consumo diario histórico.<br/>"
                  "• <b>LT:</b> <i>Lead Time</i> o tiempo de entrega del proveedor en días hábiles.", bullet_style),
        Paragraph("<b>B. Punto de Reorden (ROP - Reorder Point):</b><br/>"
                  "<b>ROP = Demanda<sub>LT</sub> + SS = ( ∑<sub>t=1..LT</sub> ŷ<sub>t</sub> ) + ( Z · σ<sub>d</sub> · √(LT) )</b><br/>"
                  "Umbral de inventario: si el stock utilizable cae por debajo de este punto, se debe emitir una orden de compra.", bullet_style),
        Paragraph("<b>C. Lote Óptimo de Compra Sugerido (Q):</b><br/>"
                  "<b>Objetivo S = ( ∑<sub>t=1..LT+Cobertura</sub> ŷ<sub>t</sub> ) + SS</b><br/>"
                  "<b>Q<sub>bruto</sub> = max(0, S − [Stock Utilizable + Entradas en Tránsito])</b><br/>"
                  "<b>Q = ⌈ max(Q<sub>bruto</sub>, MOQ) / Múltiplo ⌉ · Múltiplo</b><br/>"
                  "Ajusta el pedido al <b>MOQ</b> (pedido mínimo) y a los <b>múltiplos de empaque</b> del proveedor (ej. sacos de 25 kg).", bullet_style)
    ]
    for fc in formulas_content:
        story.append(fc)

    # ── 6. FLUJO OPERATIVO ──
    story.append(Spacer(1, 6))
    story.append(Paragraph("6. Flujo Operativo Integral en OperaStock", h1_style))
    
    flow_data = [
        [Paragraph("<b>Etapa</b>", body_style), Paragraph("<b>Acción Operativa</b>", body_style), Paragraph("<b>Impacto en el Sistema / Base de Datos</b>", body_style)],
        [Paragraph("<b>1. Fórmulas / BOM</b>", body_style), Paragraph("Definición de receta por kg de producto.", body_style), Paragraph("DetalleProducto / FormulaProducto.", body_style)],
        [Paragraph("<b>2. Producción</b>", body_style), Paragraph("Ingreso de kilos bulk y unidades producidas.", body_style), Paragraph("Descuento atómico de stock (ConsumoMateriaPrima) y trazabilidad.", body_style)],
        [Paragraph("<b>3. Entrenamiento</b>", body_style), Paragraph("Entrenamiento periódico de los 4 modelos.", body_style), Paragraph("Entrenamiento / Artefactos .joblib con métricas MAE y RMSE.", body_style)],
        [Paragraph("<b>4. Pronóstico</b>", body_style), Paragraph("Generación de demanda a 60 días.", body_style), Paragraph("Pronostico con curva diaria para cada insumo.", body_style)],
        [Paragraph("<b>5. Compras</b>", body_style), Paragraph("Cálculo de ROP, SS y sugerencias de compra.", body_style), Paragraph("SugerenciaCompra (estado PENDIENTE) con proveedor óptimo.", body_style)],
        [Paragraph("<b>6. Recepción</b>", body_style), Paragraph("Aprobación y recepción de orden de compra.", body_style), Paragraph("OrdenCompra (EN TRÁNSITO → RECIBIDA), aumento de stock físico.", body_style)],
    ]
    t_flow = Table(flow_data, colWidths=[100, 200, 204])
    t_flow.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_flow)

    # ── 7. OPORTUNIDADES Y EXTENSIONES CON IA GENERATIVA ──
    story.append(Spacer(1, 6))
    story.append(Paragraph("7. Propuestas de Expansión e Integración de IA Generativa (LLMs)", h1_style))
    story.append(Paragraph("<b>A. Módulos Avanzados de Negocio:</b>", h2_style))
    story.append(Paragraph("• <b>FEFO (First Expired, First Out):</b> Gestión inteligente de lotes priorizando insumos cercanos a caducar.", bullet_style))
    story.append(Paragraph("• <b>Costeo Unitario en Tiempo Real (COGS):</b> Cálculo del costo exacto por galleta según el precio del lote utilizado.", bullet_style))
    story.append(Paragraph("• <b>Planificador Maestro (MPS):</b> Programación de horneado sujeta a capacidad máxima instalada de planta.", bullet_style))

    story.append(Paragraph("<b>B. Casos de Uso con IA Generativa (Gemini / GPT-4):</b>", h2_style))
    story.append(Paragraph("• <b>Copiloto de Aprovisionamiento:</b> Consultas en lenguaje natural (ej. <i>'¿Qué insumos se agotarán esta semana y cuál es el proveedor más económico?'</i>).", bullet_style))
    story.append(Paragraph("• <b>Agente de Compras Autónomo:</b> Generación y envío automatizado de correos y WhatsApp a proveedores con órdenes adjuntas.", bullet_style))
    story.append(Paragraph("• <b>Asistente de Reformulación (RAG):</b> Sugerencia de sustitutos de ingredientes ante quiebres de mercado manteniendo el rendimiento.", bullet_style))

    # ── 8. GUION DE EXPOSICIÓN ──
    story.append(Spacer(1, 6))
    story.append(Paragraph("8. Guion de Sustentación Rápida (3 Minutos)", h1_style))
    
    script_box = [
        [Paragraph(
            "<b>«Buenos días, profesor. Nuestro proyecto es OperaStock:</b><br/><br/>"
            "<b>1. El Problema:</b> En la industria de alimentos, quedarse sin insumos detiene la planta, pero comprar de más produce mermas por vencimiento.<br/>"
            "<b>2. Operación Real:</b> Registramos la producción con trazabilidad dual (kilos bulk y unidades). Al confirmar un lote, el sistema descuenta automáticamente los insumos según la fórmula (BOM).<br/>"
            "<b>3. Inteligencia Predictiva:</b> El sistema evalúa en paralelo <b>4 modelos:</b> <i>Promedio Móvil, Holt-Winters (estacionalidad semanal), SARIMA y Random Forest</i>. Sobre un conjunto de prueba cronológico del 20%, calcula el error <b>MAE y RMSE</b> y selecciona automáticamente el algoritmo más preciso para cada materia prima.<br/>"
            "<b>4. Compras Automatizadas:</b> Con la demanda proyectada a 60 días, calcula el <b>Punto de Reorden (ROP)</b>, <b>Stock de Seguridad</b> y los tiempos de entrega (<i>Lead Time</i>) del proveedor, generando <b>Sugerencias de Compra</b> listas para ser aprobadas con un solo clic.<br/><br/>"
            "<b>Conclusión:</b> Unimos la gestión operativa diaria con Machine Learning y logística avanzada para tomar decisiones basadas en datos.»",
            box_style
        )]
    ]
    t_box = Table(script_box, colWidths=[504])
    t_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#93C5FD")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_box)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ PDF generado exitosamente en: {PDF_PATH}")


if __name__ == "__main__":
    build_pdf()
