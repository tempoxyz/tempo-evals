// Plain browser JavaScript: do not serialize a transpiled TypeScript callback.
(() => {
  const listeners = new Map();
  const provider = {
    isMetaMask: true, // Compatibility adapter for the injected-wallet selector.
    selectedAddress: __ADDRESS__, chainId: '0xa5bf', networkVersion: '42431',
    isConnected: () => true,
    _metamask: { isUnlocked: async () => true },
    request: async request => {
      const result = await window.__tempoWalletRequest(request);
      if (request.method === 'eth_requestAccounts') listeners.get('accountsChanged')?.forEach(fn => fn(result));
      return result;
    },
    on(event, listener) {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event).add(listener); return provider;
    },
    removeListener(event, listener) { listeners.get(event)?.delete(listener); return provider; },
  };
  Object.defineProperty(window, 'ethereum', { value: provider, configurable: true });
  const announce = () => window.dispatchEvent(new CustomEvent('eip6963:announceProvider', { detail: {
    info: { uuid: '82ab73ed-7dde-4cf5-919a-9648cfd11e63', name: 'MetaMask', rdns: 'io.metamask', icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg"/>' }, provider,
  } }));
  window.addEventListener('eip6963:requestProvider', announce);
  announce();
})();
