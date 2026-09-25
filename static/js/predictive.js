(() => {
  const read = id => JSON.parse(document.getElementById(id)?.textContent || 'null') || [];
  if (!window.Chart) {
    const el = document.getElementById('chart-error');
    if (el) el.textContent = 'No se pudo cargar el gráfico. Los valores están disponibles en la tabla de detalle.';
    return;
  }

  const a = read('analysis-data');

  // ── Marcadores de fechas clave en stock proyectado ──
  const markers = {
    id: 'decisionDates',
    afterDraw(chart) {
      if (chart.canvas.id !== 'stock-chart' || !chart.data.labels.length) return;
      const points = [
        [chart.data.labels[0], 'Hoy'],
        [a.fecha_pedido, 'Pedido'],
        [a.fecha_recepcion, 'Recep. esperada'],
        [a.fecha_agotamiento, 'Agotamiento'],
      ];
      const {ctx, chartArea, scales} = chart;
      ctx.save();
      points.forEach(([date, label], i) => {
        const index = chart.data.labels.indexOf(date);
        if (index < 0) return;
        const x = scales.x.getPixelForValue(index);
        ctx.strokeStyle = '#64748b'; ctx.setLineDash([3, 4]);
        ctx.beginPath(); ctx.moveTo(x, chartArea.top); ctx.lineTo(x, chartArea.bottom); ctx.stroke();
        ctx.setLineDash([]); ctx.fillStyle = '#334155'; ctx.font = '11px sans-serif';
        ctx.fillText(label, Math.min(x + 3, chartArea.right - 140), chartArea.top + 14 + i * 14);
      });
      ctx.restore();
    }
  };
  Chart.register(markers);

  // ── Función genérica de chart ──
  const chart = (id, rows, fields, type = 'line') => {
    const el = document.getElementById(id);
    if (!el) return;
    const colors = ['#6366f1', '#ef4444', '#10b981', '#f59e0b', '#3b82f6'];
    new Chart(el, {
      type,
      data: {
        labels: rows.map(r => r.fecha || r.modelo),
        datasets: fields.map(([key, label], i) => ({
          label,
          data: rows.map(r => r[key]),
          borderColor: colors[i], backgroundColor: type === 'bar' ? colors[i] + 'cc' : colors[i],
          borderWidth: 2, pointRadius: type === 'bar' ? 0 : 1, tension: .15,
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: {mode: 'index', intersect: false},
        plugins: {legend: {position: 'bottom'}},
        scales: {y: {beginAtZero: true}},
      },
    });
  };

  // ── Stock proyectado ──
  chart('stock-chart', a.proyeccion || [],
    [['stock','Stock proyectado'],['rop','ROP'],['seguridad','Stock seguridad'],['recepcion','Recepciones']]);

  // ── Consumo histórico + pronóstico ──
  const h = read('history-data').map(r => ({fecha: r.fecha, real: r.consumo}));
  const f = read('forecast-data').map(r => ({fecha: r.fecha, predicho: r.consumo}));
  chart('consumo-chart', [...h, ...f], [['real','Histórico'], ['predicho','Pronóstico']]);

  // ── Validación real vs predicho ──
  chart('validation-chart', read('validation-data'), [['real','Real'], ['predicho','Predicho']]);

  // ── Comparativa métricas por modelo (barra) ──
  const metricsData = read('metrics-data')
    .filter(r => r.metricas)
    .map(r => ({modelo: r.modelo, ...r.metricas}));
  chart('metric-chart', metricsData, [['mae','MAE'], ['rmse','RMSE']], 'bar');
})();
