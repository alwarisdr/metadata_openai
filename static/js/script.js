document.addEventListener('DOMContentLoaded', function() {
    const apiKeyForm = document.getElementById('api-key-form');
    const uploadForm = document.getElementById('upload-form');
    const statusDiv = document.getElementById('status');
    const resultDiv = document.getElementById('result');

    apiKeyForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const apiKey = document.getElementById('gemini-api-key').value;
        fetch('/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'gemini_api_key=' + encodeURIComponent(apiKey)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('API key saved successfully');
                uploadForm.style.display = 'block';
            } else {
                alert('Failed to save API key');
            }
        });
    });

    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        fetch('/', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'processing') {
                statusDiv.textContent = 'Processing...';
                checkStatus();
            } else {
                alert(data.message);
            }
        });
    });

    function checkStatus() {
        fetch('/status')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'processing') {
                statusDiv.textContent = 'Processing...';
                setTimeout(checkStatus, 5000);
            } else if (data.status === 'done') {
                statusDiv.textContent = 'Done';
                resultDiv.innerHTML = `
                    <p>Processing complete.</p>
                    <p>Files with embedded keywords and metadata.csv are now available in the 'uploads' folder.</p>
                    <a href="${data.download_url}" download>Download metadata.csv</a>
                `;
            }
        });
    }
});