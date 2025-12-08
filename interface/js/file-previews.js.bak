// Helper to attach file previews for images and links inside a container.
// Usage: call attachFilePreviews(containerElement) after the container's innerHTML is set.
(function(){
    window.attachFilePreviews = async function(container) {
        try {
            const apiKey = typeof getApiKey === 'function' ? getApiKey('reports') : null;
            const authToken = typeof getAuthToken === 'function' ? getAuthToken() : null;
            if (!apiKey) return;

            const containerEl = (typeof container === 'string') ? document.querySelector(container) : container;
            if (!containerEl) return;

            const imgEls = containerEl.querySelectorAll('img[data-filepath]');
            for (const imgEl of imgEls) {
                const subpath = imgEl.getAttribute('data-filepath');
                if (!subpath) continue;
                const url = getApiUrl('/files/' + encodeURIComponent(subpath));
                try {
                    const headers = { 'x-api-key': apiKey };
                    if (authToken) headers['Authorization'] = 'Bearer ' + authToken;
                    const res = await fetch(url, { method: 'GET', headers });
                    if (!res.ok) continue;
                    const blob = await res.blob();
                    const objectUrl = URL.createObjectURL(blob);
                    imgEl.src = objectUrl;
                } catch (err) {
                    console.warn('Failed to load file', subpath, err);
                }
            }

            const linkEls = containerEl.querySelectorAll('a.report-file-link[data-filepath]');
            for (const linkEl of linkEls) {
                const subpath = linkEl.getAttribute('data-filepath');
                if (!subpath) continue;
                const url = getApiUrl('/files/' + encodeURIComponent(subpath));
                linkEl.href = url;
                linkEl.target = '_blank';
            }
        } catch (err) {
            console.warn('attachFilePreviews error', err);
        }
    };
})();
