const UsersPage = (() => {
    function el(id) {
        return document.getElementById(id);
    }

    function rowHtml(user) {
        const roleLabel = user.role === 'admin' ? 'بەڕێوەبەر' : 'فرۆشیار';
        const otherRole = user.role === 'admin' ? 'cashier' : 'admin';
        const otherRoleLabel = user.role === 'admin' ? 'فرۆشیار' : 'بەڕێوەبەر';
        const roleCell = user.protected
            ? `<span class="badge badge-primary">${roleLabel}</span> <span class="badge badge-neutral">پارێزراو</span>`
            : `<span class="badge ${user.role === 'admin' ? 'badge-primary' : 'badge-neutral'}">${roleLabel}</span>`;
        const actionsCell = user.protected
            ? `<span class="text-muted">پارێزراوە</span>`
            : `
                <button class="btn btn-outline btn-sm role-toggle-btn" data-id="${user.id}" data-role="${otherRole}">
                    گۆڕین بۆ ${otherRoleLabel}
                </button>
                <button class="btn btn-ghost btn-sm reset-pw-btn" data-id="${user.id}" data-name="${user.username}">
                    <img class="icon icon-sm" src="assets/icons/key.svg" alt="" /> ڕیسێتکردنی وشەی نهێنی
                </button>
                <button class="btn btn-ghost btn-sm delete-user-btn" data-id="${user.id}" data-name="${user.username}">
                    <img class="icon icon-sm" src="assets/icons/trash.svg" alt="" /> سڕینەوە
                </button>`;
        return `
        <tr data-user-id="${user.id}">
            <td class="text-bold">${user.username}</td>
            <td>${roleCell}</td>
            <td>${formatDate(user.created_at)}</td>
            <td class="flex gap-6">${actionsCell}</td>
        </tr>`;
    }

    async function loadUsers() {
        try {
            const list = await Api.call('list_users');
            el('users-list-body').innerHTML = list.map(rowHtml).join('');
        } catch (err) {
            Toast.error(err.message);
        }
    }

    async function handleCreateUser(e) {
        e.preventDefault();
        try {
            await Api.call('create_user', el('new-username').value.trim(), el('new-password').value, el('new-role').value);
            Toast.success('بەکارهێنەر زیادکرا');
            document.getElementById('create-user-form').reset();
            await loadUsers();
        } catch (err) {
            Toast.error(err.message);
        }
    }

    function promptNewPassword(username) {
        return new Promise((resolve) => {
            const overlay = Modal.open(`
                <div class="modal-header"><h2>ڕیسێتکردنی وشەی نهێنی</h2></div>
                <p class="text-muted">بۆ بەکارهێنەری "${username}"</p>
                <div class="form-group mt-10">
                    <label>وشەی نهێنی نوێ</label>
                    <input type="password" id="reset-pw-input" minlength="4" />
                </div>
                <div class="modal-actions">
                    <button class="btn btn-outline" id="reset-pw-cancel">پاشگەزبوونەوە</button>
                    <button class="btn btn-primary" id="reset-pw-confirm">پاشەکەوتکردن</button>
                </div>
            `);
            overlay.querySelector('#reset-pw-cancel').addEventListener('click', () => {
                Modal.close(overlay);
                resolve(null);
            });
            overlay.querySelector('#reset-pw-confirm').addEventListener('click', () => {
                const val = overlay.querySelector('#reset-pw-input').value;
                Modal.close(overlay);
                resolve(val);
            });
        });
    }

    async function handleTableClick(e) {
        const roleBtn = e.target.closest('.role-toggle-btn');
        const resetBtn = e.target.closest('.reset-pw-btn');
        const deleteBtn = e.target.closest('.delete-user-btn');

        if (deleteBtn) {
            const userId = parseInt(deleteBtn.dataset.id, 10);
            const username = deleteBtn.dataset.name;
            const confirmed = await Modal.confirm(`بەکارهێنەری "${username}" بسڕدرێتەوە؟`);
            if (!confirmed) return;
            try {
                await Api.call('delete_user', userId);
                Toast.success('بەکارهێنەر سڕایەوە');
                await loadUsers();
            } catch (err) {
                Toast.error(err.message);
            }
            return;
        }

        if (roleBtn) {
            const userId = parseInt(roleBtn.dataset.id, 10);
            const newRole = roleBtn.dataset.role;
            const confirmed = await Modal.confirm(`ڕۆڵی ئەم بەکارهێنەرە بگۆڕدرێت؟`);
            if (!confirmed) return;
            try {
                await Api.call('set_user_role', userId, newRole);
                Toast.success('ڕۆڵ گۆڕدرا');
                await loadUsers();
            } catch (err) {
                Toast.error(err.message);
            }
        } else if (resetBtn) {
            const userId = parseInt(resetBtn.dataset.id, 10);
            const username = resetBtn.dataset.name;
            const newPassword = await promptNewPassword(username);
            if (!newPassword) return;
            try {
                await Api.call('reset_user_password', userId, newPassword);
                Toast.success('وشەی نهێنی ڕیسێت کرا');
            } catch (err) {
                Toast.error(err.message);
            }
        }
    }

    function init() {
        el('create-user-form').addEventListener('submit', handleCreateUser);
        el('users-list-body').addEventListener('click', handleTableClick);
        loadUsers();
    }

    function destroy() {}

    return { init, destroy };
})();
