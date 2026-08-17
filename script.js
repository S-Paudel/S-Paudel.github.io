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

// Footer year
const yearEl = document.getElementById('year');
if (yearEl) yearEl.textContent = new Date().getFullYear();

// Gentle reveal-on-scroll for specimen cards and publications
const revealTargets = document.querySelectorAll('.specimen, .pub-list li');
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
  }, { threshold: 0.15 });
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
