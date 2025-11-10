let currentSection = 'people';
let cameraStreams = {};
let capturedImages = {};

const TAIPEI_TIMEZONE = 'Asia/Taipei';
const taipeiDateFormatter = new Intl.DateTimeFormat(undefined, {
    timeZone: TAIPEI_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
});
const taipeiTimeFormatter = new Intl.DateTimeFormat(undefined, {
    timeZone: TAIPEI_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
});
const taipeiDateTimeFormatter = new Intl.DateTimeFormat(undefined, {
    timeZone: TAIPEI_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
});

function formatTaipeiDate(isoString) {
    if (!isoString) return '';
    return taipeiDateFormatter.format(new Date(isoString));
}

function formatTaipeiTime(isoString) {
    if (!isoString) return '';
    return taipeiTimeFormatter.format(new Date(isoString));
}

function formatTaipeiDateTime(isoString) {
    if (!isoString) return '';
    return taipeiDateTimeFormatter.format(new Date(isoString));
}

function showElement(element) {
    if (element) {
        element.removeAttribute('hidden');
    }
}

function hideElement(element) {
    if (element) {
        element.setAttribute('hidden', '');
    }
}

// TTS Voice Feedback Function
function speakFeedback(message, isSuccess) {
    // Check if browser supports Speech Synthesis
    if ('speechSynthesis' in window) {
        // Cancel any ongoing speech
        window.speechSynthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(message);
        
        // Configure voice settings
        utterance.lang = 'en-GB'; // English (UK)
        utterance.rate = 1.0; // Normal speed
        utterance.pitch = isSuccess ? 1.2 : 0.8; // Higher pitch for success, lower for failure
        utterance.volume = 1.0; // Full volume
        
        // Speak the message
        window.speechSynthesis.speak(utterance);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadPeople();
    setupFormHandlers();
    showSection('people');
    initializeEnrollmentCamera();
});
function showSection(section) {
    document.querySelectorAll('.section-content').forEach(el => {
        el.style.display = 'none';
    });
    document.getElementById(`${section}-section`).style.display = 'block';
    currentSection = section;
    document.querySelectorAll('nav a').forEach(el => {
        el.classList.remove('active');
    });
    document.querySelector(`nav a[href="#${section}"]`)?.classList.add('active');
    if (section === 'attendance') {
        setTimeout(() => initializeAttendanceCamera(), 100);
    }
}
function setupFormHandlers() {
    document.getElementById('person-form').addEventListener('submit', handlePersonSubmit);
    
    // Role selection handlers
    document.querySelectorAll('input[name="role"]').forEach(radio => {
        radio.addEventListener('change', handleRoleChange);
    });
    
    ['person-school', 'person-year', 'person-firstname', 'person-lastname'].forEach(fieldId => {
        document.getElementById(fieldId).addEventListener('input', updateEnrollButtonState);
    });
    document.getElementById('person-name').addEventListener('input', updateEnrollButtonState);
    document.getElementById('person-timezone').addEventListener('change', updateEnrollButtonState);
    document.getElementById('manual-attendance-form').addEventListener('submit', handleManualAttendance);
}

function handleRoleChange(event) {
    const role = event.target.value;
    const studentFields = document.getElementById('student-fields');
    const teacherStaffFields = document.getElementById('teacher-staff-fields');
    
    if (role === 'student') {
        studentFields.style.display = 'block';
        teacherStaffFields.style.display = 'none';
        
        // Set student fields as required
        document.getElementById('person-school').required = true;
        document.getElementById('person-year').required = true;
        document.getElementById('person-firstname').required = true;
        document.getElementById('person-lastname').required = true;
        document.getElementById('person-name').required = false;
        
        // Clear teacher/staff field
        document.getElementById('person-name').value = '';
    } else {
        studentFields.style.display = 'none';
        teacherStaffFields.style.display = 'block';
        
        // Set teacher/staff fields as required
        document.getElementById('person-school').required = false;
        document.getElementById('person-year').required = false;
        document.getElementById('person-firstname').required = false;
        document.getElementById('person-lastname').required = false;
        document.getElementById('person-name').required = true;
        
        // Clear student fields
        document.getElementById('person-school').value = '';
        document.getElementById('person-year').value = '';
        document.getElementById('person-firstname').value = '';
        document.getElementById('person-lastname').value = '';
    }
    
    updateEnrollButtonState();
}
async function initializeEnrollmentCamera() {
    const video = document.getElementById('person-camera');
    const captureBtn = document.getElementById('person-capture-btn');
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: 'user',
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }, 
            audio: false 
        });
        
        video.srcObject = stream;
        cameraStreams['person-camera'] = stream;
        
        video.onloadedmetadata = () => {
            showElement(captureBtn);
        };
        
    } catch (error) {
        console.error('Camera error:', error);
        console.error('Camera initialization error:', error);
    }
}

