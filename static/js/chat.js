import { getMyKeyPair } from './utils/keys.js';

// Initialize socket.io with credentials for Flask-Login session
const socket = io({
  transports: ['websocket'],
  withCredentials: true
});

// Keep track of shared secrets per friend
const chatKeys = {};   // chatKeys[friendId] = { sharedSecret }
let currentChatFriend = null;
let chatReady = false;

// DOM elements
const chatModalEl     = document.getElementById('chatModal');
const chatFriendNameEl= document.getElementById('chatFriendName');
const chatMessagesEl  = document.getElementById('chatMessages');
const chatInputEl     = document.getElementById('chatInput');
const sendChatBtn     = document.getElementById('sendChatBtn');
const bsChatModal     = new bootstrap.Modal(chatModalEl, {});

// Open chat: derive once and enable immediately
window.openChat = async function(friendPublicId, friendName) {
  currentChatFriend = friendPublicId;
  chatReady = false;

  // UI reset
  chatFriendNameEl.textContent = friendName;
  chatMessagesEl.innerHTML    = '';
  chatInputEl.value           = '';
  sendChatBtn.disabled        = true;
  chatInputEl.disabled        = true;

  // Show modal
  bsChatModal.show();

  try {
    // 1) Load/generate our long‑lived keypair
    const { publicKey: myPub, privateKey: myPriv } = await getMyKeyPair();

    // 2) Fetch friend's public JWK from server
    const res = await fetch(`/api/user/${friendPublicId}/pubkey`);
    const { publicKey: friendJwk } = await res.json();

    const friendPub = await window.crypto.subtle.importKey(
      'jwk', friendJwk,
      { name: 'ECDH', namedCurve: 'P-256' },
      false, []
    );

    // 3) Derive shared secret (AES‑GCM key)
    const shared = await window.crypto.subtle.deriveKey(
      { name: 'ECDH', public: friendPub },
      myPriv,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    );
    chatKeys[friendPublicId] = { sharedSecret: shared };

    // Enable input
    chatReady = true;
    sendChatBtn.disabled = false;
    chatInputEl.disabled = false;

    // Optionally load & decrypt history
    const historyRes = await fetch(`/api/user/${friendPublicId}/messages`);
    const { messages } = await historyRes.json();
    for (let msg of messages) {
      appendEncryptedMessage(msg.ciphertext, msg.from === friendPublicId ? 'friend' : 'me');
    }
    decryptPendingMessages();

  } catch (err) {
    console.error('Error setting up E2EE', err);
  }
};

// Append encrypted placeholder
function appendEncryptedMessage(ciphertext, sender) {
  const li = document.createElement('li');
  li.className = sender === 'me' ? 'text-end mb-2' : 'text-start mb-2';
  li.textContent = '[Encrypted message]';
  li.dataset.ciphertext = ciphertext;
  li.dataset.sender     = sender;
  chatMessagesEl.appendChild(li);
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

// Decrypt all pending
async function decryptPendingMessages() {
  if (!chatReady || !chatKeys[currentChatFriend]?.sharedSecret) return;
  const items = chatMessagesEl.querySelectorAll('li');
  for (let li of items) {
    if (li.textContent === '[Encrypted message]') {
      try {
        const ctB64 = li.dataset.ciphertext;
        const cipherBytes = Uint8Array.from(atob(ctB64), c=>c.charCodeAt(0));
        const iv   = cipherBytes.slice(0, 12);
        const data = cipherBytes.slice(12);
        const plainBuf = await window.crypto.subtle.decrypt(
          { name: 'AES-GCM', iv },
          chatKeys[currentChatFriend].sharedSecret,
          data
        );
        const text = new TextDecoder().decode(plainBuf);
        li.textContent = (li.dataset.sender === 'me' ? 'Me: ' : '') + text;
      } catch (e) {
        li.textContent = '[Unable to decrypt]';
        console.error('Decrypt failed:', e);
      }
    }
  }
}

// Receive new message from socket
socket.on('receive_message', data => {
  const { from, message: cipherText } = data;
  if (from !== currentChatFriend) {
    console.log('New message from', from);
    return;
  }
  appendEncryptedMessage(cipherText, 'friend');
  if (chatReady) decryptPendingMessages();
});

// Send handler
async function sendCurrentMessage() {
  if (!chatReady || !currentChatFriend) return;
  const plaintext = chatInputEl.value;
  if (!plaintext) return;
  const encoder = new TextEncoder();
  const ptBytes = encoder.encode(plaintext);
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  try {
    const ctBuf = await window.crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      chatKeys[currentChatFriend].sharedSecret,
      ptBytes
    );
    const combined = new Uint8Array(iv.byteLength + ctBuf.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(ctBuf), iv.byteLength);
    const ctB64 = btoa(String.fromCharCode(...combined));
    appendEncryptedMessage(ctB64, 'me');
    socket.emit('send_message', { to: currentChatFriend, message: ctB64 });
    chatInputEl.value = '';
    decryptPendingMessages();
  } catch (err) {
    console.error('Encryption error:', err);
  }
}

sendChatBtn.addEventListener('click', sendCurrentMessage);
chatInputEl.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); sendCurrentMessage(); }});

// Join personal room
socket.on('connect', () => socket.emit('join_room'));
