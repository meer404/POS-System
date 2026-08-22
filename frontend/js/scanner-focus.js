// Keeps a barcode input field reliably focused for a USB-HID barcode
// scanner, while cooperating with modals stealing focus intentionally.

const ScannerFocus = (() => {
    let inputEl = null;
    let paused = false;
    let blurHandler = null;
    let clickHandler = null;

    function bind(el) {
        unbind();
        inputEl = el;
        paused = false;
        inputEl.focus();

        blurHandler = () => {
            if (paused) return;
            setTimeout(() => {
                if (paused || !inputEl || !document.body.contains(inputEl)) return;
                // Don't steal focus back if it deliberately moved to another
                // interactive element (e.g. the manual search box, a modal
                // field) -- only reclaim it if focus was lost to nowhere.
                const active = document.activeElement;
                const wentToInteractive =
                    active && active !== document.body && active.closest('input, select, textarea, button, a, [contenteditable]');
                if (!wentToInteractive) {
                    inputEl.focus();
                }
            }, 50);
        };
        inputEl.addEventListener('blur', blurHandler);

        clickHandler = (e) => {
            if (paused || !inputEl) return;
            if (e.target.closest('.modal-overlay')) return;
            if (e.target.closest('button, a, input, select, textarea, .dropdown-item')) return;
            inputEl.focus();
        };
        document.addEventListener('click', clickHandler);
    }

    function unbind() {
        if (inputEl && blurHandler) inputEl.removeEventListener('blur', blurHandler);
        if (clickHandler) document.removeEventListener('click', clickHandler);
        inputEl = null;
        blurHandler = null;
        clickHandler = null;
    }

    function pause() {
        paused = true;
    }

    function resume() {
        paused = false;
        if (inputEl) inputEl.focus();
    }

    function refocus() {
        if (!paused && inputEl) inputEl.focus();
    }

    return { bind, unbind, pause, resume, refocus };
})();
