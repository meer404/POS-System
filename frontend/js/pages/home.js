const HomePage = (() => {
    const CARD_COLORS = ['primary', 'accent', 'warn', 'danger'];

    function el(id) {
        return document.getElementById(id);
    }

    function renderNavCards() {
        const role = State.currentUser.role;
        const items = MENU.filter((m) => m.route !== 'home' && m.roles.includes(role));
        el('home-nav-grid').innerHTML = items
            .map(
                (m, i) => `
            <a href="#/${m.route}" class="home-nav-card">
                <div class="home-nav-icon ${CARD_COLORS[i % CARD_COLORS.length]}">
                    <img class="icon icon-lg" src="assets/icons/${m.icon}.svg" alt="" />
                </div>
                <span class="home-nav-label">${m.label}</span>
            </a>`
            )
            .join('');
    }

    async function loadQuickStats() {
        if (!State.isAdmin()) return;
        try {
            const today = localDateISO();
            const [summary, nearExpiry] = await Promise.all([
                Api.call('get_report_summary', today, today, null),
                Api.call('list_near_expiry_batches', 7),
            ]);
            el('home-stat-revenue').textContent = formatMoney(summary.revenue);
            el('home-stat-near-expiry').textContent = formatNumber(nearExpiry.length);
            el('home-quick-stats').classList.remove('hidden');
        } catch (err) {
            Toast.error(err.message);
        }
    }

    function init() {
        el('home-username').textContent = State.currentUser.username;
        el('home-userrole').textContent =
            State.currentUser.role === 'admin' ? 'بەڕێوەبەر' : 'فرۆشیار';
        el('home-logout-btn').addEventListener('click', handleLogout);

        renderNavCards();
        loadQuickStats();
    }

    return { init };
})();
