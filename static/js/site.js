// AI Kurd — shared UI behaviour (header, menu, language, reveal, progress)
(function () {
    const header = document.getElementById('site-header');
    const progress = document.getElementById('scroll-progress');
    const menuBtn = document.getElementById('mobile-menu-btn');
    const menu = document.getElementById('mobile-menu');

    // Header state + reading progress
    function onScroll() {
        const y = window.scrollY || document.documentElement.scrollTop;
        header?.classList.toggle('is-scrolled', y > 12);
        if (progress) {
            const h = document.documentElement.scrollHeight - window.innerHeight;
            progress.style.width = (h > 0 ? Math.min(100, (y / h) * 100) : 0) + '%';
        }
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    // Mobile menu
    menuBtn?.addEventListener('click', () => {
        const open = menu.classList.toggle('open');
        menuBtn.setAttribute('aria-expanded', open);
        document.getElementById('icon-open')?.classList.toggle('hidden', open);
        document.getElementById('icon-close')?.classList.toggle('hidden', !open);
    });

    // Language toggle (persisted)
    function applyLang(ku) {
        document.body.classList.toggle('lang-ku', ku);
        document.documentElement.lang = ku ? 'ckb' : 'en';
        document.documentElement.dir = ku ? 'rtl' : 'ltr';
    }
    function toggleLang() {
        const ku = !document.body.classList.contains('lang-ku');
        applyLang(ku);
        try { localStorage.setItem('aikurd-lang', ku ? 'ku' : 'en'); } catch (e) {}
    }
    try { if (localStorage.getItem('aikurd-lang') === 'ku') applyLang(true); } catch (e) {}
    document.querySelectorAll('[data-lang-toggle]').forEach(b => b.addEventListener('click', toggleLang));

    // Reveal on scroll
    const io = new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if (e.isIntersecting) { e.target.classList.add('visible'); io.unobserve(e.target); }
        });
    }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });
    document.querySelectorAll('.reveal, .reveal-stagger').forEach(el => io.observe(el));

    // Background scenes: crossfade through them as the page scrolls, with a light parallax
    const scenes = document.querySelectorAll('.scene');
    if (scenes.length) {
        let current = 0;
        const update = () => {
            const y = window.scrollY;
            const h = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
            const idx = Math.min(scenes.length - 1, Math.floor((y / h) * scenes.length));
            if (idx !== current) {
                scenes[current].classList.remove('active');
                scenes[idx].classList.add('active');
                current = idx;
            }
            document.querySelector('.scenes').style.setProperty('--parallax', (-(y % (h / scenes.length)) * 0.06).toFixed(1) + 'px');
        };
        window.addEventListener('scroll', update, { passive: true });
        update();
    }

    // PS5-style hover: the hovered card's picture fills the page background
    const hoverBg = document.getElementById('hover-bg');
    const fine = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    if (hoverBg && fine) {
        const img = hoverBg.querySelector('img');
        let hideTimer, token = 0;
        document.querySelectorAll('[data-hover-bg]').forEach(el => {
            el.addEventListener('mouseenter', () => {
                clearTimeout(hideTimer);
                const src = el.dataset.hoverBg;
                if (!src) return;
                const my = ++token;
                const pre = new Image();
                pre.onload = () => {
                    if (my !== token) return;
                    img.src = src;
                    hoverBg.classList.add('show');
                    document.body.classList.add('has-hover-bg');
                };
                pre.src = src;
            });
            el.addEventListener('mouseleave', () => {
                token++;
                hideTimer = setTimeout(() => { hoverBg.classList.remove('show'); document.body.classList.remove('has-hover-bg'); }, 120);
            });
        });
    }

    // Broken/missing images fall back to the generated cover
    document.querySelectorAll('.cover img').forEach(img => {
        img.addEventListener('error', () => {
            img.style.display = 'none';
            const fb = img.parentElement.querySelector('.cover-fallback');
            if (fb) fb.style.display = 'grid';
        });
    });
})();
