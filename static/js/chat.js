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
const chatModalBody = document.getElementById('chatModalBody');
const bsChatModal = new bootstrap.Modal(chatModalEl, {});


let currentReply = null;

function startReplying({ id, previewText }) {
  // previewText already trimmed client-side, but let's be safe:
  const snippet = previewText.slice(0, 100);
  currentReply = { id, previewText: snippet };
  const replyBox = document.getElementById('replyPreview');
  replyBox.querySelector('.reply-text').textContent = currentReply.previewText;
  replyBox.classList.remove('d-none');
}

document.getElementById('cancelReplyBtn')
  .addEventListener('click', () => {
    currentReply = null;
    let preview = document.getElementById('replyPreview')
    if (preview) {
      preview.classList.add('d-none');
    }
  });

// ---------------- util ----------------
function scrollToBottom() {
  chatModalBody.scrollTop = chatModalBody.scrollHeight;
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
      appendEncryptedMessage(
        msg.ciphertext,
        msg.from == friendPublicId ? 'friend' : 'me',
        msg.reply_to,
        msg.id                    // ← newly added
      );
    }

    decryptPendingMessages();
    scrollToBottom(); // history + early packets visible

  } catch (err) {
    console.error('Error setting up E2EE', err);
  }
};

/**
 * ciphertext: Base64
 * sender: "me" | "friend"
 * replyTo: { id: number, previewText: string } | null
 * messageId: number
 */
function appendEncryptedMessage(ciphertext, sender, replyTo = null, messageId = null) {
  const li = document.createElement('li');
  li.className = sender;               
  li.dataset.ciphertext = ciphertext;
  if (messageId != null) {
    li.dataset.messageId = messageId;
    li.id = `msg-${messageId}`;
  }
  if (replyTo && replyTo.id) {
    // Try to find the already‐displayed parent message bubble
    let snippet = '';
    const parentLi = chatMessagesEl.querySelector(`li[data-message-id="${replyTo.id}"]`);
    if (parentLi) {
      const parentText = parentLi.querySelector('.chat-text').textContent;
      snippet = parentText.slice(0, 100);
    }
    if (snippet) {
      const quote = document.createElement('div');
      quote.className = 'chat-quote text-truncate';
      quote.textContent = snippet;

      // make it obvious it’s clickable
      quote.style.cursor = 'pointer';

      // on click, jump to the original
      quote.addEventListener('click', () => {
        const target = document.getElementById(`msg-${replyTo.id}`);
        if (target) {
          // scroll the modal-body so that target is centered
          target.scrollIntoView({ behavior: 'smooth', block: 'center' });

          // briefly flash a highlight
          target.classList.add('reply-highlight');
          setTimeout(() => target.classList.remove('reply-highlight'), 1500);
        }
      });

      quote.dataset.replyToId = replyTo.id;
      // we’ll render this _before_ the chat-text
      const bubble = document.createElement('div');
      bubble.classList.add('chat-bubble',
        sender=='friend' ? 'bg-secondary' : 'bg-primary',
        'text-white');
      bubble.appendChild(quote);
      const textSpan = document.createElement('span');
      textSpan.className = 'chat-text';
      textSpan.textContent = '[Encrypted message]';
      bubble.appendChild(textSpan);
      li.appendChild(bubble);
      chatMessagesEl.insertBefore(li, typingIndicatorEl);
      scrollToBottom();
      return;
    }
  }

  // No reply snippet; previous flow:
  const bubble = document.createElement('div');
  bubble.classList.add('chat-bubble',
    sender=='friend' ? 'bg-secondary' : 'bg-primary',
    'text-white');
  const textSpan = document.createElement('span');
  textSpan.className = 'chat-text';
  textSpan.textContent = '[Encrypted message]';
  bubble.appendChild(textSpan);
  li.appendChild(bubble);
  chatMessagesEl.insertBefore(li, typingIndicatorEl);
  scrollToBottom();
  return li;
}


async function decryptPendingMessages() {
  if (!chatReady) return;
  for (let li of chatMessagesEl.querySelectorAll('li')) {
    const textSpan = li.querySelector('.chat-text');
    if (!textSpan || textSpan.textContent != '[Encrypted message]') continue;

    try {
      const bytes = Uint8Array.from(atob(li.dataset.ciphertext), c=>c.charCodeAt(0));
      const iv    = bytes.slice(0, 12);
      const data  = bytes.slice(12);
      const buf   = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv },
        chatKeys[currentChatFriend].sharedSecret,
        data
      );
      textSpan.textContent = new TextDecoder().decode(buf);
      // now that this message is decrypted, update any reply-quotes pointing at it
      const decrypted = textSpan.textContent;
      const msgId     = li.dataset.messageId;
      if (msgId) {
        chatMessagesEl
          .querySelectorAll(`.chat-quote[data-reply-to-id="${msgId}"]`)
          .forEach(q => { q.textContent = decrypted.slice(0, 100); });
      }
    } catch {
      textSpan.textContent = '[Unable to decrypt]';
    }
  }
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
  if (from != currentChatFriend || !modalOpen) {
    showChatToast(from);
  }

  if (from != currentChatFriend) return; // don’t put bubbles in the wrong chat

  // on receive
  appendEncryptedMessage(
      data.message,
      'friend',
      data.reply_to,
      data.messageId           // ← newly sent by the server
    );
    decryptPendingMessages();
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
    const payload = {
      to: currentChatFriend,
      message: ctB64,
      parent_id: currentReply ? parseInt(currentReply.id, 10) : null
    };

    // on send
const myLi = appendEncryptedMessage(ctB64, 'me', currentReply);

    // reset reply state
    currentReply = null;
    let preview = document.getElementById('replyPreview')
    if (preview) {
      preview.classList.add('d-none');
    }

    // wrap emit in a Promise so we retry on failure
    try {
  await new Promise((resolve, reject) => {
    socket.emit('send_message', payload, (ack) => {
      if (!ack || ack.status != 'ok') {
        return reject(new Error('server NACK'));
      }
      // tag our LI with the real ID and anchor id
      if (myLi) {
        myLi.dataset.messageId = ack.messageId;
        myLi.id = `msg-${ack.messageId}`;
      }
      resolve();
    });

        // also time-out if no response after X seconds
        setTimeout(() => reject(new Error('ack timeout')), 5000);
      });
    } catch (err) {
      console.warn('Message not delivered, retrying…', err);
      // simple retry once more (or queue for later)
      socket.emit('send_message', payload);
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
  if (e.key == 'Enter') {
    e.preventDefault();
    sendCurrentMessage();
  }
});

// OUTGOING  – detect input --------------------------------
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

chatMessagesEl.addEventListener('contextmenu', e => {
  const li = e.target.closest('li');
  if (!li || !li.dataset.ciphertext) return;
  e.preventDefault();
  const msgId = li.dataset.messageId;          // now actually defined
  const bubble = li.querySelector('.chat-bubble');
  const originalText = bubble.querySelector('.chat-text').textContent;
  startReplying({ id: msgId, previewText: originalText });
});

// INCOMING  – toggle the indicator -------------------------
socket.on('typing', data => {
  if (data.from != currentChatFriend) return;

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
  msg.from==friendId ? 'friend' : 'me',
  msg.reply_to  // or null
);
    }
    decryptPendingMessages();
    scrollToBottom();
  }
});