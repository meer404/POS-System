// Toast notifications + a reusable animated modal dialog helper (used
// instead of window.alert()/confirm() throughout the app).

const Toast = {
    show(message, type = 'info', duration = 3200) {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = message;
        container.appendChild(el);
        setTimeout(() => {
            el.classList.add('leaving');
            setTimeout(() => el.remove(), 200);
        }, duration);
    },
    success(msg) { this.show(msg, 'success'); },
    error(msg) { this.show(msg, 'error'); },
    warn(msg) { this.show(msg, 'warn'); },
    info(msg) { this.show(msg, 'info'); },
};

const Modal = {
    _stack: [],

    open(innerHtml, { wide = false, onClose = null } = {}) {
        ScannerFocus.pause();
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `<div class="modal-box ${wide ? 'modal-wide' : ''}">${innerHtml}</div>`;
        overlay.addEventListener('mousedown', (e) => {
            if (e.target === overlay) this.close(overlay, onClose);
        });
        document.body.appendChild(overlay);
        this._stack.push(overlay);
        return overlay;
    },

    close(overlay, onClose = null) {
        if (!overlay) return;
        overlay.remove();
        this._stack = this._stack.filter((o) => o !== overlay);
        if (this._stack.length === 0) {
            ScannerFocus.resume();
        }
        if (onClose) onClose();
    },

    closeAll() {
        this._stack.forEach((o) => o.remove());
        this._stack = [];
        ScannerFocus.resume();
    },

    confirm(message, { title = 'دڵنیابوونەوە', confirmLabel = 'دڵنیام', danger = false } = {}) {
        return new Promise((resolve) => {
            const overlay = this.open(`
                <div class="modal-header"><h2>${title}</h2></div>
                <p>${message}</p>
                <div class="modal-actions">
                    <button class="btn btn-outline" id="modal-cancel-btn">پاشگەزبوونەوە</button>
                    <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" id="modal-confirm-btn">${confirmLabel}</button>
                </div>
            `);
            overlay.querySelector('#modal-cancel-btn').addEventListener('click', () => {
                this.close(overlay);
                resolve(false);
            });
            overlay.querySelector('#modal-confirm-btn').addEventListener('click', () => {
                this.close(overlay);
                resolve(true);
            });
        });
    },
};
