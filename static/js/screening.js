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

      const formData = new FormData();
      if (selectedFile) {
        formData.append('image', selectedFile);
      } else if (selectedSample) {
        formData.append('sample_name', selectedSample);
      }

      try {
        // Stage animations while fetch runs
        const t1 = setTimeout(() => setStage(1), 500);
        const t2 = setTimeout(() => setStage(2), 1100);
        const t3 = setTimeout(() => setStage(3), 1800);
        const t4 = setTimeout(() => setStage(4), 2400);

        const response = await fetch('/predict', {
          method: 'POST',
          body: formData
        });

        const result = await response.json();

        // Clear timers if finished sooner
        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
        clearTimeout(t4);

        if (result.success && result.redirect_url) {
          setStage(4);
          setTimeout(() => {
            window.location.href = result.redirect_url;
          }, 600);
        } else {
          processingOverlay.style.display = 'none';
          showToast(result.error || 'AI analysis is temporarily unavailable. Please try again.', 'danger');
        }
      } catch (err) {
        console.error(err);
        processingOverlay.style.display = 'none';
        showToast('Unable to complete AI analysis. Please check image and try again.', 'danger');
      }
    });
  }
});
