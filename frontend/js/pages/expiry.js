const ExpiryPage = (() => {
    function el(id) {
        return document.getElementById(id);
    }

    function rowHtml(batch, rowClass) {
        return `
        <tr class="${rowClass}" data-batch-id="${batch.id}">
            <td class="text-bold">${batch.product_name}</td>
            <td>${formatNumber(batch.quantity)} ${batch.unit || ''}</td>
            <td>${batch.expiry_date || '-'}</td>
            <td>${formatDate(batch.received_at)}</td>
            <td class="flex gap-6">
                <button class="btn btn-danger btn-sm loss-btn" data-id="${batch.id}" data-max="${batch.quantity}" data-name="${batch.product_name}">
                    <img class="icon icon-sm" src="assets/icons/trash.svg" alt="" /> زیانبوو
                </button>
                <button class="btn btn-outline btn-sm return-btn" data-id="${batch.id}" data-max="${batch.quantity}" data-name="${batch.product_name}">
                    <img class="icon icon-sm" src="assets/icons/arrow-repeat.svg" alt="" /> گەڕاندنەوە
                </button>
            </td>
        </tr>`;
    }

    async function promptQuantity(name, max) {
        return new Promise((resolve) => {
            const overlay = Modal.open(`
                <div class="modal-header"><h2>بڕ دیاری بکە</h2></div>
                <p class="text-muted">"${name}" — زۆرترین بڕ: ${formatNumber(max)}</p>
                <div class="form-group mt-10">
                    <label>بڕ</label>
                    <input type="text" id="qty-prompt-input" value="${max}" />
                </div>
                <div class="modal-actions">
                    <button class="btn btn-outline" id="qty-prompt-cancel">پاشگەزبوونەوە</button>
                    <button class="btn btn-primary" id="qty-prompt-confirm">دڵنیام</button>
                </div>
            `);
            NumericInput.bind(overlay.querySelector('#qty-prompt-input'));
            overlay.querySelector('#qty-prompt-cancel').addEventListener('click', () => {
                Modal.close(overlay);
                resolve(null);
            });
            overlay.querySelector('#qty-prompt-confirm').addEventListener('click', () => {
                const val = parseInt(overlay.querySelector('#qty-prompt-input').value, 10);
                Modal.close(overlay);
                resolve(val);
            });
        });
    }

    async function loadLists() {
        try {
            const [expired, nearExpiry] = await Promise.all([
                Api.call('list_expired_batches'),
                Api.call('list_near_expiry_batches', 7),
            ]);

            const expiredBody = el('expired-body');
            const expiredEmpty = el('expired-empty');
            if (expired.length === 0) {
                expiredBody.innerHTML = '';
                expiredEmpty.classList.remove('hidden');
            } else {
                expiredEmpty.classList.add('hidden');
                expiredBody.innerHTML = expired.map((b) => rowHtml(b, 'row-expired')).join('');
            }

            const nearBody = el('near-expiry-body');
            const nearEmpty = el('near-expiry-empty');
            if (nearExpiry.length === 0) {
                nearBody.innerHTML = '';
                nearEmpty.classList.remove('hidden');
            } else {
                nearEmpty.classList.add('hidden');
                nearBody.innerHTML = nearExpiry.map((b) => rowHtml(b, 'row-near-expiry')).join('');
            }
        } catch (err) {
            Toast.error(err.message);
        }
    }

    async function handleTableClick(e) {
        const lossBtn = e.target.closest('.loss-btn');
        const returnBtn = e.target.closest('.return-btn');
        if (!lossBtn && !returnBtn) return;

        const btn = lossBtn || returnBtn;
        const batchId = parseInt(btn.dataset.id, 10);
        const max = parseInt(btn.dataset.max, 10);
        const name = btn.dataset.name;

        const qty = await promptQuantity(name, max);
        if (!qty || qty <= 0) return;

        try {
            if (lossBtn) {
                await Api.call('mark_batch_as_loss', batchId, qty);
                Toast.success('وەک زیان تۆمارکرا');
            } else {
                await Api.call('return_batch_to_supplier', batchId, qty);
                Toast.success('گەڕایەوە بۆ دابینکەر');
            }
            await loadLists();
        } catch (err) {
            Toast.error(err.message);
        }
    }

    function init() {
        el('expired-body').addEventListener('click', handleTableClick);
        el('near-expiry-body').addEventListener('click', handleTableClick);
        loadLists();
    }

    function destroy() {}

    return { init, destroy };
})();
