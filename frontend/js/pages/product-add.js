const ProductAddPage = (() => {
    let existingProduct = null; // set when the scanned/entered barcode matches an existing product
    let barcodeDebounceTimer = null;

    function el(id) {
        return document.getElementById(id);
    }

    function resetForm() {
        existingProduct = null;
        document.getElementById('add-product-form').reset();
        el('add-barcode-input').value = '';
        el('existing-product-banner').classList.add('hidden');
        el('existing-batches-preview').classList.add('hidden');
        el('add-product-submit-label').textContent = 'زیادکردنی کاڵا';
        el('f-sale-price').disabled = false;
        el('f-name').disabled = false;
        el('f-category').disabled = false;
        el('f-unit').disabled = false;
        el('f-min-stock').disabled = false;
    }

    function applyExistingProduct(product) {
        existingProduct = product;
        el('existing-product-banner').classList.remove('hidden');
        el('add-product-submit-label').textContent = 'زیادکردنی بەچی نوێ';

        el('f-name').value = product.name;
        el('f-category').value = product.category || '';
        el('f-unit').value = product.unit || '';
        el('f-sale-price').value = product.sale_price;
        el('f-min-stock').value = product.min_stock;
        el('f-purchase-price').value = '';
        el('f-quantity').value = '';
        el('f-expiry-date').value = '';

        const isAdmin = State.isAdmin();
        el('f-sale-price').disabled = !isAdmin;

        const preview = el('existing-batches-preview');
        if (product.batches && product.batches.length > 0) {
            preview.innerHTML =
                '<label>بەچە چالاکەکان</label>' +
                product.batches
                    .map(
                        (b) => `
                <div class="batch-chip">
                    <span>نرخی کڕین: ${formatMoney(b.purchase_price)}</span>
                    <span>بڕ: ${formatNumber(b.quantity)}</span>
                    <span>بەسەرچوون: ${b.expiry_date || '-'}</span>
                </div>`
                    )
                    .join('');
            preview.classList.remove('hidden');
        } else {
            preview.classList.add('hidden');
        }
    }

    async function lookupBarcode(barcode) {
        if (!barcode) {
            if (existingProduct) resetForm();
            return;
        }
        try {
            const product = await Api.call('find_product_by_barcode', barcode);
            if (product) {
                applyExistingProduct(product);
            } else if (existingProduct) {
                resetForm();
                el('add-barcode-input').value = barcode;
            }
        } catch (err) {
            Toast.error(err.message);
        }
    }

    async function handleGenerateBarcode() {
        try {
            const barcode = await Api.call('generate_barcode');
            el('add-barcode-input').value = barcode;
            resetForm();
            el('add-barcode-input').value = barcode;
        } catch (err) {
            Toast.error(err.message);
        }
    }

    async function handleSubmit(e) {
        e.preventDefault();
        const btn = el('add-product-submit-btn');
        btn.disabled = true;
        try {
            if (existingProduct) {
                const purchasePrice = parseInt(el('f-purchase-price').value, 10);
                const quantity = parseInt(el('f-quantity').value, 10);
                const expiryDate = el('f-expiry-date').value || null;
                if (isNaN(purchasePrice) || isNaN(quantity)) {
                    Toast.warn('نرخی کڕین و بڕ پێویستە');
                    return;
                }
                await Api.call('add_stock_batch', existingProduct.id, purchasePrice, quantity, expiryDate);

                const updatePayload = {
                    name: el('f-name').value.trim(),
                    category: el('f-category').value.trim() || null,
                    unit: el('f-unit').value.trim() || null,
                    min_stock: parseInt(el('f-min-stock').value, 10) || 0,
                };
                if (State.isAdmin()) {
                    updatePayload.sale_price = parseInt(el('f-sale-price').value, 10);
                }
                await Api.call('update_product', existingProduct.id, updatePayload);
                Toast.success('بەچی نوێ زیادکرا');
            } else {
                const payload = {
                    name: el('f-name').value.trim(),
                    barcode: el('add-barcode-input').value.trim() || null,
                    category: el('f-category').value.trim() || null,
                    sale_price: parseInt(el('f-sale-price').value, 10),
                    unit: el('f-unit').value.trim() || null,
                    min_stock: parseInt(el('f-min-stock').value, 10) || 0,
                    purchase_price: parseInt(el('f-purchase-price').value, 10),
                    quantity: parseInt(el('f-quantity').value, 10),
                    expiry_date: el('f-expiry-date').value || null,
                };
                await Api.call('create_product', payload);
                Toast.success('کاڵا زیادکرا');
            }
            resetForm();
            ScannerFocus.refocus();
        } catch (err) {
            Toast.error(err.message);
        } finally {
            btn.disabled = false;
        }
    }

    function init() {
        const barcodeInput = el('add-barcode-input');
        ScannerFocus.bind(barcodeInput);
        NumericInput.bind(barcodeInput);
        NumericInput.bind(el('f-sale-price'));
        NumericInput.bind(el('f-min-stock'));
        NumericInput.bind(el('f-purchase-price'));
        NumericInput.bind(el('f-quantity'));

        barcodeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(barcodeDebounceTimer);
                lookupBarcode(barcodeInput.value.trim());
            }
        });
        barcodeInput.addEventListener('input', () => {
            clearTimeout(barcodeDebounceTimer);
            const val = barcodeInput.value.trim();
            if (val.length >= 6) {
                barcodeDebounceTimer = setTimeout(() => lookupBarcode(val), 150);
            }
        });

        el('generate-barcode-btn').addEventListener('click', handleGenerateBarcode);
        el('add-product-form').addEventListener('submit', handleSubmit);
        el('add-product-reset-btn').addEventListener('click', () => {
            resetForm();
            ScannerFocus.refocus();
        });

        resetForm();
    }

    function destroy() {
        ScannerFocus.unbind();
    }

    return { init, destroy };
})();
