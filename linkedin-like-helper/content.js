// LinkedIn Like Helper: highlights posts from 1st-degree connections that you
// haven't liked yet. It never likes on its own — every like starts with a click.
(() => {
  'use strict';

  // LinkedIn changes its markup often; these selectors are the first thing to
  // fix when nothing gets detected.
  const POST_SEL = [
    'div[data-urn^="urn:li:activity:"]',
    'div[data-id^="urn:li:activity:"]',
    'div.feed-shared-update-v2',
  ].join(',');
  const ACTOR_SEL = '.update-components-actor, .feed-shared-actor';
  const LIKE_SEL = 'button.react-button__trigger';
  const LIKE_FALLBACK_SEL = 'button[aria-pressed][aria-label*="like" i], button[aria-pressed][aria-label*="aime" i]';
  const COMMENT_SEL = '[class*="comments-"], [class*="comment-"]';
  // Not followed by a lowercase letter: the degree is often glued to the
  // headline in textContent ("• 1erData Engineer").
  const FIRST_DEGREE = /(?:^|[\s•·])(?:1st|1er|1re)(?![a-z])/;
  const PROMOTED = /(Promoted|Sponsored|Sponsoris[ée])/i;
  const BATCH_GAP_MS = 800;
  const STATS_KEY = 'llh-stats';

  const skipped = new Set();
  let likedToday = 0;
  let batchRunning = false;
  let panel;

  // ---------- stats (likes made through the helper, per day) ----------
  const today = () => new Date().toISOString().slice(0, 10);
  const storage = globalThis.chrome?.storage?.local;

  function loadStats() {
    if (!storage) return;
    storage.get(STATS_KEY, (res) => {
      const s = res?.[STATS_KEY];
      likedToday = s?.date === today() ? s.count : 0;
      renderPanel();
    });
  }

  function countLike() {
    likedToday += 1;
    storage?.set({ [STATS_KEY]: { date: today(), count: likedToday } });
  }

  // ---------- post detection ----------
  function posts() {
    return [...document.querySelectorAll(POST_SEL)].filter(
      (el) => !el.parentElement?.closest(POST_SEL),
    );
  }

  function postId(post) {
    if (!post.dataset.llhId) {
      post.dataset.llhId = post.dataset.urn || post.dataset.id || `llh-${Math.random().toString(36).slice(2)}`;
    }
    return post.dataset.llhId;
  }

  function isConnectionPost(post) {
    const actor = post.querySelector(ACTOR_SEL);
    if (!actor) return false;
    const text = actor.textContent.replace(/\s+/g, ' ');
    return FIRST_DEGREE.test(text) && !PROMOTED.test(text);
  }

  function likeButton(post) {
    const outsideComments = (b) => !b.closest(COMMENT_SEL);
    return [...post.querySelectorAll(LIKE_SEL)].find(outsideComments)
      || [...post.querySelectorAll(LIKE_FALLBACK_SEL)].find(outsideComments)
      || null;
  }

  const isLiked = (btn) => btn.getAttribute('aria-pressed') === 'true';

  function targets() {
    return posts().filter((post) => {
      if (skipped.has(postId(post)) || !isConnectionPost(post)) return false;
      const btn = likeButton(post);
      return btn && !isLiked(btn);
    });
  }

  function isVisible(el) {
    const r = el.getBoundingClientRect();
    return r.bottom > 0 && r.top < window.innerHeight;
  }

  // ---------- actions ----------
  function like(post) {
    const btn = likeButton(post);
    if (!btn || isLiked(btn)) return false;
    btn.click();
    countLike();
    setTimeout(scan, 300);
    return true;
  }

  async function likeVisible() {
    if (batchRunning) return;
    batchRunning = true;
    renderPanel();
    for (const post of targets().filter(isVisible)) {
      if (like(post)) await new Promise((r) => setTimeout(r, BATCH_GAP_MS));
    }
    batchRunning = false;
    scan();
  }

  function scrollToNext() {
    const next = targets().find((p) => p.getBoundingClientRect().top > 90);
    if (next) next.scrollIntoView({ behavior: 'smooth', block: 'start' });
    else window.scrollBy({ top: window.innerHeight * 0.8, behavior: 'smooth' }); // load more feed
  }

  // ---------- UI ----------
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function onClick(btn, fn) {
    btn.addEventListener('click', (e) => { e.stopPropagation(); fn(); });
    return btn;
  }

  function badgeFor(post) {
    const badge = el('div', 'llh-badge');
    badge.append(
      el('span', 'llh-badge-label'),
      onClick(el('button', 'llh-btn llh-btn-primary llh-like', '👍 Liker'), () => like(post)),
      onClick(el('button', 'llh-btn', '💬 Suggérer'), () => openSuggestions(post)),
      onClick(el('button', 'llh-btn', 'Ignorer'), () => { skipped.add(postId(post)); scan(); }),
    );
    return badge;
  }

  // Every connection post gets a badge (for suggestions); only unliked ones
  // are outlined and get the like button.
  function mark(post, connection, unliked) {
    let badge = post.querySelector(':scope > .llh-badge');
    post.classList.toggle('llh-target', unliked);
    post.classList.toggle('llh-host', connection);
    if (!connection) {
      badge?.remove();
      post.querySelector(':scope > .llh-suggest')?.remove();
      return;
    }
    if (!badge) post.prepend((badge = badgeFor(post)));
    badge.querySelector('.llh-badge-label').textContent = unliked ? 'Relation · pas encore liké' : 'Relation';
    badge.querySelector('.llh-like').hidden = !unliked;
  }

  // ---------- comment suggestions (local model, via the service worker) ----------
  const TEXT_SEL = '.update-components-text, .feed-shared-inline-show-more-text, .feed-shared-update-v2__description, .feed-shared-text';
  const EDITOR_SEL = '.ql-editor[contenteditable="true"], [contenteditable="true"][role="textbox"]';

  function postText(post) {
    const block = post.querySelector(TEXT_SEL);
    if (block) return block.innerText.trim();
    const clone = post.cloneNode(true);
    clone.querySelectorAll('.llh-badge, .llh-suggest, button').forEach((n) => n.remove());
    return clone.innerText.trim().slice(0, 3000);
  }

  function requestSuggestions(text) {
    return new Promise((resolve, reject) => {
      if (!globalThis.chrome?.runtime?.sendMessage) return reject(new Error('extension runtime unavailable'));
      chrome.runtime.sendMessage({ type: 'suggest', post: text }, (res) => {
        if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
        if (!res?.ok) return reject(new Error(res?.error || 'no response'));
        resolve(res.data.suggestions);
      });
    });
  }

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  async function insertComment(post, text) {
    let editor = post.querySelector(EDITOR_SEL);
    if (!editor) {
      const commentBtn = [...post.querySelectorAll('button')].find((b) =>
        !b.closest('.llh-badge, .llh-suggest')
        && /^(comment|commenter)\b/i.test((b.getAttribute('aria-label') || b.textContent).trim()));
      commentBtn?.click();
      for (let i = 0; i < 15 && !editor; i++) {
        await wait(200);
        editor = post.querySelector(EDITOR_SEL);
      }
    }
    if (!editor) {
      await navigator.clipboard.writeText(text);
      return 'copied';
    }
    editor.focus();
    document.execCommand('insertText', false, text); // goes through LinkedIn's editor like typing would
    return 'inserted';
  }

  async function openSuggestions(post) {
    let box = post.querySelector(':scope > .llh-suggest');
    if (!box) {
      box = el('div', 'llh-suggest');
      post.querySelector(':scope > .llh-badge').after(box);
    }
    box.replaceChildren(el('div', 'llh-suggest-status', 'Génération des suggestions…'));
    let suggestions;
    try {
      suggestions = await requestSuggestions(postText(post));
    } catch (err) {
      box.replaceChildren(
        el('div', 'llh-suggest-status llh-error', `Serveur local injoignable (${err.message}). Lance « python server.py » dans comment-model/.`),
        onClick(el('button', 'llh-btn', 'Fermer'), () => box.remove()),
      );
      return;
    }
    const list = el('div', 'llh-suggest-list');
    for (const text of suggestions) {
      const item = el('div', 'llh-suggest-item');
      const area = el('textarea', 'llh-suggest-text');
      area.value = text;
      area.rows = Math.min(6, Math.ceil(text.length / 70) + 1);
      const insertBtn = onClick(el('button', 'llh-btn llh-btn-primary', 'Insérer'), async () => {
        const how = await insertComment(post, area.value);
        insertBtn.textContent = how === 'inserted' ? 'Inséré ✓ (relis puis publie)' : 'Copié ✓ (colle-le)';
      });
      item.append(area, insertBtn);
      list.append(item);
    }
    box.replaceChildren(
      list,
      el('div', 'llh-panel-row'),
    );
    box.lastChild.append(
      onClick(el('button', 'llh-btn', '↻ Régénérer'), () => openSuggestions(post)),
      onClick(el('button', 'llh-btn', 'Fermer'), () => box.remove()),
    );
  }

  function ensurePanel() {
    if (panel) return;
    panel = el('div', 'llh-panel');
    panel.innerHTML = `
      <div class="llh-panel-title">Like Helper</div>
      <div class="llh-panel-count"></div>
      <div class="llh-panel-row">
        <button class="llh-btn" data-act="next">Suivant ↓</button>
        <button class="llh-btn llh-btn-primary" data-act="visible"></button>
      </div>
      <div class="llh-panel-today"></div>`;
    panel.querySelector('[data-act="next"]').addEventListener('click', scrollToNext);
    panel.querySelector('[data-act="visible"]').addEventListener('click', likeVisible);
    document.body.append(panel);
  }

  function renderPanel(list = targets()) {
    if (!panel) return;
    const visible = list.filter(isVisible).length;
    panel.querySelector('.llh-panel-count').textContent = `${list.length} post(s) de relations à liker`;
    const vBtn = panel.querySelector('[data-act="visible"]');
    vBtn.textContent = batchRunning ? 'En cours…' : `Liker les visibles (${visible})`;
    vBtn.disabled = batchRunning || visible === 0;
    panel.querySelector('.llh-panel-today').textContent = `Likés aujourd'hui via l'outil : ${likedToday}`;
  }

  // ---------- main loop ----------
  function scan() {
    const onFeed = location.pathname.startsWith('/feed');
    if (!onFeed) {
      panel?.remove();
      panel = null;
      posts().forEach((p) => mark(p, false, false));
      return;
    }
    ensurePanel();
    const list = targets();
    const unliked = new Set(list);
    for (const post of posts()) {
      mark(post, !skipped.has(postId(post)) && isConnectionPost(post), unliked.has(post));
    }
    renderPanel(list);
  }

  let timer;
  const scheduleScan = () => { clearTimeout(timer); timer = setTimeout(scan, 400); };

  new MutationObserver(scheduleScan).observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['aria-pressed'],
  });
  window.addEventListener('scroll', () => renderPanel(), { passive: true });

  loadStats();
  scan();
})();
