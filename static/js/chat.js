import {
  getMyKeyPair
} from './utils/keys.js';

const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

(async function publishMyPublicKey() {
  const {
    publicKey
  } = await getMyKeyPair();
  // export the JWK form  public key
  const publicJwk = await crypto.subtle.exportKey('jwk', publicKey);

  // send it once to backend
  await fetch('/api/user/pubkey', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken
    },
    credentials: 'include', // make sure cookie/session is sent
    body: JSON.stringify({
      publicKey: publicJwk
    }),
  });
})();

// Initialize socket.io with credentials for Flask-Login session
const socket = io({
  transports: ['websocket'],
  withCredentials: true
});

// Keep track of shared secrets per friend
const chatKeys = {}; // chatKeys[friendId] = { sharedSecret }
let currentChatFriend = null;
let chatReady = false;

// --- constants - typing ---------------
const TYPING_DEBOUNCE = 250; // how long to wait between key strokes
const TYPING_TIMEOUT = 2000; // how long after silence to emit "stop"

// --- state - typing -------------------
let typingTimer = null; // fires 2 s after user stops typing
let lastTypeSent = 0; // throttle outgoing "typing" events

// --- DOM ---------------------
const typingIndicatorEl = document.getElementById('typingIndicator');
const chatModalEl = document.getElementById('chatModal');
const chatFriendNameEl = document.getElementById('chatFriendName');
const chatMessagesEl = document.getElementById('chatMessages');
const chatInputEl = document.getElementById('chatInput');
const sendChatBtn = document.getElementById('sendChatBtn');
const bsChatModal = new bootstrap.Modal(chatModalEl, {});

