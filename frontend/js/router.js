// Hash-based router + role-filtered sidebar builder.

const MENU = [
    { route: 'home', label: 'ماڵەوە', icon: 'shop', roles: ['admin', 'cashier'] },
    { route: 'pos', label: 'فرۆشتن', icon: 'cart3', roles: ['admin', 'cashier'] },
    { route: 'returns', label: 'گەڕاندنەوەی کاڵا', icon: 'arrow-repeat', roles: ['admin', 'cashier'] },
    { route: 'product-add', label: 'زیادکردنی کاڵا', icon: 'plus-lg', roles: ['admin', 'cashier'] },
    { route: 'product-list', label: 'هەموو کاڵاکان', icon: 'box-seam', roles: ['admin', 'cashier'] },
    { route: 'reports', label: 'ڕاپۆرت', icon: 'bar-chart-line', roles: ['admin'] },
    { route: 'expiry', label: 'بەسەرچوون', icon: 'clock-history', roles: ['admin'] },
    { route: 'users', label: 'بەکارهێنەران', icon: 'people', roles: ['admin'] },
];

const PAGE_TITLES = {
    home: 'ماڵەوە',
    pos: 'فرۆشتن',
    returns: 'گەڕاندنەوەی کاڵا',
    'product-add': 'زیادکردنی کاڵا',
    'product-list': 'هەموو کاڵاکان',
    reports: 'ڕاپۆرت',
    expiry: 'بەسەرچوونی کاڵا',
    users: 'بەکارهێنەران',
};

const PAGE_MODULES = {
    home: () => HomePage,
    pos: () => PosPage,
    returns: () => ReturnsPage,
    'product-add': () => ProductAddPage,
    'product-list': () => ProductListPage,
    reports: () => ReportsPage,
    expiry: () => ExpiryPage,
    users: () => UsersPage,
};

const Router = (() => {
    let currentModule = null;

    function iconSvgPath(name) {
        return `assets/icons/${name}.svg`;
    }

    async function renderSidebar() {
        const nav = document.getElementById('sidebar-nav');
        if (!nav) return;
        const role = State.currentUser ? State.currentUser.role : null;
        const items = MENU.filter((m) => role && m.roles.includes(role));
        nav.innerHTML = items
            .map(
                (m) => `
            <a href="#/${m.route}" class="sidebar-nav-item" data-route="${m.route}">
                <img class="icon" src="${iconSvgPath(m.icon)}" alt="" />
                <span>${m.label}</span>
            </a>`
            )
            .join('');
    }

    function highlightActive(route) {
        document.querySelectorAll('.sidebar-nav-item').forEach((el) => {
            el.classList.toggle('active', el.dataset.route === route);
        });
    }

    function currentRoute() {
        const hash = window.location.hash.replace(/^#\//, '');
        return hash || 'home';
    }

    async function navigate() {
        const role = State.currentUser ? State.currentUser.role : null;
        let route = currentRoute();

        const menuItem = MENU.find((m) => m.route === route);
        if (!menuItem || !role || !menuItem.roles.includes(role)) {
            route = MENU.find((m) => role && m.roles.includes(role))?.route || 'home';
            window.location.hash = `#/${route}`;
            return;
        }

        if (currentModule && currentModule.destroy) {
            currentModule.destroy();
        }
        ScannerFocus.unbind();

        const titleEl = document.getElementById('page-title');
        if (titleEl) titleEl.textContent = PAGE_TITLES[route] || '';
        highlightActive(route);

        const resp = await fetch(`pages/${route}.html`);
        const html = await resp.text();
        document.getElementById('app').innerHTML = html;

        currentModule = PAGE_MODULES[route]();
        if (currentModule && currentModule.init) {
            await currentModule.init();
        }
    }

    function start() {
        window.addEventListener('hashchange', navigate);
    }

    return { start, navigate, renderSidebar };
})();
