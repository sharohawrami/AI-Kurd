// AI Kurd — ambient neural-network background v2.
// Glowing nodes, connection lines, drifting auroras, and light pulses
// traveling between nodes. Self-contained: just include this script.
// Honors prefers-reduced-motion and pauses in hidden tabs.

(function () {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    // ---- tune the look here ----
    const CFG = {
        nodeAlpha: 0.55,      // node brightness
        lineAlpha: 0.16,      // connection line brightness
        linkDist: 150,        // max px between connected nodes
        speed: 0.4,           // drift speed
        auroraAlpha: 0.05,    // big soft glow clouds
        pulseEvery: 900,      // ms between traveling light pulses
    };

    const canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    canvas.style.cssText =
        'position:fixed;inset:0;width:100%;height:100%;z-index:-1;pointer-events:none;';
    document.body.prepend(canvas);
    const ctx = canvas.getContext('2d');

    let W, H, nodes, auroras;
    const pulses = [];
    const mouse = { x: -9999, y: -9999 };

    function resize() {
        W = canvas.width = window.innerWidth;
        H = canvas.height = window.innerHeight;
        const count = Math.min(90, Math.floor((W * H) / 20000));
        nodes = Array.from({ length: count }, () => ({
            x: Math.random() * W,
            y: Math.random() * H,
            vx: (Math.random() - 0.5) * CFG.speed,
            vy: (Math.random() - 0.5) * CFG.speed,
            r: Math.random() * 1.8 + 1,
            pulse: Math.random() * Math.PI * 2,
        }));
        auroras = Array.from({ length: 3 }, (_, i) => ({
            x: Math.random() * W,
            y: Math.random() * H,
            r: Math.max(W, H) * (0.25 + i * 0.08),
            a: Math.random() * Math.PI * 2,
            spd: 0.0006 + i * 0.0003,
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

    // Traveling light pulses between random connected nodes
    setInterval(() => {
        if (!running || !nodes) return;
        const a = nodes[Math.floor(Math.random() * nodes.length)];
        let best = null, bestD = CFG.linkDist;
        for (const b of nodes) {
            if (b === a) continue;
            const d = Math.hypot(a.x - b.x, a.y - b.y);
            if (d < bestD) { bestD = d; best = b; }
        }
        if (best) pulses.push({ a, b: best, t: 0 });
    }, CFG.pulseEvery);

    function tick() {
        if (!running) return;
        ctx.clearRect(0, 0, W, H);

        // ---- auroras: huge, slow, soft light clouds ----
        for (const g of auroras) {
            g.a += g.spd;
            const gx = g.x + Math.cos(g.a) * W * 0.18;
            const gy = g.y + Math.sin(g.a * 0.8) * H * 0.18;
            const grad = ctx.createRadialGradient(gx, gy, 0, gx, gy, g.r);
            grad.addColorStop(0, `rgba(255,255,255,${CFG.auroraAlpha})`);
            grad.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, W, H);
        }

        // ---- move nodes ----
        for (const p of nodes) {
            const dx = mouse.x - p.x, dy = mouse.y - p.y;
            const md = Math.hypot(dx, dy);
            if (md < 220 && md > 0.001) {
                p.vx += (dx / md) * 0.015;
                p.vy += (dy / md) * 0.015;
            }
            const sp = Math.hypot(p.vx, p.vy);
            const max = CFG.speed * 1.8;
            if (sp > max) { p.vx *= max / sp; p.vy *= max / sp; }
            p.x += p.vx; p.y += p.vy;
            if (p.x < -20) p.x = W + 20; if (p.x > W + 20) p.x = -20;
            if (p.y < -20) p.y = H + 20; if (p.y > H + 20) p.y = -20;
            p.pulse += 0.025;
        }

        // ---- connection lines ----
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const a = nodes[i], b = nodes[j];
                const d = Math.hypot(a.x - b.x, a.y - b.y);
                if (d < CFG.linkDist) {
                    ctx.strokeStyle = `rgba(255,255,255,${CFG.lineAlpha * (1 - d / CFG.linkDist)})`;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                }
            }
        }

        // ---- traveling pulses ----
        for (let i = pulses.length - 1; i >= 0; i--) {
            const p = pulses[i];
            p.t += 0.025;
            if (p.t >= 1) { pulses.splice(i, 1); continue; }
            const x = p.a.x + (p.b.x - p.a.x) * p.t;
            const y = p.a.y + (p.b.y - p.a.y) * p.t;
            const fade = Math.sin(p.t * Math.PI);
            const grad = ctx.createRadialGradient(x, y, 0, x, y, 8);
            grad.addColorStop(0, `rgba(255,255,255,${0.9 * fade})`);
            grad.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(x, y, 8, 0, Math.PI * 2);
            ctx.fill();
        }

        // ---- glowing nodes ----
        for (const p of nodes) {
            const glow = CFG.nodeAlpha * (0.7 + 0.3 * Math.sin(p.pulse));
            const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
            grad.addColorStop(0, `rgba(255,255,255,${glow})`);
            grad.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r * 4, 0, Math.PI * 2);
            ctx.fill();
        }

        requestAnimationFrame(tick);
    }

    resize();
    requestAnimationFrame(tick);
})();
