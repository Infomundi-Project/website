const KEY_STORAGE = 'my-ecdh-key';

export async function getMyKeyPair() {
  const stored = localStorage.getItem(KEY_STORAGE);
  if (stored) {
    const { publicJwk, privateJwk } = JSON.parse(stored);
    const [ publicKey, privateKey ] = await Promise.all([
      crypto.subtle.importKey('jwk', publicJwk, { name: 'ECDH', namedCurve: 'P-256' }, true, []),
      crypto.subtle.importKey('jwk', privateJwk, { name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveKey'])
    ]);
    return { publicKey, privateKey };
  }
  // Generate new keypair
  const pair = await crypto.subtle.generateKey(
    { name: 'ECDH', namedCurve: 'P-256' },
    true,
    ['deriveKey']
  );
  const [ publicJwk, privateJwk ] = await Promise.all([
    crypto.subtle.exportKey('jwk', pair.publicKey),
    crypto.subtle.exportKey('jwk', pair.privateKey)
  ]);
  localStorage.setItem(KEY_STORAGE, JSON.stringify({ publicJwk, privateJwk }));
  return pair;
}