function updateEnrollButtonState() {
    const role = document.querySelector('input[name="role"]:checked').value;
    const timeZone = document.getElementById('person-timezone').value;
    const hasPhoto = capturedImages['person'] !== undefined;
    const enrollBtn = document.getElementById('enroll-btn');
    
    let allFieldsFilled = false;
    
    if (role === 'student') {
        const school = document.getElementById('person-school').value.trim();
        const year = document.getElementById('person-year').value.trim();
        const firstName = document.getElementById('person-firstname').value.trim();
        const lastName = document.getElementById('person-lastname').value.trim();
        allFieldsFilled = school && year && firstName && lastName && timeZone;
    } else {
        const name = document.getElementById('person-name').value.trim();
        allFieldsFilled = name && timeZone;
    }
    
    if (allFieldsFilled && hasPhoto) {
        enrollBtn.disabled = false;
        enrollBtn.textContent = 'Enroll Person';
    } else if (allFieldsFilled && !hasPhoto) {
        enrollBtn.disabled = true;
        enrollBtn.textContent = 'Capture Photo First';
    } else {
        enrollBtn.disabled = true;
        enrollBtn.textContent = 'Enroll Person';
    }
}

function stopCamera(videoId) {
    const video = document.getElementById(videoId);
    const captureBtn = document.getElementById(`${videoId.replace('-camera', '-capture-btn')}`);

    if (!video || !captureBtn) {
        return;
    }
    
    if (cameraStreams[videoId]) {
        cameraStreams[videoId].getTracks().forEach(track => track.stop());
        delete cameraStreams[videoId];
    }
    
    hideElement(video);
    hideElement(captureBtn);
    video.srcObject = null;
}

function capturePhoto(prefix) {
    const video = document.getElementById(`${prefix}-camera`);
    const canvas = document.getElementById(`${prefix}-canvas`);
    const preview = document.getElementById(`${prefix}-preview`);
    const previewImg = document.getElementById(`${prefix}-preview-img`);
    const captureBtn = document.getElementById(`${prefix}-capture-btn`);
    const retakeBtn = document.getElementById(`${prefix}-retake-btn`);
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    
    canvas.toBlob((blob) => {
        capturedImages[prefix] = blob;
        const url = URL.createObjectURL(blob);
        
        if (previewImg) {
            previewImg.src = url;
            showElement(preview);
        } else {
            preview.innerHTML = `<img src="${url}" alt="Captured photo">`;
        }
        hideElement(video);
        hideElement(captureBtn);
        showElement(retakeBtn);
        const overlay = document.getElementById(`${prefix}-camera-overlay`);
        hideElement(overlay);
        updateEnrollButtonState();
    }, 'image/jpeg', 0.9);
}

