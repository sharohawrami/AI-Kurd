// AI Kurd admin — image crop & preview, video upload preview.
// No libraries: a small canvas cropper. Pick a file → drag to position,
// zoom with the slider, choose a ratio → the cropped JPEG replaces the file
// that gets uploaded. A live "card preview" shows how it will look on the site.
(function () {
    const OUT_W = 1600;              // width of the saved image
    const RATIOS = { '16:9': 16 / 9, '16:10': 16 / 10, '4:3': 4 / 3, '1:1': 1 };

    function dataURLtoFile(dataURL, name) {
        const [head, b64] = dataURL.split(',');
        const mime = head.match(/:(.*?);/)[1];
        const bin = atob(b64);
        const arr = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
        return new File([arr], name, { type: mime });
    }

    document.querySelectorAll('.img-uploader').forEach(box => {
        const input = box.querySelector('input[type=file]');
        const editor = box.querySelector('.iu-editor');
        const canvas = box.querySelector('.iu-canvas');
        const ctx = canvas.getContext('2d');
        const zoom = box.querySelector('.iu-zoom');
        const ratioBtns = box.querySelectorAll('.iu-ratio');
        const preview = box.querySelector('.iu-preview');
        const previewTitle = box.querySelector('.iu-preview-title');
        const status = box.querySelector('.iu-status');
        const resetBtn = box.querySelector('.iu-reset');
        const form = box.closest('form');

        let img = null, original = null, ratio = RATIOS['16:10'], scale = 1, minScale = 1;
        let ox = 0, oy = 0, dragging = false, lastX = 0, lastY = 0, useOriginal = false;

        // keep the card preview title in sync with the title field
        const titleField = form?.querySelector('[name=title_en], [name=name], [name=title]');
        const syncTitle = () => { if (previewTitle) previewTitle.textContent = (titleField?.value || 'Article title').trim(); };
        titleField?.addEventListener('input', syncTitle);

        function fit() {
            const W = canvas.clientWidth || 640;
            canvas.width = W; canvas.height = Math.round(W / ratio);
            minScale = Math.max(canvas.width / img.width, canvas.height / img.height);
            scale = Math.max(scale, minScale);
            zoom.min = minScale.toFixed(3); zoom.max = (minScale * 4).toFixed(3); zoom.value = scale;
            clamp(); draw();
        }
        function clamp() {
            const w = img.width * scale, h = img.height * scale;
            ox = Math.min(0, Math.max(canvas.width - w, ox));
            oy = Math.min(0, Math.max(canvas.height - h, oy));
        }
        function draw() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, ox, oy, img.width * scale, img.height * scale);
            // rule-of-thirds guide
            ctx.strokeStyle = 'rgba(255,255,255,.18)'; ctx.lineWidth = 1;
            for (let i = 1; i < 3; i++) {
                ctx.beginPath(); ctx.moveTo(canvas.width * i / 3, 0); ctx.lineTo(canvas.width * i / 3, canvas.height); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(0, canvas.height * i / 3); ctx.lineTo(canvas.width, canvas.height * i / 3); ctx.stroke();
            }
            renderPreview();
        }
        function exportDataURL() {
            const out = document.createElement('canvas');
            out.width = OUT_W; out.height = Math.round(OUT_W / ratio);
            const k = OUT_W / canvas.width;
            out.getContext('2d').drawImage(img, ox * k, oy * k, img.width * scale * k, img.height * scale * k);
            return out.toDataURL('image/jpeg', 0.9);
        }
        let previewTimer;
        function renderPreview() {
            clearTimeout(previewTimer);
            previewTimer = setTimeout(() => {
                const pc = preview.querySelector('canvas');
                pc.width = 480; pc.height = Math.round(480 / ratio);
                const k = pc.width / canvas.width;
                pc.getContext('2d').drawImage(img, ox * k, oy * k, img.width * scale * k, img.height * scale * k);
                status.textContent = `Will be saved as ${OUT_W} × ${Math.round(OUT_W / ratio)} JPEG · drag to reposition`;
            }, 40);
        }
        function applyCrop() {
            if (!img || useOriginal) return;
            const name = (original?.name || 'image').replace(/\.[^.]+$/, '') + '-crop.jpg';
            const dt = new DataTransfer();
            dt.items.add(dataURLtoFile(exportDataURL(), name));
            input.files = dt.files;
        }

        input.addEventListener('change', () => {
            const f = input.files && input.files[0];
            if (!f || !f.type.startsWith('image/') || f.type === 'image/svg+xml' || f.type === 'image/gif') {
                editor.classList.add('hidden'); return;
            }
            original = f; useOriginal = false; resetBtn.textContent = 'Use original (no crop)';
            const url = URL.createObjectURL(f);
            img = new Image();
            img.onload = () => {
                URL.revokeObjectURL(url);
                editor.classList.remove('hidden');
                scale = 0; ox = 0; oy = 0;
                syncTitle(); fit();
            };
            img.src = url;
        });

        zoom.addEventListener('input', () => {
            const s = parseFloat(zoom.value);
            // zoom around the centre
            const cx = canvas.width / 2, cy = canvas.height / 2;
            ox = cx - (cx - ox) * (s / scale); oy = cy - (cy - oy) * (s / scale);
            scale = s; clamp(); draw();
        });
        ratioBtns.forEach(b => b.addEventListener('click', () => {
            ratioBtns.forEach(x => x.classList.remove('active')); b.classList.add('active');
            ratio = RATIOS[b.dataset.ratio]; scale = 0; ox = 0; oy = 0; fit();
        }));
        const start = (x, y) => { dragging = true; lastX = x; lastY = y; };
        const move = (x, y) => { if (!dragging) return; ox += x - lastX; oy += y - lastY; lastX = x; lastY = y; clamp(); draw(); };
        canvas.addEventListener('mousedown', e => start(e.clientX, e.clientY));
        window.addEventListener('mousemove', e => move(e.clientX, e.clientY));
        window.addEventListener('mouseup', () => dragging = false);
        canvas.addEventListener('touchstart', e => { const t = e.touches[0]; start(t.clientX, t.clientY); }, { passive: true });
        canvas.addEventListener('touchmove', e => { const t = e.touches[0]; move(t.clientX, t.clientY); e.preventDefault(); }, { passive: false });
        canvas.addEventListener('touchend', () => dragging = false);
        window.addEventListener('resize', () => { if (img && !editor.classList.contains('hidden')) fit(); });

        resetBtn.addEventListener('click', () => {
            useOriginal = !useOriginal;
            if (useOriginal) {
                const dt = new DataTransfer(); dt.items.add(original); input.files = dt.files;
                resetBtn.textContent = 'Crop again';
                status.textContent = 'The original file will be uploaded unchanged.';
                box.querySelector('.iu-stage').classList.add('opacity-40', 'pointer-events-none');
            } else {
                resetBtn.textContent = 'Use original (no crop)';
                box.querySelector('.iu-stage').classList.remove('opacity-40', 'pointer-events-none');
                draw();
            }
        });

        // Crop is applied automatically when the form is saved
        form?.addEventListener('submit', applyCrop);
    });

    // ---- video: preview the chosen file / URL before saving ----
    document.querySelectorAll('.vid-uploader').forEach(box => {
        const file = box.querySelector('input[type=file]');
        const url = box.querySelector('input[name=video]');
        const player = box.querySelector('video');
        const frame = box.querySelector('iframe');
        const info = box.querySelector('.vu-info');
        const fmt = n => n > 1e9 ? (n / 1e9).toFixed(2) + ' GB' : n > 1e6 ? (n / 1e6).toFixed(1) + ' MB' : Math.round(n / 1e3) + ' KB';
        file?.addEventListener('change', () => {
            const f = file.files && file.files[0];
            if (!f) return;
            frame.classList.add('hidden'); player.classList.remove('hidden');
            player.src = URL.createObjectURL(f);
            player.onloadedmetadata = () => {
                info.textContent = `${f.name} · ${fmt(f.size)} · ${player.videoWidth}×${player.videoHeight} · ${Math.round(player.duration)}s`;
            };
        });
        url?.addEventListener('change', () => {
            const v = url.value.trim();
            const yt = v.match(/(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)([\w-]{6,})/);
            const vm = v.match(/vimeo\.com\/(?:video\/)?(\d+)/);
            if (yt || vm) {
                player.classList.add('hidden'); frame.classList.remove('hidden');
                frame.src = yt ? `https://www.youtube-nocookie.com/embed/${yt[1]}` : `https://player.vimeo.com/video/${vm[1]}`;
                info.textContent = yt ? 'YouTube video' : 'Vimeo video';
            } else if (v) {
                frame.classList.add('hidden'); player.classList.remove('hidden'); player.src = v; info.textContent = v;
            }
        });
    });
})();
