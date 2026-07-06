// Kurdish Prompt Library — filtering, search, copy-to-clipboard

(function () {
    const filterBtns = document.querySelectorAll('.pfilter');
    const cards = document.querySelectorAll('.prompt-card');
    const searchInput = document.getElementById('prompt-search');
    const noPrompts = document.getElementById('no-prompts');
    const toast = document.getElementById('toast');

    let activeFilter = 'all';

    function applyFilters() {
        const q = searchInput.value.trim().toLowerCase();
        let visible = 0;
        cards.forEach(card => {
            const matchCat = activeFilter === 'all' || card.dataset.category === activeFilter;
            const matchSearch = !q || card.dataset.search.includes(q);
            const show = matchCat && matchSearch;
            card.style.display = show ? '' : 'none';
            if (show) visible++;
        });
        noPrompts.classList.toggle('hidden', visible > 0);
    }

    filterBtns.forEach(btn => btn.addEventListener('click', () => {
        filterBtns.forEach(b => {
            b.classList.remove('active', 'bg-white', 'text-black', 'border-white/40', 'font-semibold');
            b.classList.add('border-white/15', 'text-white/60');
        });
        btn.classList.add('active', 'bg-white', 'text-black', 'border-white/40', 'font-semibold');
        btn.classList.remove('border-white/15', 'text-white/60');
        activeFilter = btn.dataset.filter;
        applyFilters();
    }));

    searchInput.addEventListener('input', applyFilters);

    // Copy to clipboard with fallback
    let toastTimer;
    function showToast() {
        toast.classList.remove('translate-y-20', 'opacity-0');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.add('translate-y-20', 'opacity-0'), 2000);
    }

    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const text = btn.closest('.prompt-card').querySelector('.prompt-text').textContent.trim();
            try {
                await navigator.clipboard.writeText(text);
            } catch {
                const ta = document.createElement('textarea');
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                ta.remove();
            }
            const original = btn.textContent;
            btn.textContent = '✓ Copied';
            setTimeout(() => (btn.textContent = original), 1600);
            showToast();
        });
    });
})();
