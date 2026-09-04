document.addEventListener('DOMContentLoaded', async () => {
  const distCanvas = document.getElementById('distributionChart');
  const trendsCanvas = document.getElementById('trendsChart');
  const severityCanvas = document.getElementById('severityChart');

  if (!distCanvas && !trendsCanvas && !severityCanvas) return;

  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();

    const classLabels = ['No DR', 'Mild DR', 'Moderate DR', 'Severe DR', 'Proliferative DR'];
    const classCounts = [
      data.no_dr || 0,
      data.mild || 0,
      data.moderate || 0,
      data.severe || 0,
      data.proliferative || 0
    ];

    const chartColors = [
      '#10b981', // No DR (Green)
      '#0284c7', // Mild (Sky Blue)
      '#f59e0b', // Moderate (Amber)
      '#ea580c', // Severe (Orange)
      '#dc2626'  // Proliferative (Red)
    ];

    // 1. Doughnut Chart: Distribution
    if (distCanvas) {
      new Chart(distCanvas, {
        type: 'doughnut',
        data: {
          labels: classLabels,
          datasets: [{
            data: classCounts,
            backgroundColor: chartColors,
            borderColor: '#ffffff',
            borderWidth: 2,
            hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                boxWidth: 14,
                padding: 14,
                font: { family: 'Segoe UI', size: 12 }
              }
            }
          },
          cutout: '68%'
        }
      });
    }

    // 2. Bar Chart: Severity Breakdown
    if (severityCanvas) {
      new Chart(severityCanvas, {
        type: 'bar',
        data: {
          labels: classLabels,
          datasets: [{
            label: 'Patients Screened',
            data: classCounts,
            backgroundColor: chartColors,
            borderRadius: 8,
            borderSkipped: false
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { stepSize: 1, precision: 0 },
              grid: { color: '#f1f5f9' }
            },
            x: {
              grid: { display: false }
            }
          }
        }
      });
    }

    // 3. Line Chart: Timeline Trends
    if (trendsCanvas) {
      const timeline = data.timeline || [];
      const trendLabels = timeline.map((item, idx) => `Case #${idx + 1}`);
      const trendConf = timeline.map(item => item.confidence);

      new Chart(trendsCanvas, {
        type: 'line',
        data: {
          labels: trendLabels.length > 0 ? trendLabels : ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5'],
          datasets: [{
            label: 'AI Confidence Score (%)',
            data: trendConf.length > 0 ? trendConf : [96, 88, 91, 94, 97],
            borderColor: '#0f4c81',
            backgroundColor: 'rgba(15, 76, 129, 0.08)',
            borderWidth: 2.5,
            tension: 0.35,
            fill: true,
            pointBackgroundColor: '#00a896',
            pointRadius: 4,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top',
              labels: { boxWidth: 12, font: { family: 'Segoe UI', size: 12 } }
            }
          },
          scales: {
            y: {
              min: 50,
              max: 100,
              grid: { color: '#f1f5f9' },
              ticks: { callback: v => v + '%' }
            },
            x: {
              grid: { display: false }
            }
          }
        }
      });
    }

  } catch (err) {
    console.error('Failed to load dashboard data:', err);
  }
});
