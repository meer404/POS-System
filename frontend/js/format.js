// Shared IQD integer money formatting (no decimals, ever).

function formatMoney(amount) {
    const n = Math.round(Number(amount) || 0);
    return n.toLocaleString('en-US') + ' د.ع';
}

function formatNumber(n) {
    return Math.round(Number(n) || 0).toLocaleString('en-US');
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
