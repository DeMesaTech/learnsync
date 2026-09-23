(function () {
    function getProgressBar() {
        let bar = document.querySelector('.file-transfer-progress');
        if (bar) return bar;

        bar = document.createElement('div');
        bar.className = 'file-transfer-progress';
        bar.setAttribute('role', 'progressbar');
        bar.setAttribute('aria-live', 'polite');
        bar.innerHTML = '<div class="file-transfer-progress-label"></div><div class="file-transfer-progress-track"><span></span></div>';
        document.body.appendChild(bar);
        return bar;
    }

    function updateProgress(label, percent) {
        const bar = getProgressBar();
        bar.classList.add('is-active');
        bar.querySelector('.file-transfer-progress-label').textContent = label;
        bar.querySelector('span').style.width = `${Math.max(0, Math.min(100, percent))}%`;
    }

    function finishProgress() {
        const bar = document.querySelector('.file-transfer-progress');
        if (!bar) return;
        bar.querySelector('span').style.width = '100%';
        window.setTimeout(() => bar.classList.remove('is-active'), 250);
    }

    function responseFromXhr(xhr) {
        return {
            ok: xhr.status >= 200 && xhr.status < 300,
            status: xhr.status,
            async json() { return JSON.parse(xhr.responseText); },
            async text() { return xhr.responseText; }
        };
    }

    async function upload(url, formData, options = {}) {
        const label = options.label || 'Uploading file...';
        updateProgress(label, 0);

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open(options.method || 'POST', url);
            xhr.upload.addEventListener('progress', event => {
                if (event.lengthComputable) updateProgress(label, (event.loaded / event.total) * 100);
            });
            xhr.addEventListener('load', () => {
                updateProgress(label, 100);
                finishProgress();
                resolve(responseFromXhr(xhr));
            });
            xhr.addEventListener('error', () => {
                finishProgress();
                reject(new Error('The file upload could not be completed.'));
            });
            xhr.addEventListener('abort', () => {
                finishProgress();
                reject(new Error('The file upload was cancelled.'));
            });
            xhr.send(formData);
        });
    }

    async function request(label, requestFactory) {
        updateProgress(label, 10);
        try {
            updateProgress(label, 35);
            return await requestFactory();
        } finally {
            updateProgress(label, 100);
            finishProgress();
        }
    }

    async function download(url, targetWindow) {
        updateProgress('Downloading file...', 0);
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Download failed: HTTP ${response.status}`);

            const total = Number(response.headers.get('content-length')) || 0;
            const reader = response.body?.getReader();
            if (!reader) {
                const blob = await response.blob();
                openBlob(blob, targetWindow);
                finishProgress();
                return;
            }

            const chunks = [];
            let received = 0;
            while (true) {
                const result = await reader.read();
                if (result.done) break;
                chunks.push(result.value);
                received += result.value.length;
                updateProgress('Downloading file...', total ? (received / total) * 100 : 50);
            }

            const blob = new Blob(chunks);
            openBlob(blob, targetWindow);
            finishProgress();
        } catch (error) {
            if (targetWindow && !targetWindow.closed) targetWindow.close();
            finishProgress();
            alert(error.message || 'The file download could not be completed.');
        }
    }

    function openBlob(blob, targetWindow) {
        const objectUrl = URL.createObjectURL(blob);
        if (targetWindow && !targetWindow.closed) {
            targetWindow.location.href = objectUrl;
        } else {
            window.location.href = objectUrl;
        }
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    }

    document.addEventListener('click', event => {
        const link = event.target.closest('a[href]');
        if (!link || link.dataset.transferHandled === 'true') return;

        const url = new URL(link.href, window.location.href);
        if (!url.pathname.startsWith('/uploads/')) return;

        event.preventDefault();
        link.dataset.transferHandled = 'true';
        const targetWindow = link.target === '_blank' ? window.open('', '_blank') : null;
        download(url.href, targetWindow);
    });

    window.fileTransfer = {
        upload,
        request,
        download,
        start: updateProgress,
        progress: updateProgress,
        finish: finishProgress
    };
})();
