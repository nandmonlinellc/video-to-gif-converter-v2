document.addEventListener('DOMContentLoaded', () => {
    // --- Constants for DOM Elements ---
    const form = document.getElementById('converter-form');
    const videoUpload = document.getElementById('video-upload');
    const dropZone = document.getElementById('drop-zone');
    const fileNameDisplay = document.getElementById('file-name-display');
    
    // Video and Cropping Elements
    const videoPreviewContainer = document.getElementById('video-preview-container');
    const videoPreview = document.getElementById('video-preview');
    const initCropBtn = document.getElementById('init-crop-btn');
    const cropContainer = document.getElementById('crop-container');
    const cropImagePreview = document.getElementById('crop-image-preview');
    let cropper = null;

    // Other Elements
    const optionsContainer = document.getElementById('options-container');
    const startTimeInput = document.getElementById('start_time');
    const endTimeInput = document.getElementById('end_time');
    const loadingDiv = document.getElementById('loading');
    const loadingText = loadingDiv.querySelector('p');
    const gifContainer = document.getElementById('gif-container');
    const gifResult = document.getElementById('gif-result');
    const downloadBtn = document.getElementById('download-btn');
    const submitBtn = document.getElementById('submit-btn');
    const errorMessageDiv = document.getElementById('error-message');
    const gifDimensions = document.getElementById('gif-dimensions');
    const historyContainer = document.getElementById('history-container');
    const historyList = document.getElementById('history-list');
    const clearHistoryBtn = document.getElementById('clear-history-btn');
    const textColorHexInput = document.getElementById('text-color-hex'); // For hex color input
    

    const MAX_HISTORY_ITEMS = 5;

    // --- UI Helper Functions ---
    const showElement = (el) => el?.classList.add('visible');
    const hideElement = (el) => el?.classList.remove('visible');

    // --- History Logic ---
    const getHistory = () => {
        try {
            const history = localStorage.getItem('gifHistory');
            return history ? JSON.parse(history) : [];
        } catch (e) {
            console.error("Error parsing GIF history:", e);
            return [];
        }
    };

    const saveToHistory = (newGif) => {
        let history = getHistory();
        history.unshift(newGif);
        history = history.slice(0, MAX_HISTORY_ITEMS);
        localStorage.setItem('gifHistory', JSON.stringify(history));
    };

    const renderHistory = () => {
        if (!historyList) return;
        historyList.innerHTML = '';
        const history = getHistory();
        if (history.length > 0) {
            history.forEach(item => {
                const historyItem = document.createElement('div');
                historyItem.className = 'history-item flex flex-col sm:flex-row items-center p-3 bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-md transition-shadow duration-150 ease-in-out';
                historyItem.innerHTML = `
                    <img src="${item.url}" alt="Recent GIF" class="history-thumbnail w-24 h-24 sm:w-20 sm:h-20 object-contain rounded-md mb-2 sm:mb-0 sm:mr-4 bg-gray-100 dark:bg-gray-700">
                    <div class="history-info text-center sm:text-left">
                        <a href="${item.url}" download class="text-blue-600 dark:text-blue-400 hover:underline font-semibold block mb-1">Download GIF</a>
                        <p class="text-xs text-gray-500 dark:text-gray-400">Dimensions: ${item.width} x ${item.height}px</p>
                    </div>
                `;
                historyList.appendChild(historyItem);
            });
            showElement(historyContainer);
        } else {
            hideElement(historyContainer);
        }
    };

    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', () => {
            localStorage.removeItem('gifHistory');
            renderHistory();
        });
    }
    
    // --- Update Button Text Logic ---
    if (submitBtn) {
        submitBtn.textContent = 'Upload Video'; // Initial state
        submitBtn.disabled = true;
    }

    // Enable and update button after file or URL preview
    const enableConvertButton = () => {
        if (submitBtn) {
            submitBtn.textContent = 'Convert to GIF';
            submitBtn.disabled = false;
        }
    };

    // --- File Upload & UI Flow ---
    const handleFileSelect = (file) => {
        if (!file) {
            if (fileNameDisplay) fileNameDisplay.textContent = 'No file selected';
            if (submitBtn) submitBtn.disabled = true;
            return;
        }
        // Reset UI
        hideElement(gifContainer);
        hideElement(errorMessageDiv);
        hideElement(videoPreviewContainer);
        hideElement(cropContainer);
        hideElement(optionsContainer);
        if(cropper) {
            cropper.destroy();
            cropper = null;
        }

        if(fileNameDisplay) fileNameDisplay.textContent = file.name;
        
        // Show video preview first
        if (videoPreview) {
            videoPreview.src = URL.createObjectURL(file);
            videoPreview.onloadedmetadata = () => {
                if (startTimeInput) startTimeInput.value = 0;
                if (endTimeInput) endTimeInput.value = Math.floor(videoPreview.duration);
                showElement(videoPreviewContainer);
                showElement(optionsContainer);
                enableConvertButton();
            };
        }
    };

    // --- URL Upload & Preview Logic (Two-Step) ---
    const urlInput = document.getElementById('video-url');
    if (urlInput && submitBtn) {
        urlInput.addEventListener('change', async function() {
            const url = urlInput.value.trim();
            if (!url) {
                submitBtn.disabled = true;
                return;
            }
            submitBtn.textContent = 'Uploading...';
            submitBtn.disabled = true;
            // Send URL to backend to download and get preview URL
            try {
                const formData = new FormData();
                formData.append('video_url', url);
                const response = await fetch('/upload_url', { method: 'POST', body: formData });
                const result = await response.json();
                if (response.ok && result.preview_url) {
                    // Show preview using backend-served temp file
                    if (videoPreview) {
                        videoPreview.src = result.preview_url;
                        videoPreview.onloadedmetadata = () => {
                            if (startTimeInput) startTimeInput.value = 0;
                            if (endTimeInput) endTimeInput.value = Math.floor(videoPreview.duration);
                            showElement(videoPreviewContainer);
                            showElement(optionsContainer);
                            submitBtn.textContent = 'Convert to GIF';
                            submitBtn.disabled = false;
                        };
                        showElement(videoPreviewContainer);
                        showElement(optionsContainer);
                    }
                } else {
                    errorMessageDiv.textContent = result.error || 'Failed to fetch video preview.';
                    showElement(errorMessageDiv);
                    submitBtn.textContent = 'Upload Video';
                    submitBtn.disabled = true;
                }
            } catch (err) {
                errorMessageDiv.textContent = 'Network error during video URL upload.';
                showElement(errorMessageDiv);
                submitBtn.textContent = 'Upload Video';
                submitBtn.disabled = true;
            }
        });
    }

    // --- Event Listeners ---
    if (videoUpload) {
        videoUpload.addEventListener('change', (e) => handleFileSelect(e.target.files[0]));
    }
    
    if (dropZone) {
        dropZone.addEventListener('click', () => videoUpload.click());
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
        dropZone.addEventListener('dragleave', (e) => { e.preventDefault(); dropZone.classList.remove('dragover'); });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                videoUpload.files = e.dataTransfer.files;
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });
    }

    if (initCropBtn) {
        initCropBtn.addEventListener('click', () => {
            hideElement(videoPreviewContainer);

            const canvas = document.createElement('canvas');
            canvas.width = videoPreview.videoWidth;
            canvas.height = videoPreview.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(videoPreview, 0, 0, canvas.width, canvas.height);
            
            if (cropImagePreview) {
                cropImagePreview.src = canvas.toDataURL();
            }
            
            showElement(cropContainer);
            if (cropper) {
                cropper.replace(cropImagePreview.src);
            } else {
                cropper = new Cropper(cropImagePreview, {
                    aspectRatio: 0, viewMode: 1, background: false, autoCropArea: 0.8,
                    crop(event) {
                        const data = event.detail;
                        document.querySelector('input[name="crop_x"]').value = Math.round(data.x);
                        document.querySelector('input[name="crop_y"]').value = Math.round(data.y);
                        document.querySelector('input[name="crop_width"]').value = Math.round(data.width);
                        document.querySelector('input[name="crop_height"]').value = Math.round(data.height);
                    },
                });
            }
        });
    }

    // Link color picker and hex input for text color
    const textColorPicker = document.getElementById('text-color');
    if (textColorPicker && textColorHexInput) {
        textColorPicker.addEventListener('input', (e) => textColorHexInput.value = e.target.value);
        textColorHexInput.addEventListener('input', (e) => textColorPicker.value = e.target.value);
    }
    // Advanced: sync color/hex for bg
    const textBgColorPicker = document.getElementById('text-bg-color');
    const textBgColorHex = document.getElementById('text-bg-color-hex');
    if (textBgColorPicker && textBgColorHex) {
        textBgColorPicker.addEventListener('input', (e) => textBgColorHex.value = e.target.value);
        textBgColorHex.addEventListener('input', (e) => textBgColorPicker.value = e.target.value);
    }

    // Handle 'No Background' checkboxes
    const textBgColorNone = document.getElementById('text-bg-color-none');
    if (textBgColorNone && textBgColorPicker && textBgColorHex) {
        textBgColorNone.addEventListener('change', function() {
            if (this.checked) {
                textBgColorPicker.setAttribute('disabled', 'disabled');
                textBgColorHex.setAttribute('disabled', 'disabled');
            } else {
                textBgColorPicker.removeAttribute('disabled');
                textBgColorHex.removeAttribute('disabled');
            }
        });
    }
    // On form submit, set value to 'none' if any 'none' checkbox is checked
    if (form) {
        form.addEventListener('submit', function() {
            if (textBgColorNone && textBgColorNone.checked) {
                // Instead of setting the color input value to 'none', just disable it and set the form value
                const bgColorInput = form.querySelector('[name="text-bg-color"]');
                const bgColorHexInput = form.querySelector('[name="text-bg-color-hex"]');
                if (bgColorInput) bgColorInput.value = '#000000'; // fallback to valid color
                if (bgColorHexInput) bgColorHexInput.value = '#000000'; // fallback to valid color
                // Set the value to 'none' only in the form data, not the input field
                if (bgColorInput) bgColorInput.setAttribute('data-none', 'true');
                if (bgColorHexInput) bgColorHexInput.setAttribute('data-none', 'true');
            } else {
                const bgColorInput = form.querySelector('[name="text-bg-color"]');
                const bgColorHexInput = form.querySelector('[name="text-bg-color-hex"]');
                if (bgColorInput) bgColorInput.removeAttribute('data-none');
                if (bgColorHexInput) bgColorHexInput.removeAttribute('data-none');
            }
        });
    }

    // --- Polling and Form Submit Logic ---
    function pollTaskStatus(taskId) {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/status/${taskId}`);
                const data = await response.json();

                if (data.status === 'SUCCESS') {
                    clearInterval(interval);
                    hideElement(loadingDiv);
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Convert to GIF';
                    
                    // Set the image source to the direct GCS URL for viewing
                    gifResult.src = data.gif_url;
                    
                    // --- THIS IS THE MODIFIED PART ---
                    // Extract the filename from the full GCS URL
                    const gcsUrl = new URL(data.gif_url);
                    const filename = gcsUrl.pathname.split('/').pop();

                    // Point the download button to your Flask download route
                    downloadBtn.href = `/download_gif/${filename}`;
                    // --- END OF MODIFIED PART ---
                    
                    gifDimensions.textContent = `Dimensions: ${data.width}px x ${data.height}px`;
                    showElement(gifContainer);
                    
                    saveToHistory({ url: data.gif_url, width: data.width, height: data.height });
                    renderHistory();

                } else if (data.state === 'FAILURE') {
                    clearInterval(interval);
                    hideElement(loadingDiv);
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Convert to GIF';
                    errorMessageDiv.textContent = data.error || 'Conversion failed in the background.';
                    showElement(errorMessageDiv);
                } else {
                    if (loadingText) loadingText.textContent = data.status || 'Processing...';
                }
            } catch (error) {
                clearInterval(interval);
                hideElement(loadingDiv);
                submitBtn.disabled = false;
                submitBtn.textContent = 'Convert to GIF';
                errorMessageDiv.textContent = 'Error checking task status.';
                showElement(errorMessageDiv);
            }
        }, 2500);
    }

    if (form) {
        form.addEventListener('submit', async function(event) {
            event.preventDefault();
            showElement(loadingDiv);
            if (loadingText) loadingText.textContent = 'Uploading video...';
            hideElement(gifContainer);
            hideElement(errorMessageDiv);
            submitBtn.disabled = true;
            submitBtn.textContent = 'Uploading...';

            const formData = new FormData(form);
            // If no file is selected, but a video URL is provided, ensure the backend gets the URL only
            const fileInput = document.getElementById('video-upload');
            const urlInput = document.getElementById('video-url');
            if (fileInput && fileInput.files.length === 0 && urlInput && urlInput.value.trim() !== '') {
                // Remove the 'video' field if empty to avoid sending an empty file
                formData.delete('video');
            }
            try {
                const response = await fetch('/convert', { method: 'POST', body: formData });
                const result = await response.json();

                if (response.ok && result.task_id) {
                    submitBtn.textContent = 'Converting...';
                    pollTaskStatus(result.task_id);
                } else {
                    errorMessageDiv.textContent = result.error || 'Upload failed.';
                    showElement(errorMessageDiv);
                    hideElement(loadingDiv);
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Convert to GIF';
                }
            } catch (error) {
                errorMessageDiv.textContent = 'A network error occurred during upload.';
                showElement(errorMessageDiv);
                hideElement(loadingDiv);
                submitBtn.disabled = false;
                submitBtn.textContent = 'Convert to GIF';
            }
        });
    }

    // --- Improved Upload Button Logic ---
    // --- Fix for Choose Video File Button and Fallback ---
    const chooseFileBtn = document.getElementById('choose-file-btn');
    const videoUploadFallback = document.getElementById('video-upload-fallback');
    if (chooseFileBtn && videoUpload) {
        chooseFileBtn.addEventListener('click', () => videoUpload.click());
    }
    if (videoUploadFallback && videoUpload) {
        // Only show fallback if main file input is not supported or unavailable
        if (!window.File || !window.FileReader || !window.FileList || !window.Blob) {
            videoUploadFallback.style.display = 'block';
        }
        videoUploadFallback.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                // videoUpload.files = e.target.files; // Not supported in all browsers
                handleFileSelect(e.target.files[0]);
            }
        });
    }
    // Make drop zone itself clickable for upload
    // (Removed duplicate click event listener for dropZone)
    // --- Initial Load ---
    renderHistory();

    // --- Advanced Text Options Toggle ---
    const toggleAdvancedBtn = document.getElementById('toggle-advanced-text');
    const advancedOptions = document.getElementById('advanced-text-options');
    const advancedArrow = document.getElementById('advanced-arrow');
    if (toggleAdvancedBtn && advancedOptions) {
        toggleAdvancedBtn.addEventListener('click', () => {
            const isOpen = !advancedOptions.classList.contains('hidden');
            if (isOpen) {
                advancedOptions.classList.add('hidden');
                advancedArrow.style.transform = '';
            } else {
                advancedOptions.classList.remove('hidden');
                advancedArrow.style.transform = 'rotate(180deg)';
            }
        });
    }

    // --- Tab Navigation Logic ---
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active from all
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(panel => panel.classList.add('hidden'));
            // Activate selected
            btn.classList.add('active');
            const panel = document.getElementById('tab-panel-' + btn.dataset.tab);
            if (panel) panel.classList.remove('hidden');
        });
    });
    // Show first tab by default
    if (tabButtons.length && tabPanels.length) {
        tabButtons[0].classList.add('active');
        tabPanels[0].classList.remove('hidden');
    }
});
