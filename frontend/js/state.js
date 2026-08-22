// Small shared client-side state: current user + in-progress cart.

const State = {
    currentUser: null,

    cart: [], // [{product_id, name, unit_price, quantity, available_qty}]

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
        this.cart = this.cart.filter((i) => i.product_id !== productId);
    },

    cartClear() {
        this.cart = [];
    },

    isAdmin() {
        return this.currentUser && this.currentUser.role === 'admin';
    },
};
