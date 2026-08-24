// Digit-only input handling that works regardless of the OS keyboard
// language. This app's cashiers keep their keyboard set to Kurdish Sorani,
// whose layout can (depending on Windows/browser setup) produce Arabic-Indic
// or Extended Arabic-Indic digit glyphs for the digit-row keys, or in some
// layouts no digit glyph at all -- a Kurdish letter occupies that key
// instead. Numeric fields must still accept and store plain ASCII 0-9
// without the cashier ever switching layout. A USB barcode scanner behaves
// as a HID keyboard and goes through the exact same OS layout translation,
// so it hits the same bug and is fixed the same way.

const NumericInput = (() => {
    const ARABIC_INDIC = '٠١٢٣٤٥٦٧٨٩'; // U+0660-U+0669
    const EXTENDED_ARABIC_INDIC = '۰۱۲۳۴۵۶۷۸۹'; // U+06F0-U+06F9 (Kurdish/Persian/Urdu)

    const DIGIT_CODES = {
        Digit0: '0', Digit1: '1', Digit2: '2', Digit3: '3', Digit4: '4',
        Digit5: '5', Digit6: '6', Digit7: '7', Digit8: '8', Digit9: '9',
        Numpad0: '0', Numpad1: '1', Numpad2: '2', Numpad3: '3', Numpad4: '4',
        Numpad5: '5', Numpad6: '6', Numpad7: '7', Numpad8: '8', Numpad9: '9',
    };

    const ALLOWED_KEYS = new Set([
        'Backspace', 'Delete', 'Tab', 'Enter', 'Escape',
        'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
        'Home', 'End', 'PageUp', 'PageDown',
    ]);

    function keyToDigit(key) {
        if (key.length !== 1) return null;
        if (key >= '0' && key <= '9') return key;
        const ai = ARABIC_INDIC.indexOf(key);
        if (ai !== -1) return String(ai);
        const eai = EXTENDED_ARABIC_INDIC.indexOf(key);
        if (eai !== -1) return String(eai);
        return null;
    }

    function toEnglishDigits(str) {
        return String(str).replace(/[٠-٩۰-۹]/g, (ch) => {
            const ai = ARABIC_INDIC.indexOf(ch);
            if (ai !== -1) return String(ai);
            const eai = EXTENDED_ARABIC_INDIC.indexOf(ch);
            return eai !== -1 ? String(eai) : ch;
        });
    }

    function sanitizeDigitsOnly(str) {
        return toEnglishDigits(str).replace(/[^0-9]/g, '');
    }

    function insertText(el, text) {
        const start = el.selectionStart != null ? el.selectionStart : el.value.length;
        const end = el.selectionEnd != null ? el.selectionEnd : el.value.length;
        if (typeof el.setRangeText === 'function') {
            el.setRangeText(text, start, end, 'end');
        } else {
            el.value = el.value.slice(0, start) + text + el.value.slice(end);
            const pos = start + text.length;
            if (el.setSelectionRange) el.setSelectionRange(pos, pos);
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function handleKeydown(e) {
        if (e.isComposing) return;
        if (ALLOWED_KEYS.has(e.key)) return;
        if (e.ctrlKey || e.metaKey || e.altKey) return; // copy/paste/select-all/AltGr combos

        const fromKey = keyToDigit(e.key);
        if (fromKey !== null) {
            if (e.key >= '0' && e.key <= '9') return; // plain ASCII digit -- let it type normally
            e.preventDefault();
            insertText(e.target, fromKey);
            return;
        }

        const fromCode = DIGIT_CODES[e.code];
        if (fromCode) {
            // Active layout produced a non-digit glyph for a physical digit
            // key (a Kurdish letter fully occupies that key) -- fall back
            // to the physical key position instead of the glyph.
            e.preventDefault();
            insertText(e.target, fromCode);
            return;
        }

        if (e.key.length === 1) {
            e.preventDefault(); // block any other printable character
        }
    }

    function handlePaste(e) {
        e.preventDefault();
        const clipboard = e.clipboardData || window.clipboardData;
        const digits = sanitizeDigitsOnly(clipboard ? clipboard.getData('text') : '');
        if (digits) insertText(e.target, digits);
    }

    function handleInput(e) {
        // Last-resort cleanup for anything that bypassed keydown/paste
        // handling (autofill, drag-drop).
        const el = e.target;
        const sanitized = sanitizeDigitsOnly(el.value);
        if (sanitized !== el.value) {
            const pos = el.selectionStart != null ? el.selectionStart : sanitized.length;
            el.value = sanitized;
            const newPos = Math.min(pos, sanitized.length);
            if (el.setSelectionRange) el.setSelectionRange(newPos, newPos);
        }
    }

    function bind(el) {
        if (!el || el.dataset.numericBound === 'true') return;
        el.dataset.numericBound = 'true';
        el.setAttribute('inputmode', 'numeric');
        el.addEventListener('keydown', handleKeydown);
        el.addEventListener('paste', handlePaste);
        el.addEventListener('input', handleInput);
    }

    return { bind, toEnglishDigits, sanitizeDigitsOnly };
})();
