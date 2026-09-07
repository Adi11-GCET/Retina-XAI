/**
 * DrishtiAI Assistant — Intelligent Healthcare Chatbot Client
 * Handles:
 * 1. Floating trigger & responsive drawer/modal UI
 * 2. Asynchronous API communication with /api/chat
 * 3. Quick question chips
 * 4. Hands-free Web Speech API integration (STT input & TTS response readout)
 * 5. Dynamic English/Hindi language synchronization
 * 6. Accessibility & keyboard navigation
 */

(function () {
  'use strict';

  let isChatOpen = false;
  let isListening = false;
  let recognition = null;
  let currentLang = 'en';

  const CHIPS_EN = [
    { text: "What is Diabetic Retinopathy?", query: "What is diabetic retinopathy?" },
    { text: "Explain my result", query: "Explain my latest result." },
    { text: "How do I upload an image?", query: "How do I upload a retinal image?" },
    { text: "My OTP is not working", query: "Why is my OTP not arriving?" },
    { text: "How does Grad-CAM work?", query: "How does Grad-CAM work?" },
    { text: "बातचीत हिंदी में करें", query: "हिंदी में बात करें", switchLang: "hi" }
  ];

  const CHIPS_HI = [
    { text: "डायबिटिक रेटिनोपैथी क्या है?", query: "डायबिटिक रेटिनोपैथी क्या है?" },
    { text: "मेरा परिणाम समझाएं", query: "मेरा नवीनतम परिणाम समझाएं।" },
    { text: "इमेज कैसे अपलोड करें?", query: "रेटिना की इमेज कैसे अपलोड करें?" },
    { text: "OTP नहीं आ रहा?", query: "OTP नहीं आ रहा, क्या करें?" },
    { text: "Grad-CAM क्या है?", query: "Grad-CAM कैसे काम करता है?" },
    { text: "Talk in English", query: "Switch to English", switchLang: "en" }
  ];

  function getActiveLanguage() {
    if (window.getCurrentLanguage) {
      return window.getCurrentLanguage();
    }
    return localStorage.getItem('retina_lang') || 'en';
  }

  function initChatbot() {
    const launcherBtn = document.getElementById('drishtiChatLauncher');
    const chatDrawer = document.getElementById('drishtiChatDrawer');
    const closeBtn = document.getElementById('drishtiChatClose');
    const clearBtn = document.getElementById('drishtiChatClear');
    const langBtn = document.getElementById('drishtiChatLangToggle');
    const sendBtn = document.getElementById('drishtiChatSendBtn');
    const inputEl = document.getElementById('drishtiChatInput');
    const micBtn = document.getElementById('drishtiChatMicBtn');

    currentLang = getActiveLanguage();
    updateLauncherLabel();
    renderQuickChips();

    if (launcherBtn) {
      launcherBtn.addEventListener('click', toggleChat);
    }
    if (closeBtn) {
      closeBtn.addEventListener('click', toggleChat);
    }
    if (clearBtn) {
      clearBtn.addEventListener('click', clearConversation);
    }
    if (langBtn) {
      langBtn.addEventListener('click', toggleChatLanguage);
    }
    if (sendBtn && inputEl) {
      sendBtn.addEventListener('click', () => submitUserMessage());
      inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          submitUserMessage();
        }
      });
    }
    if (micBtn) {
      micBtn.addEventListener('click', toggleVoiceInput);
    }

    // Synchronize when global website language changes
    window.addEventListener('languageChanged', (e) => {
      if (e.detail && e.detail.lang) {
        currentLang = e.detail.lang;
        updateLauncherLabel();
        renderQuickChips();
        updateChatDrawerText();
      }
    });
  }

  function toggleChat() {
    const chatDrawer = document.getElementById('drishtiChatDrawer');
    const launcherBtn = document.getElementById('drishtiChatLauncher');
    if (!chatDrawer) return;

    isChatOpen = !isChatOpen;
    if (isChatOpen) {
      chatDrawer.classList.add('open');
      if (launcherBtn) launcherBtn.classList.add('active');
      const inputEl = document.getElementById('drishtiChatInput');
      if (inputEl) setTimeout(() => inputEl.focus(), 200);
      scrollToBottom();
    } else {
      chatDrawer.classList.remove('open');
      if (launcherBtn) launcherBtn.classList.remove('active');
      if (isListening) stopVoiceInput();
      if (window.retinaVoice && window.retinaVoice.stopSpeaking) {
        window.retinaVoice.stopSpeaking();
      }
    }
  }

  function toggleChatLanguage() {
    currentLang = currentLang === 'en' ? 'hi' : 'en';
    if (window.setLanguage) {
      window.setLanguage(currentLang);
    }
    updateLauncherLabel();
    renderQuickChips();
    updateChatDrawerText();
  }

  function updateLauncherLabel() {
    const labelEl = document.getElementById('drishtiChatLauncherLabel');
    if (labelEl) {
      labelEl.innerText = currentLang === 'hi' ? 'दृष्टिAI से पूछें' : 'Ask DrishtiAI';
    }
  }

  function updateChatDrawerText() {
    const langBtn = document.getElementById('drishtiChatLangToggle');
    if (langBtn) {
      langBtn.innerText = currentLang === 'hi' ? 'English' : 'हिन्दी';
    }
    const inputEl = document.getElementById('drishtiChatInput');
    if (inputEl) {
      inputEl.placeholder = currentLang === 'hi' ? 'पूछें (जैसे: मेरा रिजल्ट समझाएं...)' : 'Ask (e.g. Explain my result...)';
    }
  }

  function renderQuickChips() {
    const chipsContainer = document.getElementById('drishtiChatChips');
    if (!chipsContainer) return;

    const chips = currentLang === 'hi' ? CHIPS_HI : CHIPS_EN;
    chipsContainer.innerHTML = '';
    chips.forEach(chip => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chat-chip-btn';
      btn.innerText = chip.text;
      btn.addEventListener('click', () => {
        if (chip.switchLang) {
          currentLang = chip.switchLang;
          if (window.setLanguage) window.setLanguage(currentLang);
          updateLauncherLabel();
          renderQuickChips();
          updateChatDrawerText();
          return;
        }
        sendChatMessage(chip.query);
      });
      chipsContainer.appendChild(btn);
    });
  }

  function appendMessage(sender, text, isWarning = false, msgLang = null) {
    const container = document.getElementById('drishtiChatMessages');
    if (!container) return;

    const wrapper = document.createElement('div');
    wrapper.className = `chat-msg-wrapper ${sender}`;

    const bubble = document.createElement('div');
    bubble.className = `chat-msg-bubble ${sender}${isWarning ? ' warning-bubble' : ''}`;
    
    // Format simple bolding and bullet lines
    const formatted = text
      .replace(/\n/g, '<br>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    bubble.innerHTML = formatted;

    wrapper.appendChild(bubble);

    // If bot response, add audio readout button
    if (sender === 'bot') {
      const actions = document.createElement('div');
      actions.className = 'chat-msg-actions';

      const ttsBtn = document.createElement('button');
      ttsBtn.type = 'button';
      ttsBtn.className = 'chat-action-btn';
      ttsBtn.title = (msgLang === 'hi' || currentLang === 'hi') ? 'बोलकर सुनें' : 'Read aloud';
      ttsBtn.innerHTML = '<i class="bi bi-volume-up"></i>';
      ttsBtn.addEventListener('click', () => {
        if (window.retinaVoice && window.retinaVoice.speakText) {
          // Clean text of markdown and emoji symbols for clear speech synthesis
          const cleanSpeech = text.replace(/\*\*/g, '').replace(/•/g, '').replace(/[🤖😊👋😄⚠️📋💡🐶☀️]/g, '').trim();
          const speechLang = (msgLang === 'hi' || msgLang === 'hinglish') ? 'hi' : (msgLang || currentLang);
          window.retinaVoice.speakText(cleanSpeech, speechLang);
        }
      });

      actions.appendChild(ttsBtn);
      wrapper.appendChild(actions);
    }

    container.appendChild(wrapper);
    scrollToBottom();
  }

  function showTypingIndicator() {
    const container = document.getElementById('drishtiChatMessages');
    if (!container) return;
    const typing = document.createElement('div');
    typing.id = 'drishtiChatTyping';
    typing.className = 'chat-msg-wrapper bot';
    typing.innerHTML = `
      <div class="chat-msg-bubble bot typing-bubble">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>
    `;
    container.appendChild(typing);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    const el = document.getElementById('drishtiChatTyping');
    if (el) el.remove();
  }

  function scrollToBottom() {
    const container = document.getElementById('drishtiChatMessages');
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }

  function clearConversation() {
    const container = document.getElementById('drishtiChatMessages');
    if (!container) return;
    const isHi = currentLang === 'hi';
    container.innerHTML = `
      <div class="chat-msg-wrapper bot">
        <div class="chat-msg-bubble bot">
          ${isHi ? 
            'नमस्ते! 👋 मैं दृष्टिAI सहायक हूँ। मैं डायबिटिक रेटिनोपैथी तथा ऐप के इस्तेमाल से जुड़े सवालों में आपकी मदद कर सकता हूँ।' : 
            'Namaste! 👋 I am the DrishtiAI Assistant. I can help you understand Diabetic Retinopathy and navigate the DrishtiAI application.'}
        </div>
      </div>
    `;
  }

  function submitUserMessage() {
    const inputEl = document.getElementById('drishtiChatInput');
    if (!inputEl) return;
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = '';
    sendChatMessage(text);
  }

  async function sendChatMessage(text) {
    appendMessage('user', text);
    showTypingIndicator();

    const modeIndicator = document.getElementById('drishtiChatModeBadge');

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: json_payload({ message: text, lang: currentLang })
      });

      removeTypingIndicator();

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const errReply = errData.error || (currentLang === 'hi' ? "सेवा अस्थायी रूप से अनुपलब्ध है।" : "Assistant service temporarily unavailable.");
        appendMessage('bot', errReply);
        return;
      }

      const data = await response.json();
      if (modeIndicator && data.mode) {
        modeIndicator.innerText = data.mode === 'ai' ? 'Live AI' : 'Clinical FAQ';
      }
      appendMessage('bot', data.reply || '', data.is_medical_warning || false, data.detected_lang || currentLang);

    } catch (err) {
      removeTypingIndicator();
      const offlineReply = currentLang === 'hi' ? 
        "नेटवर्क समस्या। कृपया पुनः प्रयास करें।" : 
        "Network connection issue. Please verify your connection and retry.";
      appendMessage('bot', offlineReply);
    }
  }

  function json_payload(obj) {
    return JSON.stringify(obj);
  }

  // -------------------------------------------------------------------
  // Speech Recognition (Voice Input)
  // -------------------------------------------------------------------
  function toggleVoiceInput() {
    if (isListening) {
      stopVoiceInput();
    } else {
      startVoiceInput();
    }
  }

  function startVoiceInput() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition || null;
    const micBtn = document.getElementById('drishtiChatMicBtn');
    const inputEl = document.getElementById('drishtiChatInput');

    if (!SpeechRec) {
      const msg = currentLang === 'hi' ? 
        "आपके ब्राउज़र में स्पीच रिकॉग्निशन उपलब्ध नहीं है। कृपया टाइप करें।" : 
        "Speech recognition is not supported in this browser. Please type your question.";
      if (window.showToast) window.showToast(msg, 'warning');
      else alert(msg);
      return;
    }

    try {
      recognition = new SpeechRec();
      recognition.lang = currentLang === 'hi' ? 'hi-IN' : 'en-IN';
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onstart = () => {
        isListening = true;
        if (micBtn) {
          micBtn.classList.add('listening');
          micBtn.innerHTML = '<i class="bi bi-stop-circle-fill text-danger"></i>';
        }
        if (inputEl) {
          inputEl.placeholder = currentLang === 'hi' ? 'सुन रहा हूँ... बोलिए' : 'Listening... speak now';
        }
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (inputEl && transcript) {
          inputEl.value = transcript;
          submitUserMessage();
        }
      };

      recognition.onerror = () => {
        stopVoiceInput();
      };

      recognition.onend = () => {
        stopVoiceInput();
      };

      recognition.start();
    } catch (e) {
      stopVoiceInput();
    }
  }

  function stopVoiceInput() {
    isListening = false;
    const micBtn = document.getElementById('drishtiChatMicBtn');
    const inputEl = document.getElementById('drishtiChatInput');

    if (micBtn) {
      micBtn.classList.remove('listening');
      micBtn.innerHTML = '<i class="bi bi-mic-fill"></i>';
    }
    if (inputEl) {
      updateChatDrawerText();
    }
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
      recognition = null;
    }
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChatbot);
  } else {
    initChatbot();
  }

})();
