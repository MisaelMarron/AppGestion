(() => {
if (!window.Chart) return;
Chart.defaults.font.family = "Inter, Segoe UI, sans-serif"; Chart.defaults.color = '#89917f';
const data = JSON.parse(document.getElementById('serie-actividad').textContent);
new Chart(document.getElementById('actividad'), {type:'line',data:{labels:data.map(r=>r.fecha.slice(5)),datasets:[{label:'Producciones',data:data.map(r=>r.producciones),borderColor:'#657b45',backgroundColor:'#d9e5c257',fill:true,borderWidth:2,pointRadius:2,tension:.2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8}},y:{beginAtZero:true,ticks:{precision:0},grid:{color:'#eef1e8'}}}}});
const risk = JSON.parse(document.getElementById('serie-riesgo').textContent);
new Chart(document.getElementById('riesgo'),{type:'doughnut',data:{labels:['Estable','Atención','Crítico','Sin datos'],datasets:[{data:Object.values(risk),backgroundColor:['#c9df95','#b6b99e','#7d826e','#eeeeea'],borderWidth:3,borderColor:'#fff'}]},options:{responsive:true,maintainAspectRatio:false,cutout:'77%',plugins:{legend:{position:'bottom',labels:{boxWidth:8,boxHeight:8,padding:16,font:{size:10}}}}}});
})();
