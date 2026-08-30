const BackupPage = (() => {
    function el(id) {
        return document.getElementById(id);
    }

    function rowHtml(b) {
        const sizeKb = formatNumber(Math.max(1, Math.round(b.size / 1024)));
        return `
        <tr data-name="${b.filename}">
            <td class="text-bold">${b.filename}</td>
            <td>${sizeKb} KB</td>
            <td>${b.created_at}</td>
            <td>
                <button class="btn btn-outline btn-sm restore-row-btn" data-name="${b.filename}">
                    <img class="icon icon-sm" src="assets/icons/box-arrow-in-right.svg" alt="" /> گەڕاندنەوە
                </button>
            </td>
        </tr>`;
    }

    async function loadBackups() {
        try {
            const list = await Api.call('list_backups');
            const body = el('backups-list-body');
            if (!list.length) {
                body.innerHTML = '<tr><td colspan="4" class="text-muted text-center">هیچ باکاپێک نییە</td></tr>';
                return;
            }
            body.innerHTML = list.map(rowHtml).join('');
        } catch (err) {
            Toast.error(err.message);
        }
    }

    function promptAdminPassword() {
        return new Promise((resolve) => {
            const overlay = Modal.open(`
                <div class="modal-header"><h2>پشتڕاستکردنەوەی گەڕاندنەوە</h2></div>
                <p class="text-muted">بۆ بەردەوامبوون وشەی نهێنی هەژماری بەڕێوەبەر بنووسە.</p>
                <div class="form-group mt-10">
                    <label>وشەی نهێنی</label>
                    <input type="password" id="restore-pw-input" />
                </div>
                <div class="modal-actions">
                    <button class="btn btn-outline" id="restore-pw-cancel">پاشگەزبوونەوە</button>
                    <button class="btn btn-danger" id="restore-pw-confirm">گەڕاندنەوە</button>
                </div>
            `);
            overlay.querySelector('#restore-pw-cancel').addEventListener('click', () => {
                Modal.close(overlay);
                resolve(null);
            });
            overlay.querySelector('#restore-pw-confirm').addEventListener('click', () => {
                const val = overlay.querySelector('#restore-pw-input').value;
                Modal.close(overlay);
                resolve(val || null);
            });
        });
    }

    async function doRestore(archiveName) {
        const password = await promptAdminPassword();
        if (!password) return;
        try {
            await Api.call('restore_backup', password, archiveName || null);
            Toast.success('داتاکان گەڕێنرانەوە، تکایە دووبارە بچۆرە ژوورەوە');
            State.currentUser = null;
            State.resetAllSalesTabs();
            window.location.hash = '';
            showLoginScreen();
        } catch (err) {
            Toast.error(err.message);
        }
    }

    async function handleCreateBackup() {
        const btn = el('create-backup-btn');
        btn.disabled = true;
        try {
            const data = await Api.call('create_backup');
            Toast.success(
                data.exported_to
                    ? 'باکاپ دروستکرا و پاشەکەوتکرا'
                    : 'باکاپ دروستکرا لە بوخچەی data/backups'
            );
            await loadBackups();
        } catch (err) {
            Toast.error(err.message);
        } finally {
            btn.disabled = false;
        }
    }

    async function handleListClick(e) {
        const btn = e.target.closest('.restore-row-btn');
        if (!btn) return;
        const name = btn.dataset.name;
        const confirmed = await Modal.confirm(
            `گەڕاندنەوە بۆ "${name}"؟ هەموو داتای ئێستا دەگۆڕدرێت.`,
            { confirmLabel: 'گەڕاندنەوە', danger: true }
        );
        if (!confirmed) return;
        await doRestore(name);
    }

    function init() {
        el('create-backup-btn').addEventListener('click', handleCreateBackup);
        el('restore-file-btn').addEventListener('click', () => doRestore(null));
        el('backups-list-body').addEventListener('click', handleListClick);
        loadBackups();
    }

    function destroy() {}

    return { init, destroy };
})();
