const ReturnsPage = (() => {
    let barcodeDebounceTimer = null;
    let returnList = [];

    function el(id) {
        return document.getElementById(id);
    }

    function totalRefund() {
        return returnList.reduce((sum, item) => sum + (parseInt(item.refund_amount, 10) || 0), 0);
    }

    function updateTotal() {
        el('returns-total').textContent = formatMoney(totalRefund());
    }

    function rowHtml(item) {
        return `
        <tr data-product-id="${item.product_id}">
            <td class="cell-name">${item.name}</td>
            <td>
                <input type="text" class="qty-input" data-id="${item.product_id}" value="${item.quantity}" />
            </td>
            <td>
                <input type="text" class="refund-input" data-id="${item.product_id}" value="${item.refund_amount}" />
            </td>
            <td>
                <button class="btn btn-icon btn-ghost item-remove" data-id="${item.product_id}" title="سڕینەوە">
                    <img class="icon icon-sm" src="assets/icons/trash.svg" alt="" />
                </button>
            </td>
        </tr>`;
    }

    function renderList() {
        const body = el('returns-body');
        const empty = el('returns-empty');
        const card = document.querySelector('.pos-cart-card');

        if (returnList.length === 0) {
            body.innerHTML = '';
            empty.classList.remove('hidden');
            card.querySelector('.table-wrap').classList.add('hidden');
        } else {
            empty.classList.add('hidden');
            card.querySelector('.table-wrap').classList.remove('hidden');
            body.innerHTML = returnList.map(rowHtml).join('');
            body.querySelectorAll('.qty-input, .refund-input').forEach(NumericInput.bind);
        }
        updateTotal();
    }

    function findItem(productId) {
        return returnList.find((i) => i.product_id === productId);
    }

    function addProductToList(product) {
        const existing = findItem(product.id);
        if (existing) {
            existing.quantity += 1;
            if (!existing.refundManuallySet) {
                existing.refund_amount = existing.quantity * product.sale_price;
            }
        } else {
            returnList.push({
                product_id: product.id,
                name: product.name,
                sale_price: product.sale_price,
                quantity: 1,
                refund_amount: product.sale_price,
                refundManuallySet: false,
            });
        }
        renderList();
        ScannerFocus.refocus();
    }

    async function handleBarcodeSubmit() {
        const input = el('returns-barcode-input');
        const barcode = input.value.trim();
        if (!barcode) return;
        input.value = '';
        try {
            const product = await Api.call('find_product_by_barcode', barcode);
            if (!product) {
                Toast.error('کاڵا بەم بارکۆدە نەدۆزرایەوە');
                return;
            }
            addProductToList(product);
        } catch (err) {
            Toast.error(err.message);
        }
    }

    function handleListInput(e) {
        const id = parseInt(e.target.dataset.id, 10);
        const item = findItem(id);
        if (!item) return;

        if (e.target.classList.contains('qty-input')) {
            item.quantity = parseInt(e.target.value, 10) || 0;
            if (!item.refundManuallySet) {
                item.refund_amount = item.quantity * item.sale_price;
                const row = e.target.closest('tr');
                row.querySelector('.refund-input').value = item.refund_amount;
            }
            updateTotal();
        } else if (e.target.classList.contains('refund-input')) {
            item.refundManuallySet = true;
            item.refund_amount = parseInt(e.target.value, 10) || 0;
            updateTotal();
        }
    }

    function handleListClick(e) {
        const removeBtn = e.target.closest('.item-remove');
        if (!removeBtn) return;
        const id = parseInt(removeBtn.dataset.id, 10);
        returnList = returnList.filter((i) => i.product_id !== id);
        renderList();
        ScannerFocus.refocus();
    }

    function buildReceiptHtml(receipt) {
        const lines = receipt.items
            .map(
                (item) => `
            <div class="receipt-line">
                <span>${item.name} × ${item.quantity}</span>
                <span>${formatMoney(item.refund_amount)}</span>
            </div>`
            )
            .join('');

        return `
        <div id="receipt-print-area">
            <div class="receipt-header">
                <div class="shop-name">فرۆشگا</div>
                <div class="receipt-meta">پسوڵەی گەڕاندنەوە · ${formatDate(receipt.created_at)}</div>
            </div>
            <div class="receipt-lines">${lines}</div>
            <div class="pos-summary-row total">
                <span>کۆی گەڕاندنەوە</span>
                <span>${formatMoney(receipt.total_refund)}</span>
            </div>
        </div>`;
    }

    function showReceiptDialog(receipt) {
        const overlay = Modal.open(
            `
            <div class="modal-header">
                <h2>گەڕاندنەوە سەرکەوتوو بوو</h2>
                <img class="icon" src="assets/icons/check-circle.svg" alt="" style="color: var(--color-primary)" />
            </div>
            ${buildReceiptHtml(receipt)}
            <div class="modal-actions">
                <button class="btn btn-outline" id="receipt-close-btn">داخستن</button>
                <button class="btn btn-accent" id="receipt-print-btn">
                    <img class="icon" src="assets/icons/printer.svg" alt="" /> چاپکردن
                </button>
            </div>
            `,
            { wide: false }
        );
        overlay.querySelector('#receipt-close-btn').addEventListener('click', () => Modal.close(overlay));
        overlay.querySelector('#receipt-print-btn').addEventListener('click', () => window.print());
    }

    async function handleCompleteReturn() {
        if (returnList.length === 0) {
            Toast.warn('لیستی گەڕاندنەوە بەتاڵە');
            return;
        }
        const btn = el('returns-complete-btn');
        btn.disabled = true;
        try {
            const items = returnList.map((i) => ({
                product_id: i.product_id,
                quantity: i.quantity,
                refund_amount: i.refund_amount,
            }));
            const receipt = await Api.call('create_customer_return', items);
            returnList = [];
            renderList();
            showReceiptDialog(receipt);
            Toast.success('گەڕاندنەوەکە تۆمار کرا');
        } catch (err) {
            Toast.error(err.message);
        } finally {
            btn.disabled = false;
            ScannerFocus.refocus();
        }
    }

    function init() {
        returnList = [];
        const barcodeInput = el('returns-barcode-input');
        ScannerFocus.bind(barcodeInput);
        NumericInput.bind(barcodeInput);

        barcodeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                clearTimeout(barcodeDebounceTimer);
                handleBarcodeSubmit();
            }
        });
        barcodeInput.addEventListener('input', () => {
            clearTimeout(barcodeDebounceTimer);
            const val = barcodeInput.value.trim();
            if (val.length >= 6) {
                barcodeDebounceTimer = setTimeout(handleBarcodeSubmit, 80);
            }
        });

        el('returns-body').addEventListener('input', handleListInput);
        el('returns-body').addEventListener('click', handleListClick);
        el('returns-complete-btn').addEventListener('click', handleCompleteReturn);

        renderList();
    }

    function destroy() {
        ScannerFocus.unbind();
    }

    return { init, destroy };
})();
