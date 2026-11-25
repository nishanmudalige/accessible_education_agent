'use strict';
(() => {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) return;

  const byId = id => document.getElementById(id);
  const question = byId('question');
  const mic = byId('dictate');
  const languages = byId('dictation-languages');
  const tr = window.AccessEdu.tr;
  const key = 'accessedu-dictation-language';
  const permissionMessage = [
    'Microphone access denied. Allow it in the browser address bar, then reload the page.',
    'Accès au microphone refusé. Autorisez-le dans la barre d’adresse du navigateur, puis rechargez la page.'
  ];
  let language = 'en-US';
  try {
    if (localStorage.getItem(key) === 'fr-CA') language = 'fr-CA';
  } catch {}
  let active = null;
  let remaining = null;
  let timer;
  let message = ['', ''];

  function render() {
    mic.setAttribute('aria-pressed', String(remaining !== null));
    mic.setAttribute('aria-label', tr('Dictate question', 'Dicter la question'));
    byId('dictate-label').textContent = remaining !== null
      ? tr('Stop', 'Arrêter') + ' · ' + remaining + ' s'
      : active ? tr('Cancel', 'Annuler') : tr('Dictate', 'Dicter');
    languages.setAttribute('aria-label', tr('Dictation language', 'Langue de dictée'));
    for (const button of languages.querySelectorAll('button')) {
      button.setAttribute('aria-pressed', String(button.dataset.lang === language));
      button.setAttribute('aria-label', button.dataset.lang === 'en-US'
        ? tr('Dictate in English', 'Dicter en anglais')
        : tr('Dictate in Canadian French', 'Dicter en français canadien'));
    }
    byId('dictation-status').textContent = tr(...message);
  }

  function finish(en = 'Dictation stopped.', fr = 'Dictée arrêtée.') {
    clearInterval(timer);
    remaining = null;
    active = null;
    message = [en, fr];
    render();
  }

  function cancel() {
    if (!active) return;
    const recognition = active;
    finish();
    recognition.abort();
  }

  function start() {
    if (byId('ask').disabled) return;
    const before = question.value.slice(0, question.selectionStart);
    const after = question.value.slice(question.selectionEnd);
    try {
      const recognition = new Recognition();
      active = recognition;
      recognition.lang = language;
      recognition.continuous = true;
      recognition.interimResults = true;
      let stopping = false;
      function stop() {
        if (stopping) return;
        stopping = true;
        clearInterval(timer);
        recognition.stop();
      }
      recognition.onresult = event => {
        if (active !== recognition) return;
        let words = Array.from(event.results, result => result[0].transcript.trim()).filter(Boolean).join(' ');
        if (words && before && !/\s$/.test(before)) words = ' ' + words;
        if (words && after && !/^\s/.test(after)) words += ' ';
        words = words.slice(0, Math.max(0, question.maxLength - before.length - after.length));
        question.value = before + words + after;
        question.setSelectionRange(before.length + words.length, before.length + words.length);
      };
      recognition.onend = () => { if (active === recognition) finish(); };
      recognition.onerror = event => {
        console.log('SpeechRecognition error:', event.error);
        if (active !== recognition) return;
        switch (event.error) {
          case 'not-allowed':
          case 'service-not-allowed':
            finish(...permissionMessage);
            break;
          case 'network':
            finish('Speech recognition service unreachable. Chrome needs a connection to Google servers.',
              'Service de reconnaissance vocale inaccessible. Chrome doit pouvoir joindre les serveurs de Google.');
            break;
          case 'no-speech':
            finish('No speech was heard.', 'Aucune parole détectée.');
            break;
          case 'audio-capture':
            finish('No microphone found.', 'Aucun microphone détecté.');
            break;
          default:
            finish('Dictation error: ' + event.error, 'Erreur de dictée : ' + event.error);
        }
      };
      recognition.onstart = () => {
        if (active !== recognition || stopping) return;
        remaining = 30;
        message = ['Recording.', 'Enregistrement en cours.'];
        render();
        const deadline = Date.now() + 30000;
        timer = setInterval(() => {
          remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
          byId('dictate-label').textContent = tr('Stop', 'Arrêter') + ' · ' + remaining + ' s';
          if (!remaining) stop();
        }, 250);
      };
      message = ['Starting microphone…', 'Activation du microphone…'];
      render();
      mic.onclick = () => {
        if (!active) start();
        else if (remaining === null) cancel();
        else stop();
      };
      recognition.start();
    } catch (error) {
      if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
        finish(...permissionMessage);
      } else {
        finish('Could not start dictation.', 'Impossible de démarrer la dictée.');
      }
    }
  }

  mic.onclick = start;
  languages.addEventListener('click', event => {
    const next = event.target.closest('button')?.dataset.lang;
    if (!next || next === language) return;
    cancel();
    language = next;
    try { localStorage.setItem(key, language); } catch {}
    render();
  });
  question.addEventListener('input', cancel);
  byId('examples').addEventListener('click', cancel);
  byId('local-search').addEventListener('click', cancel, true);
  byId('ask-form').addEventListener('submit', cancel, true);
  window.addEventListener('pagehide', cancel);
  document.addEventListener('languagechange', render);
  render();
  byId('dictation').hidden = false;
})();
