/**
 * RETINA-XAI Accessibility & Voice Engine
 * Handles:
 * 1. Web Speech API Recognition (English + Hindi)
 * 2. Web Speech Synthesis (Text-to-Speech) with Stop control
 * 3. Light / Dark Theme Switching with localStorage persistence
 * 4. Application-level UI/Text Zoom Scaling (A-, A, A+)
 */

(function () {
  'use strict';

  // ==========================================
  // 1. THEME MANAGER
  // ==========================================
  const THEME_KEY = 'retina_theme';

  function getSavedTheme() {
    return localStorage.getItem(THEME_KEY) || 'light';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);

    const toggleBtn = document.getElementById('themeToggle');
    if (toggleBtn) {
      const isDark = theme === 'dark';
      toggleBtn.innerHTML = isDark ? '<i class="bi bi-sun-fill"></i>' : '<i class="bi bi-moon-stars-fill"></i>';
      toggleBtn.setAttribute('aria-label', isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme');
      toggleBtn.setAttribute('title', isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme');
    }

    // Inform charts and other components
    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    if (window.showToast) {
      window.showToast(next === 'dark' ? 'Dark theme enabled' : 'Light theme enabled', 'info');
    }
  }

  // ==========================================
  // 2. ZOOM / ACCESSIBILITY SCALING MANAGER
  // ==========================================
  const ZOOM_KEY = 'retina_zoom';

  function getSavedZoom() {
    return localStorage.getItem(ZOOM_KEY) || 'normal';
  }

  function applyZoom(level) {
    if (!['small', 'normal', 'large'].includes(level)) {
      level = 'normal';
    }
    document.documentElement.setAttribute('data-zoom', level);
    localStorage.setItem(ZOOM_KEY, level);

    document.querySelectorAll('.zoom-btn').forEach(btn => {
      if (btn.dataset.zoom === level) {
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
      } else {
        btn.classList.remove('active');
        btn.setAttribute('aria-pressed', 'false');
      }
    });

    window.dispatchEvent(new CustomEvent('zoomChanged', { detail: { level } }));
  }

  // ==========================================
  // 3. WEB SPEECH API: SPEECH RECOGNITION (STT)
  // ==========================================
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  let recognitionInstance = null;
  let currentVoiceState = 'ready'; // 'ready', 'listening', 'processing', 'error'
  let currentTranscript = '';
  let activeDictationTarget = null;

  function isSpeechRecognitionSupported() {
    return SpeechRecognition !== null;
  }

  function setVoiceModalState(state, message) {
    currentVoiceState = state;
    const micBtn = document.getElementById('voiceModalMicBtn');
    const statusText = document.getElementById('voiceModalStatusText');
    const startStopBtn = document.getElementById('voiceModalToggleBtn');
    const waveEl = document.getElementById('audioWaveform');

    if (micBtn) {
      micBtn.className = `voice-mic-btn state-${state}`;
      const iconEl = micBtn.querySelector('i');
      if (iconEl) {
        if (state === 'listening') {
          iconEl.className = 'bi bi-mic-fill';
        } else if (state === 'processing') {
          iconEl.className = 'bi bi-hourglass-split';
        } else if (state === 'error') {
          iconEl.className = 'bi bi-exclamation-triangle-fill';
        } else {
          iconEl.className = 'bi bi-mic-fill';
        }
      }
    }

    if (statusText) {
      const currentLang = window.getCurrentLanguage ? window.getCurrentLanguage() : 'en';
      const t = window.translations && window.translations[currentLang] ? window.translations[currentLang] : {};
      
      let defaultMsg = '';
      if (state === 'listening') {
        defaultMsg = t['voice.status_listening'] || 'Listening... Speak now';
      } else if (state === 'processing') {
        defaultMsg = t['voice.status_processing'] || 'Processing speech...';
      } else if (state === 'error') {
        defaultMsg = t['voice.status_error'] || 'Microphone error or permission denied';
      } else {
        defaultMsg = t['voice.status_ready'] || 'Ready to listen';
      }
      statusText.textContent = message || defaultMsg;
    }

    if (startStopBtn) {
      const currentLang = window.getCurrentLanguage ? window.getCurrentLanguage() : 'en';
      const t = window.translations && window.translations[currentLang] ? window.translations[currentLang] : {};
      if (state === 'listening') {
        startStopBtn.innerHTML = `<i class="bi bi-stop-circle me-1"></i> <span>${t['voice.stop_btn'] || 'Stop Listening'}</span>`;
        startStopBtn.className = 'btn btn-danger px-4';
      } else {
        startStopBtn.innerHTML = `<i class="bi bi-mic-fill me-1"></i> <span>${t['voice.start_btn'] || 'Start Speaking'}</span>`;
        startStopBtn.className = 'btn btn-primary-custom px-4';
      }
    }

    // Global nav voice button indicator
    const navVoiceBtn = document.getElementById('navVoiceBtn');
    if (navVoiceBtn) {
      if (state === 'listening') {
        navVoiceBtn.classList.add('listening');
      } else {
        navVoiceBtn.classList.remove('listening');
      }
    }
  }

  function startRecognition(lang = 'en-US', onResultCallback = null, onEndCallback = null) {
    if (!isSpeechRecognitionSupported()) {
      setVoiceModalState('error', 'Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.');
      if (window.showToast) {
        window.showToast('Speech recognition not supported in this browser.', 'warning');
      }
      return null;
    }

    // Stop any existing instance
    stopRecognition();

    try {
      recognitionInstance = new SpeechRecognition();
      recognitionInstance.continuous = false; // Never listen infinitely in background
      recognitionInstance.interimResults = true;
      recognitionInstance.lang = lang === 'hi' ? 'hi-IN' : (lang === 'en' ? 'en-US' : lang);

      setVoiceModalState('listening');

      recognitionInstance.onstart = () => {
        setVoiceModalState('listening');
      };

      recognitionInstance.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }

        const text = (finalTranscript || interimTranscript).trim();
        if (text) {
          currentTranscript = text;
          const transcriptBox = document.getElementById('voiceTranscriptBox');
          if (transcriptBox) {
            transcriptBox.textContent = text;
          }

          if (onResultCallback) {
            onResultCallback(text, !!finalTranscript);
          }
        }
      };

      recognitionInstance.onerror = (event) => {
        console.warn('[SpeechRecognition error]:', event.error);
        setVoiceModalState('error', `Microphone: ${event.error}`);
        if (event.error === 'not-allowed') {
          if (window.showToast) {
            window.showToast('Microphone permission was denied. Please allow microphone access.', 'danger');
          }
        }
      };

      recognitionInstance.onend = () => {
        setVoiceModalState('ready');
        if (onEndCallback) onEndCallback();
      };

      recognitionInstance.start();
    } catch (e) {
      console.error('[SpeechRecognition start error]:', e);
      setVoiceModalState('error', 'Could not access microphone.');
    }
  }

  function stopRecognition() {
    if (recognitionInstance) {
      try {
        recognitionInstance.stop();
      } catch (e) {
        // already stopped
      }
      recognitionInstance = null;
    }
    setVoiceModalState('ready');
  }

  // Dictate directly into an input or textarea
  function dictateDirectly(targetElement, lang = 'en-US', triggerButton = null) {
    if (!targetElement) return;

    if (!isSpeechRecognitionSupported()) {
      if (window.showToast) {
        window.showToast('Speech recognition is not supported in this browser.', 'warning');
      }
      return;
    }

    if (currentVoiceState === 'listening') {
      stopRecognition();
      if (triggerButton) triggerButton.classList.remove('listening');
      return;
    }

    if (triggerButton) triggerButton.classList.add('listening');

    startRecognition(lang, (text, isFinal) => {
      const currentVal = targetElement.value.trim();
      if (isFinal) {
        targetElement.value = currentVal ? `${currentVal} ${text}` : text;
        if (triggerButton) triggerButton.classList.remove('listening');
        if (window.showToast) {
          window.showToast('Dictation captured into field.', 'success');
        }
      }
    }, () => {
      if (triggerButton) triggerButton.classList.remove('listening');
    });
  }

  // ==========================================
  // 4. WEB SPEECH API: TEXT-TO-SPEECH (TTS)
  // ==========================================
  let isSpeaking = false;

  function stopSpeaking() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      isSpeaking = false;
      updateTtsUi(false);
    }
  }

  function updateTtsUi(active) {
    const playBtn = document.getElementById('ttsPlayBtn');
    const stopBtn = document.getElementById('ttsStopBtn');
    const statusBadge = document.getElementById('ttsStatusBadge');

    if (playBtn) playBtn.disabled = active;
    if (stopBtn) stopBtn.style.display = active ? 'inline-flex' : 'none';
    if (statusBadge) statusBadge.style.display = active ? 'inline-flex' : 'none';
  }

  function speakText(text, lang = 'en') {
    if (!('speechSynthesis' in window)) {
      if (window.showToast) {
        window.showToast('Text-to-speech is not supported in this browser.', 'warning');
      }
      return;
    }

    stopSpeaking();

    if (!text || text.trim() === '') return;

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === 'hi' ? 'hi-IN' : 'en-US';
    utterance.rate = 0.95; // Clear natural rate for healthcare comprehension
    utterance.pitch = 1.0;

    // Try to find a matching voice if available
    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
      const match = voices.find(v => v.lang.startsWith(lang === 'hi' ? 'hi' : 'en'));
      if (match) utterance.voice = match;
    }

    utterance.onstart = () => {
      isSpeaking = true;
      updateTtsUi(true);
    };

    utterance.onend = () => {
      isSpeaking = false;
      updateTtsUi(false);
    };

    utterance.onerror = (e) => {
      console.warn('[TTS Error]:', e);
      isSpeaking = false;
      updateTtsUi(false);
    };

    window.speechSynthesis.speak(utterance);
  }

  // Function to construct clinical voice summary for result page
  function speakScreeningResult(data, lang = 'en') {
    let textToSpeak = '';
    if (lang === 'hi') {
      textToSpeak = `रेटिना-एक्सएआई स्क्रीनिंग रिपोर्ट। रोगी पहचान: ${data.patientId}। ` +
        `एआई मूल्यांकन: श्रेणी ${data.classId}, ${data.prediction}। विश्वास स्तर: ${Math.round(data.confidence)} प्रतिशत। ` +
        `नैदानिक अनुशंसा: ${data.riskStatus}। ${data.referralRequired ? 'विशेषज्ञ नेत्र रोग अस्पताल रेफरल आवश्यक है।' : 'प्राथमिक दृष्टि केंद्र पर नियमित अनुवर्ती जांच।'}`;
    } else {
      textToSpeak = `RETINA-XAI Screening Report for Patient ID ${data.patientId}. ` +
        `AI classification is Severity Grade ${data.classId}, ${data.prediction}, with ${Math.round(data.confidence)} percent confidence. ` +
        `Clinical recommendation: ${data.riskStatus}. ` +
        `${data.referralRequired ? 'Referral to specialist ophthalmologist is strongly advised.' : 'Routine follow-up at primary vision centre.'}`;
    }

    speakText(textToSpeak, lang);
  }

  // ==========================================
  // 5. INITIALIZATION & BINDINGS
  // ==========================================
  document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Theme
    applyTheme(getSavedTheme());
    const themeBtn = document.getElementById('themeToggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', toggleTheme);
    }

    // 2. Initialize Zoom
    applyZoom(getSavedZoom());
    document.querySelectorAll('.zoom-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const level = e.currentTarget.dataset.zoom;
        applyZoom(level);
      });
    });

    // 3. Voice Assistant Modal Event Listeners
    const micBtn = document.getElementById('voiceModalMicBtn');
    const toggleBtn = document.getElementById('voiceModalToggleBtn');
    const langSelect = document.getElementById('voiceModalLangSelect');
    const copyBtn = document.getElementById('voiceCopyBtn');
    const insertBtn = document.getElementById('voiceInsertBtn');
    const clearBtn = document.getElementById('voiceClearBtn');
    const transcriptBox = document.getElementById('voiceTranscriptBox');

    // Sync modal language select with site language
    if (langSelect) {
      const siteLang = window.getCurrentLanguage ? window.getCurrentLanguage() : 'en';
      langSelect.value = siteLang;

      window.addEventListener('languageChanged', (e) => {
        if (langSelect) langSelect.value = e.detail.lang;
      });

      langSelect.addEventListener('change', () => {
        if (currentVoiceState === 'listening') {
          stopRecognition();
          startRecognition(langSelect.value);
        }
      });
    }

    function toggleModalListening() {
      if (currentVoiceState === 'listening') {
        stopRecognition();
      } else {
        const lang = langSelect ? langSelect.value : (window.getCurrentLanguage ? window.getCurrentLanguage() : 'en');
        startRecognition(lang);
      }
    }

    if (micBtn) micBtn.addEventListener('click', toggleModalListening);
    if (toggleBtn) toggleBtn.addEventListener('click', toggleModalListening);

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        currentTranscript = '';
        if (transcriptBox) transcriptBox.textContent = '';
        if (window.showToast) window.showToast('Transcript cleared.', 'info');
      });
    }

    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        if (!currentTranscript) {
          if (window.showToast) window.showToast('No transcript to copy.', 'warning');
          return;
        }
        try {
          await navigator.clipboard.writeText(currentTranscript);
          if (window.showToast) window.showToast('Transcript copied to clipboard!', 'success');
        } catch (err) {
          if (window.showToast) window.showToast('Unable to copy text.', 'danger');
        }
      });
    }

    if (insertBtn) {
      insertBtn.addEventListener('click', () => {
        if (!currentTranscript) {
          if (window.showToast) window.showToast('No speech transcript available.', 'warning');
          return;
        }
        const doctorNotes = document.getElementById('doctorNotes');
        if (doctorNotes) {
          const prev = doctorNotes.value.trim();
          doctorNotes.value = prev ? `${prev}\n${currentTranscript}` : currentTranscript;
          if (window.showToast) window.showToast('Inserted transcript into clinical notes!', 'success');
          // Close modal if open
          const modalEl = document.getElementById('voiceAssistantModal');
          if (modalEl && window.bootstrap) {
            const modal = window.bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
          }
        } else {
          // If not on result page, copy instead
          if (copyBtn) copyBtn.click();
        }
      });
    }

    // Stop speaking when user navigates away or modal closes
    const voiceModal = document.getElementById('voiceAssistantModal');
    if (voiceModal) {
      voiceModal.addEventListener('hidden.bs.modal', () => {
        stopRecognition();
      });
    }

    // Check browser support and inform user if missing
    if (!isSpeechRecognitionSupported()) {
      const warnEl = document.getElementById('voiceUnsupportedAlert');
      if (warnEl) warnEl.classList.remove('d-none');
      if (micBtn) micBtn.classList.add('opacity-50');
    }
  });

  // Export global API
  window.retinaVoice = {
    startRecognition,
    stopRecognition,
    dictateDirectly,
    speakText,
    stopSpeaking,
    speakScreeningResult,
    toggleTheme,
    applyTheme,
    applyZoom,
    isSpeechRecognitionSupported
  };

})();
