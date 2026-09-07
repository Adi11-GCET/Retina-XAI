document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('uploadDropzone');
  const fileInput = document.getElementById('retinaFileInput');
  const previewCard = document.getElementById('previewCard');
  const previewImage = document.getElementById('previewImage');
  const previewFilename = document.getElementById('previewFilename');
  const previewFilesize = document.getElementById('previewFilesize');
  const removeBtn = document.getElementById('removeImageBtn');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const screeningForm = document.getElementById('screeningForm');
  const processingOverlay = document.getElementById('processingOverlay');
  const samplePills = document.querySelectorAll('.sample-pill-btn');
  const sampleInput = document.getElementById('sampleInput');

  let selectedFile = null;
  let selectedSample = null;

  if (!dropzone || !fileInput) return;

  // Drag & drop handlers
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  });

  dropzone.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  });

  function handleFile(file) {
    // Validate file type
    const validTypes = ['image/jpeg', 'image/png', 'image/jpg'];
    if (!validTypes.includes(file.type.toLowerCase())) {
      showToast('Please upload a valid JPG or PNG retinal fundus image.', 'danger');
      return;
    }

    // Validate size (10 MB max)
    if (file.size > 10 * 1024 * 1024) {
      showToast('Maximum file size is 10 MB. Please choose a smaller image.', 'danger');
      return;
    }

    selectedFile = file;
    selectedSample = null;
    sampleInput.value = '';
    samplePills.forEach(p => p.classList.remove('active'));

    const reader = new FileReader();
    reader.onload = (e) => {
      previewImage.src = e.target.result;
      previewFilename.textContent = file.name;
      previewFilesize.textContent = (file.size / (1024 * 1024)).toFixed(2) + ' MB';
      
      dropzone.classList.add('d-none');
      previewCard.classList.remove('d-none');
      analyzeBtn.removeAttribute('disabled');
    };
    reader.readAsDataURL(file);
  }

  // Sample images selector
  samplePills.forEach(pill => {
    pill.addEventListener('click', (e) => {
      const sampleFile = pill.dataset.sample;
      const sampleLabel = pill.dataset.label;
      const sampleImgSrc = pill.dataset.src;

      selectedSample = sampleFile;
      selectedFile = null;
      fileInput.value = '';
      sampleInput.value = sampleFile;

      samplePills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');

      previewImage.src = sampleImgSrc;
      previewFilename.textContent = sampleLabel + " (Clinical Sample)";
      previewFilesize.textContent = "Preloaded Reference Case";

      dropzone.classList.add('d-none');
      previewCard.classList.remove('d-none');
      analyzeBtn.removeAttribute('disabled');
    });
  });

  // Remove button
  if (removeBtn) {
    removeBtn.addEventListener('click', () => {
      selectedFile = null;
      selectedSample = null;
      fileInput.value = '';
      sampleInput.value = '';
      samplePills.forEach(p => p.classList.remove('active'));
      
      dropzone.classList.remove('d-none');
      previewCard.classList.add('d-none');
      analyzeBtn.setAttribute('disabled', 'true');
    });
  }

  // Form submission & multi-stage progress
  if (screeningForm) {
    screeningForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      if (!selectedFile && !selectedSample) {
        showToast('Please select or upload a retinal image before analysis.', 'warning');
        return;
      }

      // Show processing overlay
      processingOverlay.style.display = 'flex';

      const stages = [
        document.getElementById('stage-1'),
        document.getElementById('stage-2'),
        document.getElementById('stage-3'),
        document.getElementById('stage-4'),
        document.getElementById('stage-5')
      ];

      function setStage(idx) {
        stages.forEach((st, i) => {
          if (!st) return;
          if (i < idx) {
            st.className = 'stage-item done';
            st.querySelector('.stage-icon').className = 'bi bi-check-circle-fill stage-icon';
          } else if (i === idx) {
            st.className = 'stage-item active';
            st.querySelector('.stage-icon').className = 'spinner-border spinner-border-sm stage-icon';
          } else {
            st.className = 'stage-item';
            st.querySelector('.stage-icon').className = 'bi bi-circle stage-icon';
          }
        });
      }

      setStage(0);

      // Continuous status cycler for Render free tier / CPU execution
      const dynamicStatus = document.getElementById('dynamicStatusNotice');
      const statusCycleMessages = [
        "Analyzing retinal image structure & illumination...",
        "Evaluating microaneurysms and vascular caliber...",
        "Executing PyTorch neural inference (IDRiD weights)...",
        "Computing Grad-CAM saliency heatmaps...",
        "Synthesizing pixel lesion segmentation...",
        "Structuring clinical findings and referral advisory...",
        "Finalizing diagnostic report..."
      ];
      let msgIndex = 0;
      if (dynamicStatus) {
        dynamicStatus.innerHTML = `<i class="bi bi-cpu me-1"></i> ${statusCycleMessages[0]}`;
      }
      const statusInterval = setInterval(() => {
        msgIndex = (msgIndex + 1) % statusCycleMessages.length;
        if (dynamicStatus) {
          dynamicStatus.innerHTML = `<i class="bi bi-cpu me-1"></i> ${statusCycleMessages[msgIndex]}`;
        }
      }, 2800);

      let currentStage = 0;
      const stageTimer = setInterval(() => {
        if (currentStage < 3) {
          currentStage++;
          setStage(currentStage);
        }
      }, 2400);

      const formData = new FormData();
      if (selectedFile) {
        formData.append('image', selectedFile);
      } else if (selectedSample) {
        formData.append('sample_name', selectedSample);
      }

      try {
        const response = await fetch('/predict', {
          method: 'POST',
          body: formData
        });

        const result = await response.json();

        clearInterval(statusInterval);
        clearInterval(stageTimer);

        if (result.success && result.redirect_url) {
          setStage(4);
          if (dynamicStatus) {
            dynamicStatus.innerHTML = '<i class="bi bi-check-circle-fill text-success me-1"></i> Analysis complete! Loading clinical report...';
          }
          setTimeout(() => {
            window.location.href = result.redirect_url;
          }, 450);
        } else {
          processingOverlay.style.display = 'none';
          const errMsg = result.error || 'AI analysis is temporarily unavailable. Please try again.';
          showToast(errMsg, 'danger');

          // If image quality check failed, display structured guidance
          const qualityCard = document.getElementById('qualityGuidanceCard');
          const reasonEl = document.getElementById('qualityErrorReason');
          const guideEl = document.getElementById('qualityErrorGuidance');

          if (result.is_invalid_image && qualityCard && reasonEl && guideEl) {
            reasonEl.textContent = result.reason || 'Image does not meet quality requirements for diagnostic evaluation.';
            guideEl.textContent = result.guidance || 'Please upload an authentic, clear retinal fundus photograph.';
            qualityCard.classList.remove('d-none');
            qualityCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }

          if (result.is_invalid_image && window.retinaVoice && window.retinaVoice.speakText) {
            const lang = window.getCurrentLanguage ? window.getCurrentLanguage() : 'en';
            const alertText = lang === 'hi'
              ? 'अमान्य छवि। ' + (result.reason || '')
              : 'Invalid image. ' + (result.reason || 'Please upload a standard retinal fundus photograph.');
            window.retinaVoice.speakText(alertText, lang);
          }
        }
      } catch (err) {
        console.error(err);
        clearInterval(statusInterval);
        clearInterval(stageTimer);
        processingOverlay.style.display = 'none';
        showToast('Unable to complete AI analysis. The server took too long to respond. Please check image and try again.', 'danger');
      }
    });
  }
});