function retakePhoto(prefix) {
    const video = document.getElementById(`${prefix}-camera`);
    const preview = document.getElementById(`${prefix}-preview`);
    const captureBtn = document.getElementById(`${prefix}-capture-btn`);
    const retakeBtn = document.getElementById(`${prefix}-retake-btn`);
    
    delete capturedImages[prefix];
    hideElement(preview);
    showElement(video);
    showElement(captureBtn);
    hideElement(retakeBtn);
    const overlay = document.getElementById(`${prefix}-camera-overlay`);
    showElement(overlay);
    updateEnrollButtonState();
}
async function loadPeople() {
    const tableBody = document.getElementById('students-table-body');
    const countDiv = document.getElementById('students-count');
    
    tableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 2rem;"><span class="loading"></span> Loading people...</td></tr>';
    
    try {
        const response = await fetch('/api/people');
        const people = await response.json();
        
        if (people.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 2rem; color: var(--muted-color);">No people enrolled yet. Add someone above!</td></tr>';
            countDiv.textContent = 'Total: 0 people';
            return;
        }
        
        people.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
        
        tableBody.innerHTML = people.map(person => `
            <tr data-student-id="${person.ident.toLowerCase()}">
                <td class="student-id-cell">${person.ident}</td>
                <td>${person.time_zone || 'Not set'}</td>
                <td>
                    <div class="date-cell">
                        <span class="date">${formatTaipeiDate(person.created_at)}</span>
                        <span class="time">${formatTaipeiTime(person.created_at)}</span>
                    </div>
                </td>
                <td class="actions-cell">
                    <a onclick="deletePerson('${person.ident.replace(/'/g, "\\'")}')">Delete</a>
                </td>
            </tr>
        `).join('');
        
        countDiv.textContent = `Total: ${people.length} ${people.length !== 1 ? 'people' : 'person'}`;
        
    } catch (error) {
        tableBody.innerHTML = `<tr><td colspan="4"><div class="result-message error">Error loading people: ${error.message}</div></td></tr>`;
        countDiv.textContent = '';
    }
}

function filterStudents() {
    const searchInput = document.getElementById('student-search');
    const filter = searchInput.value.toLowerCase();
    const table = document.getElementById('students-table');
    const rows = table.getElementsByTagName('tr');
    let visibleCount = 0;
    
    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const studentId = row.getAttribute('data-student-id');
        
        if (studentId) {
            if (studentId.includes(filter)) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        }
    }
    
    const countDiv = document.getElementById('students-count');
    const totalCount = rows.length - 1;
    const pluralLabel = totalCount !== 1 ? 'people' : 'person';
    if (filter) {
        countDiv.textContent = `Showing: ${visibleCount} of ${totalCount} ${pluralLabel}`;
    } else {
        countDiv.textContent = `Total: ${totalCount} ${pluralLabel}`;
    }
}

async function handlePersonSubmit(event) {
    event.preventDefault();
    console.log('Form submitted');
    
    const form = event.target;
    const formData = new FormData(form);
    const resultDiv = document.getElementById('person-form-result');
    
    const role = formData.get('role');
    console.log('Role:', role);
    let ident = '';
    
    if (role === 'student') {
        const school = formData.get('school').trim();
        const year = formData.get('year').trim();
        const firstName = formData.get('first_name').trim();
        const lastName = formData.get('last_name').trim();
        ident = `${school}${year} ${firstName} ${lastName}`;
    } else if (role === 'teacher') {
        const name = formData.get('name').trim();
        ident = `TEACHER ${name}`;
    } else if (role === 'staff') {
        const name = formData.get('name').trim();
        ident = `STAFF ${name}`;
    }
    
    console.log('Generated ident:', ident);
    
    // Check if photo was captured
    if (!capturedImages['person']) {
        showEnrollmentResult('failure', '', 'Please capture a photo');
        return;
    }
    
    // Show checking overlay
    showEnrollmentResult('checking', '', ident);
    
    try {
        const checkResponse = await fetch(`/api/people/${encodeURIComponent(ident)}`);
        
        if (checkResponse.ok) {
            showEnrollmentResult('failure', '', 'Already enrolled');
            return;
        }
    } catch (error) {
        // 404 is expected if person doesn't exist (which is good)
        if (error.message && !error.message.includes('404')) {
            console.error('Duplicate check error:', error);
            showEnrollmentResult('failure', '', 'Check failed');
            return;
        }
    }
    
    // Create new FormData with only the necessary fields
    const submitFormData = new FormData();
    submitFormData.append('ident', ident);
    submitFormData.append('time_zone', formData.get('time_zone'));
    
    if (capturedImages['person']) {
        submitFormData.append('face_photo', capturedImages['person'], 'captured.jpg');
        console.log('Photo added to form data');
    }
    
    // Show processing overlay
    showEnrollmentResult('processing', '', 'Enrolling...');
    
    try {
        console.log('Sending enrollment request...');
        const response = await fetch('/api/people', {
            method: 'POST',
            body: submitFormData
        });
        
        console.log('Response status:', response.status);
        
        if (response.ok) {
            showEnrollmentResult('success', ident);
            delete capturedImages['person'];
            resetPersonForm();
            loadPeople();
        } else {
            const error = await response.text();
            console.error('Enrollment error:', error);
            showEnrollmentResult('failure', '', 'Enrollment failed');
        }
    } catch (error) {
        console.error('Request error:', error);
        showEnrollmentResult('failure', '', 'Network error');
    }
}

