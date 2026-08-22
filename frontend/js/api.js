// Thin wrapper around window.pywebview.api.* that waits for the bridge to
// be ready and normalizes the {ok, data|error,message} envelope.

const Api = (() => {
    let readyPromise = null;

    function ready() {
        if (readyPromise) return readyPromise;
        readyPromise = new Promise((resolve) => {
            if (window.pywebview && window.pywebview.api) {
                resolve();
                return;
            }
            window.addEventListener('pywebviewready', () => resolve(), { once: true });
        });
        return readyPromise;
    }

    async function call(method, ...args) {
        await ready();
        const fn = window.pywebview.api[method];
        if (typeof fn !== 'function') {
            throw new Error(`Unknown API method: ${method}`);
        }
        const result = await fn(...args);
        if (result && typeof result === 'object' && 'ok' in result) {
            if (!result.ok) {
                const err = new Error(result.message || result.error || 'هەڵەیەک ڕوویدا');
                err.code = result.error;
                throw err;
            }
            return result.data;
        }
        return result;
    }

    return { call, ready };
})();
