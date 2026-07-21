// AI Kurd — ambient neural-network background.
// Self-contained: creates its own canvas. Subtle white particles that
// drift, connect, and react gently to the mouse. Skips animation for
// users who prefer reduced motion, and pauses when the tab is hidden.

(function () {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    canvas.style.cssText =
        'position:fixed;inset:0;width:100%;height:100%;z-index:-1;pointer-events:none;';
    document.body.prepend(canvas);
    const ctx = canvas.getContext('2d');

    let W, H, particles;
    const mouse = { x: -9999, y: -9999 };
    const COUNT = () => Math.min(90, Math.floor((W * H) / 22000));
    const LINK_DIST = 130;

    function resize() {
        W = canvas.width = window.innerWidth;
        H = canvas.height = window.innerHeight;
        particles = Array.from({ length: COUNT() }, () => ({
            x: Math.random() * W,
            y: Math.random() * H,
            vx: (Math.random() - 0.5) * 0.35,
            vy: (Math.random() - 0.5) * 0.35,
            r: Math.random() * 1.6 + 0.6,
            pulse: Math.random() * Math.PI * 2,
        }));
    }

    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
    window.addEventListener('mouseout', () => { mouse.x = -9999; mouse.y = -9999; });

    let running = true;
    document.addEventListener('visibilitychange', () => {
        running = !document.hidden;
        if (running) requestAnimationFrame(tick);
    });

    function tick() {
        if (!running) return;
        ctx.clearRect(0, 0, W, H);

        for (const p of particles) {
            // gentle attraction toward the mouse
            const dx = mouse.x - p.x, dy = mouse.y - p.y;
            const md = Math.hypot(dx, dy);
            if (md < 200 && md > 0.001) {
                p.vx += (dx / md) * 0.012;
                p.vy += (dy / md) * 0.012;
            }
            // speed limit + drift
            const sp = Math.hypot(p.vx, p.vy);
            if (sp > 0.6) { p.vx *= 0.6 / sp; p.vy *= 0.6 / sp; }
            p.x += p.vx; p.y += p.vy;
            if (p.x < -20) p.x = W + 20; if (p.x > W + 20) p.x = -20;
            if (p.y < -20) p.y = H + 20; if (p.y > H + 20) p.y = -20;
            p.pulse += 0.02;
        }

        // connection lines
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const a = particles[i], b = particles[j];
                const d = Math.hypot(a.x - b.x, a.y - b.y);
                if (d < LINK_DIST) {
                    ctx.strokeStyle = `rgba(255,255,255,${0.09 * (1 - d / LINK_DIST)})`;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                }
            }
        }

        // dots (soft pulsing)
        for (const p of particles) {
            const glow = 0.25 + 0.2 * Math.sin(p.pulse);
            ctx.fillStyle = `rgba(255,255,255,${glow})`;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fill();
        }

        requestAnimationFrame(tick);
    }

    resize();
    requestAnimationFrame(tick);
})();
