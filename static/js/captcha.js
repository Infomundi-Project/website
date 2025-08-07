// infomundi-captcha.js
class InfoMundiCaptcha extends HTMLElement {
  constructor() {
    super();
    // grab attributes or fall back to defaults
    this.apiEndpoint   = this.getAttribute('api-endpoint')   || '/api/captcha';
    this.inputName     = this.getAttribute('input-name')     || 'captcha';
    this.inputLabel    = this.getAttribute('input-label')    || 'Captcha';
    this.submitText    = this.getAttribute('submit-text')    || 'Submit';
    this.width         = this.getAttribute('width')          || 200;
    this.height        = this.getAttribute('height')         || 80;
    this.COOLDOWN_MS   = parseInt(this.getAttribute('cooldown-ms'), 10) || 2000;
  }

  connectedCallback() {
    this.innerHTML = `
      <div class="input-group has-validation mt-3 mb-2">
        <div class="form-floating flex-grow-1">
          <input
            type="text"
            class="form-control"
            id="im-captcha-input"
            name="${this.inputName}"
            placeholder="Enter ${this.inputLabel}"
            minlength="6"
            maxlength="6"
            required
            aria-describedby="im-captcha-reload"
            style="height: ${this.height}px;"
          />
          <label for="im-captcha-input">${this.inputLabel}</label>
        </div>

        <span
          class="input-group-text p-0"
          style="width:${this.width}px; height:${this.height}px; overflow:hidden;"
        >
          <img
            id="im-captcha-image"
            class="w-100 h-100 placeholder placeholder-wave"
            alt="CAPTCHA"
          />
        </span>

        <button
          class="btn btn-outline-secondary p-1"
          type="button"
          id="im-captcha-reload"
          title="Reload CAPTCHA"
          aria-label="Reload CAPTCHA"
        >
          <i class="fa-solid fa-rotate"></i>
        </button>

        <div class="invalid-feedback">
          Please enter the 6-character code to continue.
        </div>
      </div>

      <span id="im-captcha-message" class="small">
        <i class="fa-solid fa-robot me-1"></i>Please complete the captcha to enable the submit button.
      </span>

      <button class="btn btn-lg btn-secondary w-100 my-2" 
              type="submit" 
              id="im-captcha-submit" 
              disabled>
        ${this.submitText}
      </button>
    `;

    this._cacheElements();
    this._attachListeners();
    this._loadCaptcha();
  }

  _cacheElements() {
    this.img       = this.querySelector('#im-captcha-image');
    this.input     = this.querySelector('#im-captcha-input');
    this.reloadBtn = this.querySelector('#im-captcha-reload');
    this.msg       = this.querySelector('#im-captcha-message');
    this.submitBtn = this.querySelector('#im-captcha-submit');
  }

  _attachListeners() {
    this.input.addEventListener('input', () => {
      const ok = this.input.value.trim().length === 6;
      this.submitBtn.disabled = !ok;
      this.submitBtn.classList.toggle('btn-primary', ok);
      this.submitBtn.classList.toggle('btn-secondary', !ok);
      this.msg.classList.toggle('d-none', ok);
    });

    this.reloadBtn.addEventListener('click', () => {
      if (this.reloadBtn.disabled) return;
      this.reloadBtn.disabled = true;
      this._loadCaptcha();
      setTimeout(() => { this.reloadBtn.disabled = false; }, this.COOLDOWN_MS);
    });
  }

  async _loadCaptcha() {
    this.img.removeAttribute('src');
    this.img.classList.add('placeholder','placeholder-wave');
    this.submitBtn.disabled = true;
    this.submitBtn.classList.replace('btn-primary','btn-secondary');
    this.msg.classList.remove('d-none');
    this.input.value = '';

    try {
      const res = await fetch(this.apiEndpoint);
      if (!res.ok) throw new Error(res.statusText);
      const { captcha } = await res.json();
      this.img.src = 'data:image/webp;base64,' + captcha;
      this.img.classList.remove('placeholder','placeholder-wave');
    } catch (err) {
      console.error('CAPTCHA load failed:', err);
    }
  }
}

// define the custom element
customElements.define('infomundi-captcha', InfoMundiCaptcha);