function resetPersonForm() {
    const form = document.getElementById('person-form');
    form.reset();
    
    // Reset to student role by default
    document.getElementById('role-student').checked = true;
    handleRoleChange({ target: { value: 'student' } });

    delete capturedImages['person'];

    const preview = document.getElementById('person-preview');
    const previewImg = document.getElementById('person-preview-img');
    hideElement(preview);
    if (previewImg) {
        previewImg.src = '';
    }
    
    const video = document.getElementById('person-camera');
    const captureBtn = document.getElementById('person-capture-btn');
    const retakeBtn = document.getElementById('person-retake-btn');
    const overlay = document.getElementById('person-camera-overlay');
    
    showElement(video);
    showElement(captureBtn);
    hideElement(retakeBtn);
    showElement(overlay);

    if (!cameraStreams['person-camera']) {
        initializeEnrollmentCamera();
    }

    updateEnrollButtonState();
}

async function deletePerson(ident) {
    if (!confirm(`Are you sure you want to delete ${ident}?`)) return;
    
    try {
        const response = await fetch(`/api/people/${ident}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadPeople();
        } else {
            const error = await response.text();
            alert(`Error: ${error}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function initializeAttendanceCamera() {
    const video = document.getElementById('attendance-camera');
    const punchBtn = document.getElementById('punch-btn');
    
    if (cameraStreams['attendance-camera']) {
        punchBtn.disabled = false;
        return;
    }
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: 'user',
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            }, 
            audio: false 
        });
        
        video.srcObject = stream;
        cameraStreams['attendance-camera'] = stream;
        
        video.onloadedmetadata = () => {
            if (statusText) {
                statusText.textContent = 'Camera ready.';
            }
            punchBtn.disabled = false;
        };
        
    } catch (error) {
        if (statusText) {
            statusText.textContent = `Camera error: ${error.message}. Please use manual punch below.`;
        }
        punchBtn.disabled = true;
        console.error('Attendance camera initialization error:', error);
    }
}

async function handleFacialPunch() {
    const video = document.getElementById('attendance-camera');
    const canvas = document.getElementById('attendance-canvas');
    const punchBtn = document.getElementById('punch-btn');
    
    punchBtn.disabled = true;
    punchBtn.innerHTML = '<span class="loading"></span> PROCESSING...';
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    
    canvas.toBlob(async (blob) => {
        try {
            const verifyFormData = new FormData();
            verifyFormData.append('image', blob, 'face.jpg');
            verifyFormData.append('threshold', '0.50');
            verifyFormData.append('top_k', '1');
            
            const verifyResponse = await fetch('/api/face/verify', {
                method: 'POST',
                body: verifyFormData
            });
            
            if (!verifyResponse.ok) {
                throw new Error('Face verification failed');
            }
            
            const verifyResult = await verifyResponse.json();
            
            if (!verifyResult.match || !verifyResult.ident) {
                // Show failure overlay
                showAttendanceResult(false, null);
                // Voice feedback for failure
                speakFeedback('Attendance failed. Please try again.', false);
                resetPunchButton();
                return;
            }
            
            const punchFormData = new FormData();
            punchFormData.append('ident', verifyResult.ident);
            punchFormData.append('image', blob, 'attendance.jpg');
            
            const punchResponse = await fetch('/api/punch', {
                method: 'POST',
                body: punchFormData
            });
            
            if (punchResponse.ok) {
                const punchResult = await punchResponse.json();
                
                // Show success overlay
                showAttendanceResult(true, punchResult.ident);
                
                // Voice feedback for success
                speakFeedback('Attendance recorded successfully.', true);
            } else {
                const error = await punchResponse.text();
                throw new Error(error);
            }
            
        } catch (error) {
            console.error('Attendance error:', error);
            // Show failure overlay
            showAttendanceResult(false, null);
            // Voice feedback for error/failure
            speakFeedback('Attendance failed. Please try again.', false);
        } finally {
            resetPunchButton();
        }
    }, 'image/jpeg', 0.95);
}

