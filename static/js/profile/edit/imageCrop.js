let cropper = null;
let currentInput = null;

function openCropper(file, aspectRatio) {
  const reader = new FileReader();
  reader.onload = e => {
    const img = document.createElement('img');
    img.id = 'cropperImage';
    img.src = e.target.result;
    const wrapper = document.getElementById('cropperWrapper');
    wrapper.innerHTML = '';
    wrapper.appendChild(img);
    cropper = new Cropper(img, {
      aspectRatio,
      viewMode: 1,
      autoCropArea: 1,
      responsive: true
    });
    new bootstrap.Modal(document.getElementById('cropModal')).show();
  };
  reader.readAsDataURL(file);
}

document.querySelectorAll('input[type=file]').forEach(input => {
  input.addEventListener('change', () => {
    if (input.files && input.files[0]) {
      currentInput = input;
      const [w, h] = input.dataset.aspect.split('/').map(Number);
      openCropper(input.files[0], w / h);
    }
  });
});

// Cropper toolbar actions
document.getElementById('zoomIn').addEventListener('click',  () => cropper.zoom(0.1));
document.getElementById('zoomOut').addEventListener('click', () => cropper.zoom(-0.1));
document.getElementById('rotateLeft').addEventListener('click', () => cropper.rotate(-45));
document.getElementById('rotateRight').addEventListener('click',() => cropper.rotate(45));

document.getElementById('cropBtn').addEventListener('click', () => {
  if (!cropper || !currentInput) return;
  cropper.getCroppedCanvas().toBlob(blob => {
    const file = new File([blob], currentInput.name, {
      type: 'image/png',
      lastModified: Date.now()
    });
    const dt = new DataTransfer();
    dt.items.add(file);
    currentInput.files = dt.files;
    const url = URL.createObjectURL(file);
    if (currentInput.id === 'backgroundImage') {
      document.getElementById('profileBackground').style.backgroundImage = `url(${url})`;
    } else if (currentInput.id === 'bannerImage') {
      document.getElementById('profileHeader').style.backgroundImage = `url(${url})`;
    } else {
      ['largeAvatar','mediumAvatar','smallAvatar']
        .forEach(id => document.getElementById(id).src = url);
    }
    bootstrap.Modal.getInstance(
      document.getElementById('cropModal')
    ).hide();
    cropper.destroy();
    cropper = null;
  }, 'image/png');
});

document.getElementById('avatarForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  const submitBtn = document.getElementById('submitBtn');
  const originalHTML = submitBtn.innerHTML;
  submitBtn.disabled = true;
  submitBtn.innerHTML = `
    <span class="spinner-border spinner-border-sm me-2"
          role="status" aria-hidden="true"></span>
    Uploading...
  `;

  const csrfToken = document.querySelector('input[name="csrf_token"]').value;
  const ops = [], mapping = {
    backgroundImage: 'wallpaper',
    bannerImage:     'banner',
    profilePhoto:    'avatar'
  };

  for (let inputId in mapping) {
    const inp = document.getElementById(inputId);
    if (inp.files.length) {
      const fd = new FormData();
      fd.append(mapping[inputId], inp.files[0]);
      fd.append('csrf_token', csrfToken);
      ops.push(
        fetch(`/api/user/image/${mapping[inputId]}`, {
          method: 'POST',
          credentials: 'same-origin',
          body: fd
        })
        .then(async res => {
          if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            const err = data.error || {};
            throw {
              status: err.status || res.status,
              title:  err.title  || 'Upload Error',
              detail: err.detail || res.statusText
            };
          }
        })
      );
    }
  }

  if (!ops.length) {
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalHTML;
    const em = new bootstrap.Modal(document.getElementById('errorModal'));
    document.getElementById('errorModalLabel').textContent = 'No files selected';
    document.getElementById('errorModalBody').textContent = 'Please choose at least one image.';
    em.show();
    return;
  }

  try {
    await Promise.all(ops);
    // success toast
    const toastEl = document.getElementById('successToast');
    const toast = new bootstrap.Toast(toastEl, { delay: 2000 });
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => window.location.reload());
  } catch (err) {
    console.error(err);
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalHTML;
    const em = new bootstrap.Modal(document.getElementById('errorModal'));
    document.getElementById('errorModalLabel').textContent = err.title;
    document.getElementById('errorModalBody').innerHTML = `
      <p><strong>Status:</strong> ${err.status}</p>
      <p>${err.detail}</p>
    `;
    em.show();
  }
});