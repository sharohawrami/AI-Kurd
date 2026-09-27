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

    // Broken/missing images fall back to the generated cover
    document.querySelectorAll('.cover img').forEach(img => {
        img.addEventListener('error', () => {
            img.style.display = 'none';
            const fb = img.parentElement.querySelector('.cover-fallback');
            if (fb) fb.style.display = 'grid';
        });
    });
})();
