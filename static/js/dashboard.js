document.addEventListener('DOMContentLoaded', async () => {
  const distCanvas = document.getElementById('distributionChart');
  const trendsCanvas = document.getElementById('trendsChart');
  const severityCanvas = document.getElementById('severityChart');

  if (!distCanvas && !trendsCanvas && !severityCanvas) return;

  let chartInstances = {};

  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();

    // Store data globally for voice summary
    window.dashboardStatsData = data;

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

    function buildCharts() {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      const textColor = isDark ? '#cbd5e1' : '#334155';
      const gridColor = isDark ? '#1e293b' : '#f1f5f9';
      const donutBorder = isDark ? '#131f37' : '#ffffff';

      // Destroy prior instances if re-rendering on theme change
      if (chartInstances.dist) chartInstances.dist.destroy();
      if (chartInstances.severity) chartInstances.severity.destroy();
      if (chartInstances.trends) chartInstances.trends.destroy();

      // 1. Doughnut Chart: Distribution
      if (distCanvas) {
        chartInstances.dist = new Chart(distCanvas, {
          type: 'doughnut',
          data: {
            labels: classLabels,
            datasets: [{
              data: classCounts,
              backgroundColor: chartColors,
              borderColor: donutBorder,
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
                  color: textColor,
                  boxWidth: 13,
                  padding: 12,
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
        chartInstances.severity = new Chart(severityCanvas, {
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
                ticks: { stepSize: 1, precision: 0, color: textColor },
                grid: { color: gridColor }
              },
              x: {
                ticks: { color: textColor },
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

        chartInstances.trends = new Chart(trendsCanvas, {
          type: 'line',
          data: {
            labels: trendLabels.length > 0 ? trendLabels : ['Case 1', 'Case 2', 'Case 3', 'Case 4', 'Case 5'],
            datasets: [{
              label: 'AI Confidence Score (%)',
              data: trendConf.length > 0 ? trendConf : [96, 88, 91, 94, 97],
              borderColor: isDark ? '#38bdf8' : '#0f4c81',
              backgroundColor: isDark ? 'rgba(56, 189, 248, 0.15)' : 'rgba(15, 76, 129, 0.08)',
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
                labels: { boxWidth: 12, color: textColor, font: { family: 'Segoe UI', size: 12 } }
              }
            },
            scales: {
              y: {
                min: 50,
                max: 100,
                grid: { color: gridColor },
                ticks: { callback: v => v + '%', color: textColor }
              },
              x: {
                ticks: { color: textColor },
                grid: { display: false }
              }
            }
          }
        });
      }
    }

    // Initial render
    buildCharts();

    // Re-render when theme switches
    window.addEventListener('themeChanged', () => {
      buildCharts();
    });

  } catch (err) {
    console.error('Failed to load dashboard data:', err);
  }
});
