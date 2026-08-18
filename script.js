// Mobile nav toggle
const navToggle = document.getElementById('navToggle');
const navMenu = document.querySelector('.site-nav nav');
if (navToggle && navMenu) {
  navToggle.addEventListener('click', () => {
    const isOpen = navMenu.classList.toggle('open');
    navToggle.setAttribute('aria-expanded', isOpen);
  });
  navMenu.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      navMenu.classList.remove('open');
      navToggle.setAttribute('aria-expanded', 'false');
    });
  });
}

// Highlight the current page in the nav (works across index.html, professional.html, community.html, blogs.html)
(function highlightActiveNav(){
  const links = document.querySelectorAll('.site-nav nav a[href]');
  const path = window.location.pathname.split('/').pop() || 'index.html';
  links.forEach(link => {
    const href = link.getAttribute('href').split('/').pop();
    if (href === path || (path === '' && href === 'index.html')) {
      link.classList.add('active');
    }
  });
})();

// Footer year
const yearEl = document.getElementById('year');
if (yearEl) yearEl.textContent = new Date().getFullYear();

// Gentle reveal-on-scroll for specimen cards, publications, blog cards, teasers
const revealTargets = document.querySelectorAll('.specimen, .pub-list li, .blog-card, .teaser-card');
if ('IntersectionObserver' in window) {
  revealTargets.forEach(el => { el.style.opacity = 0; el.style.transform = 'translateY(10px)'; el.style.transition = 'opacity 0.5s ease, transform 0.5s ease'; });
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = 1;
        entry.target.style.transform = 'translateY(0)';
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  revealTargets.forEach(el => io.observe(el));
}

// If the CV file hasn't been uploaded yet, don't send visitors to a 404 silently
const cvLink = document.getElementById('cvLink');
if (cvLink) {
  cvLink.addEventListener('click', async (e) => {
    try {
      const res = await fetch(cvLink.getAttribute('href'), { method: 'HEAD' });
      if (!res.ok) throw new Error('missing');
    } catch (err) {
      e.preventDefault();
      alert('CV not uploaded yet — add Sulav_Paudel_CV.pdf to the assets folder in the repo.');
    }
  });
}

// ===========================================================
// Blog list rendering — only runs on blogs.html (needs blogs-data.js loaded first)
// ===========================================================
(function renderBlogs(){
  const grid = document.getElementById('blogGrid');
  if (!grid || typeof BLOG_POSTS === 'undefined') return;

  const filterBar = document.getElementById('blogFilter');
  const kinds = ['All', ...new Set(BLOG_POSTS.map(p => p.kind))];

  function draw(kind){
    grid.innerHTML = '';
    const posts = BLOG_POSTS
      .filter(p => kind === 'All' || p.kind === kind)
      .sort((a, b) => new Date(b.date) - new Date(a.date));

    if (posts.length === 0) {
      grid.innerHTML = '<p class="blog-empty">Nothing here yet.</p>';
      return;
    }

    posts.forEach(post => {
      const card = document.createElement('a');
      card.className = 'blog-card';
      card.href = post.url;
      card.target = '_blank';
      card.rel = 'noopener';
      card.innerHTML = `
        <span class="blog-kind">${post.kind}</span>
        <h3>${post.title}</h3>
        <p>${post.excerpt}</p>
        <span class="blog-meta">${post.source} · ${new Date(post.date).toLocaleDateString('en-NZ', { year: 'numeric', month: 'short' })}</span>
      `;
      grid.appendChild(card);
    });
  }

  if (filterBar) {
    kinds.forEach(kind => {
      const btn = document.createElement('button');
      btn.textContent = kind;
      if (kind === 'All') btn.classList.add('active');
      btn.addEventListener('click', () => {
        filterBar.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        draw(kind);
      });
      filterBar.appendChild(btn);
    });
  }

  draw('All');
})();
