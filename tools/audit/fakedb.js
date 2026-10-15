// In-memory stand-in for the Artifact db capability, to try the page locally with Playwright.
window.claude = { use: async () => { const store = {}; const subs = [];
  const snap = () => ({ docs: Object.entries(store).map(([id, v]) => ({ id, data: () => v })) });
  const fire = () => subs.forEach(f => f(snap()));
  return { collection: () => ({ onSnapshot: (f) => { subs.push(f); setTimeout(() => f(snap()), 0); return () => {}; },
    doc: id => ({ set: async v => { store[id] = v; fire(); }, delete: async () => { delete store[id]; fire(); } }) }) }; } };