// ---------------- util ----------------
function scrollToBottom() {
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

const friendNames = {}; // e.g.  friendNames[uuid] = "Alice"

// helper ------------------------------------------------
function showChatToast(friendId) {
  const name = friendNames[friendId] || 'Someone';

  // toast markup
  const toastEl = document.createElement('div');
  toastEl.className = 'toast align-items-center text-bg-primary border-0';
  toastEl.role = 'alert';
  toastEl.ariaLive = 'assertive';
  toastEl.ariaAtomic = 'true';
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">
        <i class="fa-solid fa-comment-dots me-1"></i>
        You received a new message from <strong>${name}</strong>
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto"
              data-bs-dismiss="toast" aria-label="Close"></button>
    </div>`;

  // clicking the toast opens the chat
  toastEl.addEventListener('click', () => {
    bootstrap.Toast.getOrCreateInstance(toastEl).hide(); // optional
    window.openChat(friendId, name);
  });

  // add to container & show
  document.getElementById('chatToastContainer').appendChild(toastEl);
  bootstrap.Toast.getOrCreateInstance(toastEl, {
    delay: 7000
  }).show();
}



// Function to open chat: derive once, decrypt instantly
window.openChat = async function(friendPublicId, friendName) {
  currentChatFriend = friendPublicId;
  chatReady = false;

  // Reset UI
  chatFriendNameEl.textContent = friendName;

  // Remove old messages but keep the typing indicator
  chatMessagesEl
    .querySelectorAll('li:not(#typingIndicator)')
    .forEach(li => li.remove());

  chatInputEl.value = '';
  sendChatBtn.disabled = true;
  chatInputEl.disabled = true;

  // hide any open modal
  const openModal = document.querySelector('.modal.show');
  if (openModal) {
    bootstrap.Modal.getInstance(openModal).hide();
  }


  bsChatModal.show();

  try {
    // Load or generate our device keypair
    const {
      publicKey: myPub,
      privateKey: myPriv
    } = await getMyKeyPair();

    // Fetch friend’s public JWK
    const res = await fetch(`/api/user/${friendPublicId}/pubkey`);
    const {
      publicKey: friendJwk
    } = await res.json();

    const friendPub = await window.crypto.subtle.importKey(
      'jwk', friendJwk, {
        name: 'ECDH',
        namedCurve: 'P-256'
      },
      false, []
    );

    // Derive shared AES-GCM key
    const shared = await window.crypto.subtle.deriveKey({
        name: 'ECDH',
        public: friendPub
      },
      myPriv, {
        name: 'AES-GCM',
        length: 256
      },
      false,
      ['encrypt', 'decrypt']
    );
    chatKeys[friendPublicId] = {
      sharedSecret: shared
    };

    // Enable UI
    chatReady = true;
    sendChatBtn.disabled = false;
    chatInputEl.disabled = false;

    decryptPendingMessages(); // handles anything that arrived early

    // Optional: load + decrypt history
    const historyRes = await fetch(`/api/user/${friendPublicId}/messages`);
    const {
      messages
    } = await historyRes.json();
    for (let msg of messages) {
      appendEncryptedMessage(msg.ciphertext, msg.from === friendPublicId ? 'friend' : 'me');
    }

    decryptPendingMessages();
    scrollToBottom(); // history + early packets visible

  } catch (err) {
    console.error('Error setting up E2EE', err);
  }
};

// 1. Add a bubble wrapper when appending ciphertext
function appendEncryptedMessage(ciphertext, sender) {
  const li = document.createElement('li');
  li.className = `${sender}`; // me | friend
  li.dataset.ciphertext = ciphertext;
  li.dataset.sender = sender;

  const bubble = document.createElement('span');
  bubble.className = 'chat-bubble';
  if (sender === 'friend') {
    bubble.classList.add('bg-secondary', 'text-white');
  } else {
    bubble.classList.add('bg-primary', 'text-white');
  }

  bubble.textContent = '[Encrypted message]'; // placeholder
  li.appendChild(bubble);

  chatMessagesEl.insertBefore(li, typingIndicatorEl);
  typingIndicatorEl.classList.add('d-none'); // hide if it was shown
  scrollToBottom(); // every new bubble
}

// 2. Write into the bubble after decryption
async function decryptPendingMessages() {
  if (!chatReady || !chatKeys[currentChatFriend]?.sharedSecret) return;

  const items = chatMessagesEl.querySelectorAll('li');
  for (let li of items) {
    const bubble = li.querySelector('.chat-bubble');
    if (bubble && bubble.textContent === '[Encrypted message]') {
      try {
        const bytes = Uint8Array.from(atob(li.dataset.ciphertext), c => c.charCodeAt(0));
        const iv = bytes.slice(0, 12);
        const data = bytes.slice(12);
        const buf = await crypto.subtle.decrypt({
            name: 'AES-GCM',
            iv
          },
          chatKeys[currentChatFriend].sharedSecret,
          data
        );
        const text = new TextDecoder().decode(buf);
        bubble.textContent = text;
      } catch {
        bubble.textContent = '[Unable to decrypt]';
      }
    }
  }
  scrollToBottom(); // bubble may have grown in height
}


socket.on('receive_message', data => {
  const {
    from,
    fromName,
    message
  } = data;
  friendNames[from] = fromName; // cache it
  const modalOpen = chatModalEl.classList.contains('show');

  // 1) if the message is for a different conversation   → toast
  // 2) if it’s for the current conversation but the modal is hidden → toast
  // 3) otherwise (active chat in view)                   → no toast
  if (from !== currentChatFriend || !modalOpen) {
    showChatToast(from);
  }

  if (from !== currentChatFriend) return; // don’t put bubbles in the wrong chat

  appendEncryptedMessage(message, 'friend');

  decryptPendingMessages(); // cheap no-op until the secret exists
});


// Send encrypted message
async function sendCurrentMessage() {
  if (!chatReady || !currentChatFriend) return;
  const plaintext = chatInputEl.value.trim();
  if (!plaintext) return;
  const encoder = new TextEncoder();
  const ptBytes = encoder.encode(plaintext);
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  socket.emit('typing', {
    to: currentChatFriend,
    typing: false
  });
  try {
    const ctBuf = await window.crypto.subtle.encrypt({
        name: 'AES-GCM',
        iv
      },
      chatKeys[currentChatFriend].sharedSecret,
      ptBytes
    );
    const combined = new Uint8Array(iv.byteLength + ctBuf.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(ctBuf), iv.byteLength);
    const ctB64 = btoa(String.fromCharCode(...combined));
    appendEncryptedMessage(ctB64, 'me');
    // wrap emit in a Promise so we retry on failure
    try {
      await new Promise((resolve, reject) => {
        // third arg is the ack callback from server
        socket.emit('send_message', {
          to: currentChatFriend,
          message: ctB64
        }, (ack) => {
          if (ack && ack.status === 'ok') return resolve();
          reject(new Error('server NACK'));
        });

        // also time-out if no response after X seconds
        setTimeout(() => reject(new Error('ack timeout')), 5000);
      });
    } catch (err) {
      console.warn('Message not delivered, retrying…', err);
      // simple retry once more (or queue for later)
      socket.emit('send_message', {
        to: currentChatFriend,
        message: ctB64
      });
    }
    chatInputEl.value = '';
    decryptPendingMessages();
  } catch (err) {
    console.error('Encryption error:', err);
  }
}

// Bind send handlers
sendChatBtn.addEventListener('click', sendCurrentMessage);
chatInputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    e.preventDefault();
    sendCurrentMessage();
  }
});

// 2-a.  OUTGOING  – detect input --------------------------------
chatInputEl.addEventListener('input', () => {
  if (!chatReady) return; // key still not derived

  const now = Date.now();
  if (now - lastTypeSent > TYPING_DEBOUNCE) {
    socket.emit('typing', {
      to: currentChatFriend,
      typing: true
    });
    lastTypeSent = now;
  }

  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => {
    socket.emit('typing', {
      to: currentChatFriend,
      typing: false
    });
  }, TYPING_TIMEOUT);
});

// 2-b.  INCOMING  – toggle the indicator -------------------------
socket.on('typing', data => {
  if (data.from !== currentChatFriend) return;

  if (data.typing) {
    typingIndicatorEl.classList.remove('d-none');
    // keep it visible for at most 3 s even if the "stop" packet is lost
    clearTimeout(typingIndicatorEl._hideTmr);
    typingIndicatorEl._hideTmr = setTimeout(
      () => typingIndicatorEl.classList.add('d-none'),
      3000
    );
  } else {
    typingIndicatorEl.classList.add('d-none');
  }
});


// Join personal room on connect
socket.on('connect', () => socket.emit('join_room'));

socket.on('disconnect', (reason) => {
  console.warn('Socket disconnected:', reason);
});

socket.on('reconnect', async (attempt) => {
  console.log('Socket reconnected after', attempt, 'attempts');
  // rejoin your room
  socket.emit('join_room');

  // if we currently have a chat open, re-fetch any missed messages
  if (currentChatFriend) {
    const res = await fetch(`/api/user/${currentChatFriend}/messages`, {
      credentials: 'include'
    });
    const {
      messages
    } = await res.json();
    // ideally diff against already-shown messages, but simplest is:
    chatMessagesEl
      .querySelectorAll('li:not(#typingIndicator)')
      .forEach(li => li.remove());
    for (let msg of messages) {
      appendEncryptedMessage(
        msg.ciphertext,
        msg.from === currentChatFriend ? 'friend' : 'me'
      );
    }
    decryptPendingMessages();
    scrollToBottom();
  }
});