function showAttendanceResult(isSuccess, ident) {
    const overlay = document.getElementById('attendance-result-overlay');
    const icon = document.getElementById('result-icon');
    const text = document.getElementById('result-text');
    const identDiv = document.getElementById('result-ident');
    
    // Remove previous classes
    overlay.classList.remove('success', 'failure', 'show');
    
    if (isSuccess) {
        overlay.classList.add('success');
        icon.textContent = '✓';
        text.textContent = 'SUCCESS';
        identDiv.textContent = ident || '';
    } else {
        overlay.classList.add('failure');
        icon.textContent = '✗';
        text.textContent = 'FAILED';
        identDiv.textContent = 'Please try again';
    }
    
    // Show overlay with animation
    setTimeout(() => {
        overlay.classList.add('show');
    }, 50);
    
    // Hide overlay after 3 seconds
    setTimeout(() => {
        overlay.classList.remove('show');
    }, 3000);
}

function showEnrollmentResult(status, ident, message) {
    const overlay = document.getElementById('enrollment-result-overlay');
    const icon = document.getElementById('enrollment-result-icon');
    const text = document.getElementById('enrollment-result-text');
    const identDiv = document.getElementById('enrollment-result-ident');
    
    // Remove previous classes
    overlay.classList.remove('success', 'failure', 'processing', 'show');
    
    if (status === 'success') {
        overlay.classList.add('success');
        icon.textContent = '✓';
        text.textContent = 'ENROLLED';
        identDiv.textContent = ident || '';
    } else if (status === 'processing') {
        overlay.classList.add('processing');
        icon.innerHTML = '<span class="loading"></span>';
        text.textContent = message || 'PROCESSING...';
        identDiv.textContent = '';
    } else if (status === 'checking') {
        overlay.classList.add('processing');
        icon.innerHTML = '<span class="loading"></span>';
        text.textContent = 'CHECKING...';
        identDiv.textContent = message || '';
    } else {
        overlay.classList.add('failure');
        icon.textContent = '✗';
        text.textContent = 'FAILED';
        identDiv.textContent = message || 'Please try again';
    }
    
    // Show overlay with animation
    setTimeout(() => {
        overlay.classList.add('show');
    }, 50);
    
    // Auto-hide after delay (except for processing states)
    if (status !== 'processing' && status !== 'checking') {
        setTimeout(() => {
            overlay.classList.remove('show');
        }, 3000);
    }
}

function hideEnrollmentResult() {
    const overlay = document.getElementById('enrollment-result-overlay');
    overlay.classList.remove('show');
}

function resetPunchButton() {
    const punchBtn = document.getElementById('punch-btn');
    
    punchBtn.disabled = false;
    punchBtn.innerHTML = 'Punch';
}

async function handleManualAttendance(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const resultDiv = document.getElementById('manual-attendance-result');
    
    resultDiv.innerHTML = '<p>Recording attendance... <span class="loading"></span></p>';
    
    try {
        const response = await fetch('/api/punch', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            resultDiv.innerHTML = `
                <div class="result-message success">
                    <h4>Manual Attendance Recorded</h4>
                    <p><strong>ID:</strong> ${result.ident}</p>
                    <p><strong>Time:</strong> ${formatTaipeiDateTime(result.punch_time)}</p>
                </div>
            `;
            form.reset();
            
            setTimeout(() => {
                resultDiv.innerHTML = '';
            }, 5000);
        } else {
            const error = await response.text();
            resultDiv.innerHTML = `<div class="result-message error">Error: ${error}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="result-message error">Error: ${error.message}</div>`;
    }
}
