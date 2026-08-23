// Shared IQD integer money formatting (no decimals, ever).

function formatMoney(amount) {
    const n = Math.round(Number(amount) || 0);
    return n.toLocaleString('en-US') + ' د.ع';
}

function formatNumber(n) {
    return Math.round(Number(n) || 0).toLocaleString('en-US');
}

// Local (not UTC) calendar date as YYYY-MM-DD -- for date inputs / report
// range defaults, where "today" must match the user's wall-clock day, not
// Date.toISOString()'s UTC day.
function localDateISO(d = new Date()) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatDate(isoString) {
    if (!isoString) return '-';
    const d = new Date(isoString.replace(' ', 'T'));
    if (isNaN(d)) return isoString;
    return d.toLocaleString('en-GB', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}
