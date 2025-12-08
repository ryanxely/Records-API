// Helper to attach file previews for images and links inside a container.
// Usage: call attachFilePreviews(containerElement) after the container's innerHTML is set.
(function () {
    window.attachFilePreviews = async function (container) {
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





let selectedFilesData = [];

// ===== Utilitaires =====

/**
 * Convertit une URL de données en Blob
 */
function dataURLToBlob(dataURL) {
    const parts = dataURL.split(',');
    const mime = parts[0].match(/:(.*?);/)[1];
    const bstr = atob(parts[1]);
    let n = bstr.length;
    const u8arr = new Uint8Array(n);
    while (n--) {
        u8arr[n] = bstr.charCodeAt(n);
    }
    return new Blob([u8arr], { type: mime });
}

/**
 * Formate la taille du fichier
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Octets';
    const k = 1024;
    const sizes = ['Octets', 'Ko', 'Mo', 'Go'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Obtient l'icône pour un type de fichier
 */
function getFileIcon(type) {
    if (type.startsWith('image/')) return '🖼️';
    if (type.startsWith('video/')) return '🎥';
    if (type.startsWith('audio/')) return '🎵';
    if (type.includes('pdf')) return '📄';
    if (type.includes('word') || type.includes('document')) return '📝';
    if (type.includes('sheet') || type.includes('excel')) return '📊';
    if (type.includes('presentation') || type.includes('powerpoint')) return '📽️';
    if (type.includes('zip') || type.includes('rar') || type.includes('compressed')) return '🗜️';
    if (type.includes('text')) return '📃';
    return '📎';
}

/**
 * Crée un élément de prévisualisation pour un fichier
 */
function createPreviewElement(fileData, index) {
    const item = document.createElement('div');
    item.className = 'preview-item';

    const removeBtn = document.createElement('button');
    removeBtn.className = 'preview-item-remove';
    removeBtn.innerHTML = '×';
    removeBtn.onclick = (e) => {
        e.stopPropagation();
        removeFile(index);
    };

    if (fileData.type.startsWith('image/')) {
        const img = document.createElement('img');
        img.src = fileData.data;
        img.alt = fileData.name;
        item.appendChild(img);
    } else if (fileData.type.startsWith('video/')) {
        const video = document.createElement('video');
        video.src = fileData.data;
        video.controls = false;
        video.muted = true;
        item.appendChild(video);
    } else {
        const fileDiv = document.createElement('div');
        fileDiv.className = 'preview-item-file';

        const icon = document.createElement('div');
        icon.className = 'preview-item-file-icon';
        icon.textContent = getFileIcon(fileData.type);

        const name = document.createElement('div');
        name.className = 'preview-item-file-name';
        name.textContent = fileData.name;

        fileDiv.appendChild(icon);
        fileDiv.appendChild(name);
        item.appendChild(fileDiv);
    }

    const info = document.createElement('div');
    info.className = 'preview-item-info';
    info.textContent = formatFileSize(fileData.size);
    item.appendChild(info);

    item.appendChild(removeBtn);

    return item;
}

/**
 * Supprime un fichier de la sélection
 */
function removeFile(index) {
    selectedFilesData.splice(index, 1);
    updatePreview();
}

/**
 * Met à jour l'affichage de la prévisualisation
 */
function updatePreview() {
    const previewEl = document.getElementById('preview');
    if (!previewEl) return;

    previewEl.innerHTML = '';
    selectedFilesData.forEach((fileData, index) => {
        const element = createPreviewElement(fileData, index);
        previewEl.appendChild(element);
    });

    let attachment_content = document.querySelector('#attachments-content')
    attachment_content.style.maxHeight = attachment_content.scrollHeight + 'px'

}

/**
 * Lit les fichiers sélectionnés
 */
async function readFiles(files) {
    const readers = Array.from(files).map(file => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve({
                name: file.name,
                type: file.type,
                data: reader.result,
                size: file.size
            });
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    });

    try {
        const filesData = await Promise.all(readers);
        // Ajouter les nouveaux fichiers aux fichiers existants
        selectedFilesData.push(...filesData);
        updatePreview();
    } catch (err) {
        console.error('Erreur lors de la lecture des fichiers:', err);
        showStatus('Erreur lors de la lecture des fichiers', true);
    }
}

