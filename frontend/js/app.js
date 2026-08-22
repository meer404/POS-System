// Boot script: decides login vs. shell, wires login form + logout + forced
// password change flow. Loaded last, after all page modules exist.

function showLoginScreen() {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('app-shell').classList.add('hidden');
    document.getElementById('login-form').reset();
    document.getElementById('login-error').classList.add('hidden');
    document.getElementById('login-username').focus();
}

async function showAppShell() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('app-shell').classList.remove('hidden');
    document.getElementById('sidebar-username').textContent = State.currentUser.username;
    document.getElementById('sidebar-userrole').textContent =
        State.currentUser.role === 'admin' ? 'بەڕێوەبەر' : 'فرۆشیار';
    await Router.renderSidebar();
    Router.start();
    await Router.navigate();
}

function openForcePasswordChangeModal() {
    const overlay = Modal.open(
        `
        <div class="modal-header"><h2>گۆڕینی وشەی نهێنی</h2></div>
        <p class="text-muted mt-10">تکایە وشەی نهێنی بنەڕەتی بگۆڕە بۆ پاراستنی هەژمارەکەت.</p>
        <form id="force-pw-form" class="flex flex-col gap-14 mt-20">
            <div class="form-group">
                <label>وشەی نهێنی نوێ</label>
                <input type="password" id="force-pw-new" required minlength="4" />
            </div>
            <div class="form-group">
                <label>دووبارەکردنەوەی وشەی نهێنی</label>
                <input type="password" id="force-pw-confirm" required minlength="4" />
            </div>
            <div id="force-pw-error" class="field-error hidden"></div>
            <button type="submit" class="btn btn-primary btn-block">پاشەکەوتکردن</button>
        </form>
        `,
        { onClose: null }
    );

    const form = overlay.querySelector('#force-pw-form');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const newPw = overlay.querySelector('#force-pw-new').value;
        const confirmPw = overlay.querySelector('#force-pw-confirm').value;
        const errorEl = overlay.querySelector('#force-pw-error');
        errorEl.classList.add('hidden');

        if (newPw !== confirmPw) {
            errorEl.textContent = 'وشەی نهێنیەکان وەک یەک نین';
            errorEl.classList.remove('hidden');
            return;
        }
        try {
            await Api.call('force_change_password', newPw);
            Toast.success('وشەی نهێنی گۆڕدرا');
            Modal.close(overlay);
        } catch (err) {
            errorEl.textContent = err.message;
            errorEl.classList.remove('hidden');
        }
    });
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    const submitBtn = document.getElementById('login-submit-btn');
    errorEl.classList.add('hidden');
    submitBtn.disabled = true;

    try {
        const user = await Api.call('login', username, password);
        State.currentUser = user;
        await showAppShell();
        if (user.force_password_change) {
            openForcePasswordChangeModal();
        }
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove('hidden');
    } finally {
        submitBtn.disabled = false;
    }
}

async function handleLogout() {
    const confirmed = await Modal.confirm('دڵنیایت لە دەرچوون؟', { confirmLabel: 'دەرچوون' });
    if (!confirmed) return;
    await Api.call('logout');
    State.currentUser = null;
    State.cartClear();
    window.location.hash = '';
    showLoginScreen();
}

async function boot() {
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('logout-btn').addEventListener('click', handleLogout);

    await Api.ready();
    const user = await Api.call('get_current_user');
    if (user) {
        State.currentUser = user;
        await showAppShell();
    } else {
        showLoginScreen();
    }
}

boot();
