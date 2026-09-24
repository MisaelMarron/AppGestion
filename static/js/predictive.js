(() => {
  const read = id => JSON.parse(document.getElementById(id)?.textContent || 'null') || [];
  if (!window.Chart) {
    document.getElementById('chart-error').textContent = 'No se pudo cargar el gráfico. Los valores están disponibles en la tabla de detalle.';
    return;
  }
  const a = read('analysis-data');
  const markers = {
    id: 'decisionDates',
    afterDraw(chart) {
      if (chart.canvas.id !== 'stock-chart' || !chart.data.labels.length) return;
      const points = [[chart.data.labels[0], 'Hoy'], [a.fecha_pedido, 'Pedido'],
        [a.fecha_recepcion, 'Recepción esperada'], [a.fecha_agotamiento, 'Agotamiento']];
      const {ctx, chartArea, scales} = chart;
      ctx.save();
      points.forEach(([date, label], i) => {
        const index = chart.data.labels.indexOf(date);
        if (index < 0) return;
        const x = scales.x.getPixelForValue(index);
        ctx.strokeStyle = '#64748b'; ctx.setLineDash([3, 4]);
        ctx.beginPath(); ctx.moveTo(x, chartArea.top); ctx.lineTo(x, chartArea.bottom); ctx.stroke();
        ctx.setLineDash([]); ctx.fillStyle = '#334155'; ctx.font = '11px sans-serif';
        ctx.fillText(label, Math.min(x + 3, chartArea.right - 110), chartArea.top + 12 + i * 13);
      });
      ctx.restore();
    }
  };
  Chart.register(markers);
  const chart = (id, rows, fields, type = 'line') => {
    const colors = ['#0f3460', '#e94560', '#00b894', '#b87910'];
    new Chart(document.getElementById(id), {type, data: {
      labels: rows.map(r => r.fecha || r.modelo),
      datasets: fields.map(([key, label], i) => ({label, data: rows.map(r => r[key]),
        borderColor: colors[i], backgroundColor: colors[i], borderWidth: 2, pointRadius: 1, tension: .1}))
    }, options: {responsive: true, maintainAspectRatio: false, interaction: {mode: 'index', intersect: false},
      plugins: {legend: {position: 'bottom'}}, scales: {y: {beginAtZero: true}}}});
  };
  chart('stock-chart', a.proyeccion || [], [['stock','Stock proyectado'],['rop','ROP'],['seguridad','Stock de seguridad'],['recepcion','Recepciones']]);
  const h = read('history-data').map(r => ({fecha:r.fecha, real:r.consumo}));
  const f = read('forecast-data').map(r => ({fecha:r.fecha, predicho:r.consumo}));
  chart('consumo-chart', [...h,...f], [['real','Histórico'],['predicho','Pronóstico']]);
  chart('validation-chart', read('validation-data'), [['real','Real'],['predicho','Predicho']]);
  chart('history-stock-chart', read('stocks-data'), [['stock','Stock']]);
  chart('metric-chart', read('metrics-data').filter(r => r.metricas).map(r => ({modelo:r.modelo,...r.metricas})), [['mae','MAE'],['rmse','RMSE']], 'bar');
})();
