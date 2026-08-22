const PosPage = (() => {
    let discountMode = 'flat';
    let searchDebounceTimer = null;
    let barcodeDebounceTimer = null;

    function el(id) {
        return document.getElementById(id);
    }

    function renderCart() {
        const body = el('pos-cart-body');
        const empty = el('pos-cart-empty');
        const card = document.querySelector('.pos-cart-card');

        if (State.cart.length === 0) {
            body.innerHTML = '';
            empty.classList.remove('hidden');
            card.querySelector('.table-wrap').classList.add('hidden');
        } else {
            empty.classList.add('hidden');
            card.querySelector('.table-wrap').classList.remove('hidden');
            body.innerHTML = State.cart
                .map(
                    (item) => `
                <tr data-product-id="${item.product_id}">
                    <td class="cell-name">${item.name}</td>
                    <td class="cell-price">${formatMoney(item.unit_price)}</td>
                    <td>
                        <div class="qty-control">
                            <button class="btn btn-outline btn-sm qty-minus" data-id="${item.product_id}">−</button>
                            <span class="qty-value">${item.quantity}</span>
                            <button class="btn btn-outline btn-sm qty-plus" data-id="${item.product_id}">+</button>
                        </div>
                    </td>
                    <td class="cell-total">${formatMoney(item.unit_price * item.quantity)}</td>
                    <td>
                        <button class="btn btn-icon btn-ghost qty-remove" data-id="${item.product_id}" title="سڕینەوە">
                            <img class="icon icon-sm" src="assets/icons/trash.svg" alt="" />
                        </button>
                    </td>
                </tr>`
                )
                .join('');
        }
        renderTotals();
    }

    function renderTotals() {
        const subtotal = State.cartTotal();
        const discountValue = parseInt(el('discount-value').value, 10) || 0;
        let discount;
        if (discountMode === 'percent') {
            discount = Math.round((subtotal * discountValue) / 100);
        } else {
            discount = discountValue;
        }
        discount = Math.max(0, Math.min(subtotal, discount));
        const final = subtotal - discount;

        el('pos-subtotal').textContent = formatMoney(subtotal);
        el('pos-final-total').textContent = formatMoney(final);
    }

    async function addProductToCart(product) {
        if (product.available_qty !== undefined && product.available_qty <= 0) {
            Toast.warn(`کاڵای "${product.name}" لە کۆگا نەماوە`);
            return;
        }
        const existing = State.cart.find((i) => i.product_id === product.product_id);
        const nextQty = (existing ? existing.quantity : 0) + 1;
        if (product.available_qty !== undefined && nextQty > product.available_qty) {
            Toast.warn(`تەنها ${product.available_qty} دانە بەردەستە بۆ "${product.name}"`);
            return;
        }
        State.cartAdd({
            product_id: product.product_id,
            name: product.name,
            unit_price: product.sale_price,
            available_qty: product.available_qty,
        });
        renderCart();
        ScannerFocus.refocus();
    }

    async function handleBarcodeSubmit() {
        const input = el('pos-barcode-input');
        const barcode = input.value.trim();
        if (!barcode) return;
        input.value = '';
        try {
            const product = await Api.call('find_product_by_barcode', barcode);
            if (!product) {
                Toast.error('کاڵا بەم بارکۆدە نەدۆزرایەوە');
                return;
            }
            const snapshot = await Api.call('get_cart_item_snapshot', product.id);
            await addProductToCart(snapshot);
        } catch (err) {
            Toast.error(err.message);
        }
    }

    async function handleSearchInput() {
        const query = el('pos-search-input').value.trim();
        const results = el('pos-search-results');
        clearTimeout(searchDebounceTimer);
        if (!query) {
            results.classList.add('hidden');
            return;
        }
        searchDebounceTimer = setTimeout(async () => {
            try {
                const products = await Api.call('search_products', query);
                if (products.length === 0) {
                    results.innerHTML = '<div class="dropdown-item text-muted">هیچ کاڵایەک نەدۆزرایەوە</div>';
                } else {
                    results.innerHTML = products
                        .map(
                            (p) => `
                        <div class="dropdown-item" data-id="${p.id}">
                            <span class="name">${p.name}</span>
                            <span class="meta">${formatMoney(p.sale_price)} · بەردەست: ${p.stock_qty}</span>
                        </div>`
                        )
                        .join('');
                }
                results.classList.remove('hidden');
            } catch (err) {
                Toast.error(err.message);
            }
        }, 180);
    }

    async function handleSearchResultClick(e) {
        const item = e.target.closest('.dropdown-item[data-id]');
        if (!item) return;
        const productId = parseInt(item.dataset.id, 10);
        el('pos-search-input').value = '';
        el('pos-search-results').classList.add('hidden');
        try {
            const snapshot = await Api.call('get_cart_item_snapshot', productId);
            await addProductToCart(snapshot);
        } catch (err) {
            Toast.error(err.message);
        }
        ScannerFocus.refocus();
    }

    function handleCartClick(e) {
        const plus = e.target.closest('.qty-plus');
        const minus = e.target.closest('.qty-minus');
        const remove = e.target.closest('.qty-remove');
        if (plus) {
            const id = parseInt(plus.dataset.id, 10);
            const item = State.cart.find((i) => i.product_id === id);
            if (item.available_qty !== undefined && item.quantity + 1 > item.available_qty) {
                Toast.warn(`تەنها ${item.available_qty} دانە بەردەستە`);
                return;
            }
            State.cartSetQuantity(id, item.quantity + 1);
            renderCart();
        } else if (minus) {
            const id = parseInt(minus.dataset.id, 10);
            const item = State.cart.find((i) => i.product_id === id);
            State.cartSetQuantity(id, item.quantity - 1);
            renderCart();
        } else if (remove) {
            const id = parseInt(remove.dataset.id, 10);
            State.cartRemove(id);
            renderCart();
        }
        ScannerFocus.refocus();
    }

    function setDiscountMode(mode) {
        discountMode = mode;
        el('discount-mode-flat').classList.toggle('active', mode === 'flat');
        el('discount-mode-percent').classList.toggle('active', mode === 'percent');
        renderTotals();
    }

    function buildReceiptHtml(receipt) {
        const lines = receipt.items
            .map(
                (item) => `
            <div class="receipt-line">
                <span>${item.name} × ${item.quantity}</span>
                <span>${formatMoney(item.total_price)}</span>
            </div>`
            )
            .join('');

        return `
        <div id="receipt-print-area">
            <div class="receipt-header">
                <div class="shop-name">فرۆشگا</div>
                <div class="receipt-meta">پسوڵەی ژمارە ${receipt.sale_id} · ${formatDate(receipt.created_at)}</div>
            </div>
            <div class="receipt-lines">${lines}</div>
            <div class="pos-summary-row">
                <span class="text-muted">کۆی گشتی</span>
                <span>${formatMoney(receipt.total_amount)}</span>
            </div>
            <div class="pos-summary-row">
                <span class="text-muted">داشکاندن</span>
                <span>${formatMoney(receipt.discount)}</span>
            </div>
            <div class="pos-summary-row total">
                <span>کۆی کۆتایی</span>
                <span>${formatMoney(receipt.final_amount)}</span>
            </div>
        </div>`;
    }

    function showReceiptDialog(receipt) {
        const overlay = Modal.open(
            `
            <div class="modal-header">
                <h2>فرۆشتن سەرکەوتوو بوو</h2>
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

    async function handleCompleteSale() {
        if (State.cart.length === 0) {
            Toast.warn('سەبەتە بەتاڵە');
            return;
        }
        const btn = el('pos-complete-sale-btn');
        btn.disabled = true;
        try {
            const discountValue = parseInt(el('discount-value').value, 10) || 0;
            const items = State.cart.map((i) => ({ product_id: i.product_id, quantity: i.quantity }));
            const receipt = await Api.call('complete_sale', items, discountMode, discountValue);
            State.cartClear();
            el('discount-value').value = 0;
            renderCart();
            showReceiptDialog(receipt);
        } catch (err) {
            Toast.error(err.message);
        } finally {
            btn.disabled = false;
            ScannerFocus.refocus();
        }
    }

    async function handleClearCart() {
        if (State.cart.length === 0) return;
        const confirmed = await Modal.confirm('سەبەتەکە بەتاڵ بکرێت؟');
        if (confirmed) {
            State.cartClear();
            renderCart();
        }
        ScannerFocus.refocus();
    }

    function init() {
        const barcodeInput = el('pos-barcode-input');
        ScannerFocus.bind(barcodeInput);

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

        el('pos-search-input').addEventListener('input', handleSearchInput);
        el('pos-search-results').addEventListener('click', handleSearchResultClick);
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.dropdown-wrap')) {
                const results = el('pos-search-results');
                if (results) results.classList.add('hidden');
            }
        });

        el('pos-cart-body').addEventListener('click', handleCartClick);
        el('discount-value').addEventListener('input', renderTotals);
        el('discount-mode-flat').addEventListener('click', () => setDiscountMode('flat'));
        el('discount-mode-percent').addEventListener('click', () => setDiscountMode('percent'));
        el('pos-complete-sale-btn').addEventListener('click', handleCompleteSale);
        el('pos-clear-cart-btn').addEventListener('click', handleClearCart);

        renderCart();
    }

    function destroy() {
        ScannerFocus.unbind();
    }

    return { init, destroy };
})();
