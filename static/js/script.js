document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('converter-form');
    const videoUpload = document.getElementById('video-upload');
    const dropZone = document.getElementById('drop-zone');
    const fileNameDisplay = document.getElementById('file-name-display');
    
    const videoPreviewContainer = document.getElementById('video-preview-container');
    const videoPreview = document.getElementById('video-preview');
    const optionsContainer = document.getElementById('options-container');

    const startTimeInput = document.getElementById('start_time');
    const endTimeInput = document.getElementById('end_time');
    
    const loadingDiv = document.getElementById('loading');
    const gifContainer = document.getElementById('gif-container');
    const gifResult = document.getElementById('gif-result');
    const downloadBtn = document.getElementById('download-btn');
    const submitBtn = document.getElementById('submit-btn');
    const errorMessageDiv = document.getElementById('error-message');

    // Helper function to show an element with transition
    function showElement(el) {
        if (!el) return;
        el.classList.add('visible');
    }

    // Helper function to hide an element with transition
    function hideElement(el) {
        if (!el) return;
        el.classList.remove('visible');
    }

    // --- Drag and Drop Logic ---
    dropZone.addEventListener('click', () => videoUpload.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            videoUpload.files = files;
            // Manually trigger the 'change' event
            const changeEvent = new Event('change', { bubbles: true });
            videoUpload.dispatchEvent(changeEvent);
        }
    });

    // --- File Input Change Logic ---
    const handleFileSelect = (event) => {
        hideElement(gifContainer);
        hideElement(errorMessageDiv);
        hideElement(videoPreviewContainer);
        hideElement(optionsContainer);

        const file = event.target.files[0];
        if (file) {
            const videoURL = URL.createObjectURL(file);
            videoPreview.src = videoURL;
            fileNameDisplay.textContent = file.name;
            
            videoPreview.onloadedmetadata = () => {
                // No need to revoke, as it's used by the video element
                startTimeInput.value = 0;
                endTimeInput.value = Math.floor(videoPreview.duration);
                showElement(videoPreviewContainer);
                showElement(optionsContainer);
            };
        } else {
            fileNameDisplay.textContent = 'No file selected';
        }
    };

    videoUpload.addEventListener('change', handleFileSelect);

    // --- Form Submission Logic ---
    form.addEventListener('submit', async function(event) {
        event.preventDefault();

        showElement(loadingDiv);
        hideElement(gifContainer);
        hideElement(errorMessageDiv);
        submitBtn.disabled = true;
        submitBtn.textContent = 'Converting...';

        const formData = new FormData(form);

        try {
            const response = await fetch('/convert', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (response.ok) {
                gifResult.src = result.gif_url;
                downloadBtn.href = result.gif_url;
                showElement(gifContainer);
            } else {
                errorMessageDiv.textContent = result.error || 'An unknown error occurred.';
                showElement(errorMessageDiv);
            }

        } catch (error) {
            errorMessageDiv.textContent = 'A network error occurred. Please try again.';
            showElement(errorMessageDiv);
        } finally {
            hideElement(loadingDiv);
            submitBtn.disabled = false;
            submitBtn.textContent = 'Convert to GIF';
        }
    });
});
