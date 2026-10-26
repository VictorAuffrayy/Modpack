/* Per-mod chat. Expects <div id="mod-chat" data-pack data-mod data-lang> and window.CHAT_T (strings).
   Sends the conversation to /api/chat (Vercel function) and streams the answer as plain text. */
(() => {
  const mount = document.getElementById('mod-chat');
  if (!mount) return;
  const T = window.CHAT_T;
  const { pack, mod, lang } = mount.dataset;
  const KEY = `chat-${pack}-${mod}`;
  const MAX_LEN = 1500;

  let history = [];
  try { history = JSON.parse(sessionStorage.getItem(KEY) || '[]') } catch (e) {}
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(history.slice(-20))) } catch (e) {} };

  const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  // Just enough Markdown for chat answers: bold, inline code, bullet lists, paragraphs
  function md(text) {
    const lines = esc(text).split('\n');
    let out = '', inList = false;
    for (const raw of lines) {
      const line = raw.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');
      const item = line.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)/);
      if (item) { if (!inList) { out += '<ul>'; inList = true } out += `<li>${item[1]}</li>`; continue }
      if (inList) { out += '</ul>'; inList = false }
      if (line.trim()) out += `<p>${line}</p>`;
    }
    return out + (inList ? '</ul>' : '');
  }

  mount.innerHTML = `
    <button type="button" class="chat-fab" aria-expanded="false" aria-controls="chat-panel">💬 ${esc(T.chat_open)}</button>
    <section class="chat-panel" id="chat-panel" hidden aria-label="${esc(T.chat_title)}">
      <header><h2>${esc(T.chat_title)}</h2>
        <button type="button" class="chat-reset">${esc(T.chat_reset)}</button>
        <button type="button" class="chat-x" aria-label="${esc(T.chat_close)}">×</button></header>
      <div class="chat-log" aria-live="polite"></div>
      <form class="chat-form">
        <textarea rows="2" maxlength="${MAX_LEN}" placeholder="${esc(T.chat_placeholder)}" aria-label="${esc(T.chat_placeholder)}"></textarea>
        <button type="submit">${esc(T.chat_send)}</button>
      </form>
      <p class="chat-note">${esc(T.chat_disclaimer)}</p>
    </section>`;
  const fab = mount.querySelector('.chat-fab'), panel = mount.querySelector('.chat-panel');
  const log = mount.querySelector('.chat-log'), form = mount.querySelector('.chat-form');
  const input = form.querySelector('textarea'), send = form.querySelector('button');

  function bubble(role, text) {
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.innerHTML = role === 'assistant' ? md(text) : `<p>${esc(text)}</p>`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }
  history.forEach(m => bubble(m.role, m.content));

  const toggle = open => {
    panel.hidden = !open; fab.setAttribute('aria-expanded', open);
    if (open) input.focus();
  };
  fab.addEventListener('click', () => toggle(panel.hidden));
  mount.querySelector('.chat-x').addEventListener('click', () => toggle(false));
  mount.querySelector('.chat-reset').addEventListener('click', () => { history = []; save(); log.innerHTML = '' });
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit() } });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const question = input.value.trim().slice(0, MAX_LEN);
    if (!question || send.disabled) return;
    input.value = '';
    history.push({ role: 'user', content: question });
    bubble('user', question);
    const answer = bubble('assistant', '…');
    answer.classList.add('pending');
    send.disabled = true;
    let text = '';
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack, mod, lang, messages: history.slice(-10) }),
      });
      if (!res.ok || !res.body) throw new Error(res.status === 429 ? 'busy' : 'http');
      const reader = res.body.getReader(), dec = new TextDecoder();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        text += dec.decode(value, { stream: true });
        answer.innerHTML = md(text);
        log.scrollTop = log.scrollHeight;
      }
      if (!text.trim()) throw new Error('empty');
      history.push({ role: 'assistant', content: text });
    } catch (err) {
      // Drop the unanswered question so the next request still alternates user/assistant
      history.pop();
      answer.innerHTML = `<p>${esc(err.message === 'busy' ? T.chat_busy : T.chat_error)}</p>`;
      answer.classList.add('error');
    } finally {
      answer.classList.remove('pending');
      send.disabled = false;
      save();
    }
  });
})();
