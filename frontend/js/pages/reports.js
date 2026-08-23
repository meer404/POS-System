const ReportsPage = (() => {
    let chartInstance = null;

    function el(id) {
        return document.getElementById(id);
    }

    function setActivePreset(preset) {
        document.querySelectorAll('.preset-buttons button').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.preset === preset);
        });
    }

    function renderSummary(summary) {
        el('stat-items-sold').textContent = formatNumber(summary.items_sold);
        el('stat-revenue').textContent = formatMoney(summary.revenue);
        el('stat-profit').textContent = formatMoney(summary.profit);
        if (summary.returns) {
            el('stat-returns').textContent = `${formatMoney(summary.returns.amount)} (${formatNumber(summary.returns.quantity)} دانە)`;
        }

        const topBody = el('top-products-body');
        if (summary.top_products.length === 0) {
            topBody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">هیچ فرۆشتنێک نییە</td></tr>`;
        } else {
            topBody.innerHTML = summary.top_products
                .map(
                    (p) => `
                <tr>
                    <td class="text-bold">${p.name}</td>
                    <td>${formatNumber(p.qty_sold)}</td>
                    <td>${formatMoney(p.revenue)}</td>
                </tr>`
                )
                .join('');
        }

        renderChart(summary.daily_chart);
    }

    function renderChart(dailyData) {
        const ctx = document.getElementById('daily-chart');
        if (!ctx) return;
        const labels = dailyData.map((d) => d.day.slice(5));
        const values = dailyData.map((d) => d.revenue);

        if (chartInstance) {
            chartInstance.destroy();
        }
        chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'داهات',
                        data: values,
                        backgroundColor: '#1f9d6e',
                        borderRadius: 6,
                        maxBarThickness: 40,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: (v) => formatNumber(v) } },
                },
            },
        });
    }

    async function loadSummary({ preset = null, startDate = null, endDate = null } = {}) {
        try {
            const summary = await Api.call('get_report_summary', startDate, endDate, preset);
            renderSummary(summary);
        } catch (err) {
            Toast.error(err.message);
        }
    }

    function init() {
        const today = localDateISO();
        el('report-start-date').value = today;
        el('report-end-date').value = today;

        document.querySelectorAll('.preset-buttons button').forEach((btn) => {
            btn.addEventListener('click', () => {
                setActivePreset(btn.dataset.preset);
                loadSummary({ preset: btn.dataset.preset });
            });
        });

        el('report-apply-range-btn').addEventListener('click', () => {
            setActivePreset(null);
            loadSummary({ startDate: el('report-start-date').value, endDate: el('report-end-date').value });
        });

        loadSummary({ preset: 'today' });
    }

    function destroy() {
        if (chartInstance) {
            chartInstance.destroy();
            chartInstance = null;
        }
    }

    return { init, destroy };
})();
