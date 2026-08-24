const ProductListPage = (() => {
    let allProducts = [];

    function el(id) {
        return document.getElementById(id);
    }

    function populateCategoryFilter() {
        const select = el('products-list-category-filter');
        const current = select.value;
        const categories = Array.from(
            new Set(allProducts.map((p) => p.category).filter((c) => c))
        ).sort((a, b) => a.localeCompare(b, 'ar'));

        select.innerHTML =
            '<option value="">هەموو هاوپۆلەکان</option>' +
            categories.map((c) => `<option value="${c}">${c}</option>`).join('');

        if (categories.includes(current)) {
            select.value = current;
        }
    }

    function renderProductList(filterText = '', categoryFilter = '') {
        const body = el('products-list-body');
        const filtered = allProducts.filter((p) => {
            const matchesText =
                !filterText ||
                p.name.includes(filterText) ||
                (p.barcode && p.barcode.includes(filterText)) ||
                (p.category && p.category.includes(filterText));
            const matchesCategory = !categoryFilter || p.category === categoryFilter;
            return matchesText && matchesCategory;
        });

        if (filtered.length === 0) {
            body.innerHTML = `<tr><td colspan="6" class="text-center text-muted">هیچ کاڵایەک نییە</td></tr>`;
            return;
        }

        body.innerHTML = filtered
            .map((p) => {
                const low = p.stock_qty <= p.min_stock;
                return `
                <tr data-id="${p.id}">
                    <td class="text-bold">${p.name}</td>
                    <td>${p.barcode || '-'}</td>
                    <td>${p.category || '-'}</td>
                    <td>${formatMoney(p.sale_price)}</td>
                    <td class="${low ? 'stock-low' : ''}">${formatNumber(p.stock_qty)}${low ? ' ⚠' : ''}</td>
                    <td>
                        <button class="btn btn-ghost btn-sm edit-product-btn" data-id="${p.id}">
                            <img class="icon icon-sm" src="assets/icons/pencil-square.svg" alt="" /> دەستکاری
                        </button>
                    </td>
                </tr>`;
            })
            .join('');
    }

    function currentFilters() {
        return {
            filterText: el('products-list-search').value.trim(),
            categoryFilter: el('products-list-category-filter').value,
        };
    }

    async function loadProductList() {
        try {
            allProducts = await Api.call('list_products');
            populateCategoryFilter();
            const { filterText, categoryFilter } = currentFilters();
            renderProductList(filterText, categoryFilter);
        } catch (err) {
            Toast.error(err.message);
        }
    }

    function batchListHtml(batches) {
        if (!batches || batches.length === 0) {
            return '<p class="text-muted">هیچ بەچێکی چالاک نییە</p>';
        }
        return `<div class="batch-list">${batches
            .map(
                (b) => `
            <div class="batch-chip">
                <span>نرخی کڕین: ${formatMoney(b.purchase_price)}</span>
                <span>بڕ: ${formatNumber(b.quantity)}</span>
                <span>بەسەرچوون: ${b.expiry_date || '-'}</span>
            </div>`
            )
            .join('')}</div>`;
    }

    async function openViewBatchesModal(productId) {
        try {
            const product = await Api.call('get_product_detail', productId);
            const overlay = Modal.open(
                `
                <div class="modal-header"><h2>${product.name}</h2></div>
                <div class="product-form-grid product-detail-grid">
                    <div class="form-group"><label>بارکۆد</label><span>${product.barcode || '-'}</span></div>
                    <div class="form-group"><label>هاوپۆل</label><span>${product.category || '-'}</span></div>
                    <div class="form-group"><label>یەکە</label><span>${product.unit || '-'}</span></div>
                    <div class="form-group"><label>نرخی فرۆشتن</label><span>${formatMoney(product.sale_price)}</span></div>
                    <div class="form-group"><label>کەمترین بڕی کۆگا</label><span>${formatNumber(product.min_stock)}</span></div>
                </div>
                <label>بەچە چالاکەکان</label>
                ${batchListHtml(product.batches)}
                <div class="modal-actions">
                    <button class="btn btn-outline" id="view-batches-close">داخستن</button>
                </div>
            `,
                { wide: true }
            );
            overlay.querySelector('#view-batches-close').addEventListener('click', () => {
                Modal.close(overlay);
            });
        } catch (err) {
            Toast.error(err.message);
        }
    }

    async function openEditProductModal(productId) {
        try {
            const product = await Api.call('get_product_detail', productId);
            const isAdmin = State.isAdmin();
            const overlay = Modal.open(
                `
                <div class="modal-header"><h2>دەستکاری کاڵا</h2></div>
                <div class="product-form-grid">
                    <div class="form-group">
                        <label>ناوی کاڵا</label>
                        <input type="text" id="edit-name" value="${product.name}" />
                    </div>
                    <div class="form-group">
                        <label>بارکۆد</label>
                        <input type="text" id="edit-barcode" value="${product.barcode || ''}" />
                    </div>
                    <div class="form-group">
                        <label>هاوپۆل</label>
                        <input type="text" id="edit-category" value="${product.category || ''}" />
                    </div>
                    <div class="form-group">
                        <label>یەکە</label>
                        <input type="text" id="edit-unit" value="${product.unit || ''}" />
                    </div>
                    <div class="form-group">
                        <label>کەمترین بڕی کۆگا</label>
                        <input type="number" id="edit-min-stock" min="0" value="${product.min_stock}" />
                    </div>
                    ${
                        isAdmin
                            ? `<div class="form-group">
                        <label>نرخی فرۆشتن (د.ع)</label>
                        <input type="number" id="edit-sale-price" min="0" value="${product.sale_price}" />
                    </div>`
                            : ''
                    }
                </div>
                <div class="modal-actions">
                    <button class="btn btn-outline" id="edit-product-cancel">پاشگەزبوونەوە</button>
                    <button class="btn btn-primary" id="edit-product-save">پاشەکەوتکردن</button>
                </div>
            `,
                { wide: true }
            );

            overlay.querySelector('#edit-product-cancel').addEventListener('click', () => {
                Modal.close(overlay);
            });
            overlay.querySelector('#edit-product-save').addEventListener('click', async () => {
                const saveBtn = overlay.querySelector('#edit-product-save');
                saveBtn.disabled = true;
                try {
                    const payload = {
                        name: overlay.querySelector('#edit-name').value.trim(),
                        barcode: overlay.querySelector('#edit-barcode').value.trim() || null,
                        category: overlay.querySelector('#edit-category').value.trim() || null,
                        unit: overlay.querySelector('#edit-unit').value.trim() || null,
                        min_stock: parseInt(overlay.querySelector('#edit-min-stock').value, 10) || 0,
                    };
                    if (isAdmin) {
                        payload.sale_price = parseInt(overlay.querySelector('#edit-sale-price').value, 10);
                    }
                    await Api.call('update_product', productId, payload);
                    Toast.success('کاڵا نوێکرایەوە');
                    Modal.close(overlay);
                    await loadProductList();
                } catch (err) {
                    Toast.error(err.message);
                } finally {
                    saveBtn.disabled = false;
                }
            });
        } catch (err) {
            Toast.error(err.message);
        }
    }

    function handleTableClick(e) {
        const editBtn = e.target.closest('.edit-product-btn');
        if (editBtn) {
            openEditProductModal(parseInt(editBtn.dataset.id, 10));
            return;
        }
        const row = e.target.closest('tr[data-id]');
        if (row) {
            openViewBatchesModal(parseInt(row.dataset.id, 10));
        }
    }

    function init() {
        el('products-list-search').addEventListener('input', () => {
            const { filterText, categoryFilter } = currentFilters();
            renderProductList(filterText, categoryFilter);
        });
        el('products-list-category-filter').addEventListener('change', () => {
            const { filterText, categoryFilter } = currentFilters();
            renderProductList(filterText, categoryFilter);
        });
        el('products-list-body').addEventListener('click', handleTableClick);

        loadProductList();
    }

    function destroy() {}

    return { init, destroy };
})();
