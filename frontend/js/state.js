// Small shared client-side state: current user + in-progress sales tabs.
//
// The POS screen can have several independent sales open at once (one per
// tab, e.g. one customer's items while a second customer is served). Each
// tab holds its own cart + discount settings; State.cart/cartAdd/etc. always
// operate on the *active* tab so pos.js can keep using the same cart API it
// always has, without needing to know about tabs itself.

function makeSalesTab(id) {
    return { id, cart: [], discountMode: 'flat', discountValue: 0 };
}

const State = {
    currentUser: null,

    salesTabs: [makeSalesTab(1)],
    activeSalesTabId: 1,
    _nextSalesTabId: 2,

    activeSalesTab() {
        return this.salesTabs.find((t) => t.id === this.activeSalesTabId);
    },

    addSalesTab() {
        const tab = makeSalesTab(this._nextSalesTabId++);
        this.salesTabs.push(tab);
        this.activeSalesTabId = tab.id;
        return tab;
    },

    closeSalesTab(tabId) {
        const idx = this.salesTabs.findIndex((t) => t.id === tabId);
        if (idx === -1) return;
        this.salesTabs.splice(idx, 1);
        if (this.activeSalesTabId === tabId) {
            const next = this.salesTabs[idx] || this.salesTabs[idx - 1];
            this.activeSalesTabId = next.id;
        }
    },

    resetSalesTab(tabId) {
        const tab = this.salesTabs.find((t) => t.id === tabId);
        if (!tab) return;
        tab.cart = [];
        tab.discountMode = 'flat';
        tab.discountValue = 0;
    },

    resetAllSalesTabs() {
        this.salesTabs = [makeSalesTab(1)];
        this.activeSalesTabId = 1;
        this._nextSalesTabId = 2;
    },

    get cart() {
        return this.activeSalesTab().cart; // [{product_id, name, unit_price, quantity, available_qty}]
    },

    cartTotal() {
        return this.cart.reduce((sum, item) => sum + item.unit_price * item.quantity, 0);
    },

    cartAdd(item) {
        const existing = this.cart.find((i) => i.product_id === item.product_id);
        if (existing) {
            existing.quantity += 1;
        } else {
            this.cart.push({ ...item, quantity: 1 });
        }
    },

    cartSetQuantity(productId, quantity) {
        const item = this.cart.find((i) => i.product_id === productId);
        if (!item) return;
        if (quantity <= 0) {
            this.cartRemove(productId);
            return;
        }
        item.quantity = quantity;
    },

    cartRemove(productId) {
        this.activeSalesTab().cart = this.cart.filter((i) => i.product_id !== productId);
    },

    cartClear() {
        this.activeSalesTab().cart = [];
    },

    isAdmin() {
        return this.currentUser && this.currentUser.role === 'admin';
    },
};
