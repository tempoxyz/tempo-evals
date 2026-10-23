import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';

test('plain wallet script announces a provider and forwards requests without page keys', async () => {
  const address = `0x${'1'.repeat(40)}`;
  const requests: object[] = [];
  const events: any[] = [];
  const listeners = new Map();
  const window: any = {
    __tempoWalletRequest: async (request: object) => { requests.push(request); return [address]; },
    dispatchEvent: (event: unknown) => { events.push(event); },
    addEventListener: (name: string, fn: () => void) => { listeners.set(name, fn); },
  };
  const source = readFileSync(new URL('./wallet-provider.js', import.meta.url), 'utf8');
  runInNewContext(source.replace('__ADDRESS__', JSON.stringify(address)), {
    window, CustomEvent: class { constructor(public type: string, public detail: object) {} },
  });
  assert.equal(window.ethereum.selectedAddress, address);
  assert.equal(window.ethereum.chainId, '0xa5bf');
  assert.equal(events[0].type, 'eip6963:announceProvider');
  listeners.get('eip6963:requestProvider')();
  assert.equal(events.length, 2);
  let updates = 0;
  const listener = () => updates++;
  window.ethereum.on('accountsChanged', listener);
  await window.ethereum.request({ method: 'eth_requestAccounts' });
  assert.equal(updates, 1);
  window.ethereum.removeListener('accountsChanged', listener);
  await window.ethereum.request({ method: 'eth_requestAccounts' });
  assert.equal(updates, 1);
  assert.equal(requests.length, 2);
  assert.equal('privateKey' in window.ethereum, false);
});
