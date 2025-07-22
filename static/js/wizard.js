/**
 * Enhanced Vessel Wizard with Offline Support
 * Ported from stevedores-dashboard-2.0 with offline-first architecture
 */

let currentStep = 1;
let extractedData = {};
let wizardData = {};

// Initialize wizard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeWizard();
});

function initializeWizard() {
    // Load any saved wizard data from localStorage (offline support)
    loadSavedWizardData();
    
    // Setup auto-save functionality
    setupAutoSave();
    
    // Set default operation date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('operationDate').value = today;
    
    // Setup drag and drop for document upload
    setupDragAndDrop();
    
    // Setup form submission handler
    document.getElementById('vesselWizardForm').addEventListener('submit', handleFormSubmission);
    
    console.log('Vessel wizard initialized with offline support');
}

// Wizard Navigation Functions
function nextStep(step) {
    if (validateStep(step)) {
        saveStepData(step);
        hideStep(step);
        showStep(step + 1);
        updateStepIndicators(step, step + 1);
        currentStep = step + 1;
        
        if (step === 3) {
            generateReviewSummary();
        }
    }
}

function prevStep(step) {
    saveStepData(step);
    hideStep(step);
    showStep(step - 1);
    updateStepIndicators(step, step - 1);
    currentStep = step - 1;
}

function hideStep(step) {
    document.getElementById(`step${step}`).classList.add('hidden');
}

function showStep(step) {
    document.getElementById(`step${step}`).classList.remove('hidden');
}

function updateStepIndicators(fromStep, toStep) {
    // Update from step
    const fromIndicator = document.getElementById(`step${fromStep}-indicator`);
    fromIndicator.classList.remove('step-active');
    if (toStep > fromStep) {
        fromIndicator.classList.add('step-completed');
    } else {
        fromIndicator.classList.remove('step-completed');
    }
    
    // Update to step
    const toIndicator = document.getElementById(`step${toStep}-indicator`);
    toIndicator.classList.add('step-active');
    toIndicator.classList.remove('step-completed');
}

// Step Validation
function validateStep(step) {
    clearValidationErrors();
    
    if (step === 1) {
        return validateStep1();
    } else if (step === 2) {
        return validateStep2();
    } else if (step === 3) {
        return validateStep3();
    }
    
    return true;
}

function validateStep1() {
    const vesselName = getValue('vesselName');
    const vesselType = getValue('vesselType');
    const port = getValue('port');
    const operationDate = getValue('operationDate');
    
    if (!vesselName.trim()) {
        showValidationError('vesselName', 'Vessel name is required');
        return false;
    }
    
    if (!vesselType) {
        showValidationError('vesselType', 'Vessel type is required');
        return false;
    }
    
    if (!port) {
        showValidationError('port', 'Port of call is required');
        return false;
    }
    
    if (!operationDate) {
        showValidationError('operationDate', 'Operation date is required');
        return false;
    }
    
    // Validate date is not too far in the past
    const selectedDate = new Date(operationDate);
    const today = new Date();
    const daysDiff = (today - selectedDate) / (1000 * 60 * 60 * 24);
    
    if (daysDiff > 30) {
        if (!confirm('The selected date is more than 30 days ago. Are you sure you want to continue?')) {
            return false;
        }
    }
    
    return true;
}

function validateStep2() {
    // Step 2 validation - mostly optional fields
    const totalAutomobiles = getValue('totalAutomobiles');
    
    if (totalAutomobiles && parseInt(totalAutomobiles) < 0) {
        showValidationError('totalAutomobiles', 'Total automobiles cannot be negative');
        return false;
    }
    
    return true;
}

function validateStep3() {
    // Step 3 validation - operational parameters
    const shiftStart = getValue('shiftStart');
    const shiftEnd = getValue('shiftEnd');
    
    if (shiftStart && shiftEnd) {
        if (shiftStart >= shiftEnd) {
            showValidationError('shiftEnd', 'Shift end time must be after start time');
            return false;
        }
    }
    
    return true;
}

function showValidationError(fieldId, message) {
    const field = document.getElementById(fieldId);
    if (field) {
        field.classList.add('validation-error');
        
        // Create or update error message
        let errorEl = document.getElementById(`${fieldId}-error`);
        if (!errorEl) {
            errorEl = document.createElement('div');
            errorEl.id = `${fieldId}-error`;
            errorEl.className = 'text-red-600 text-sm mt-1';
            field.parentNode.appendChild(errorEl);
        }
        errorEl.textContent = message;
    }
    
    // Show general alert
    showAlert(message, 'error');
}

function clearValidationErrors() {
    // Remove validation error classes
    document.querySelectorAll('.validation-error').forEach(el => {
        el.classList.remove('validation-error');
    });
    
    // Remove error messages
    document.querySelectorAll('[id$="-error"]').forEach(el => {
        el.remove();
    });
}

// Auto-save functionality for offline support
function setupAutoSave() {
    const formInputs = document.querySelectorAll('#vesselWizardForm input, #vesselWizardForm select');
    
    formInputs.forEach(input => {
        input.addEventListener('change', () => {
            saveStepData(currentStep);
        });
    });
}

function saveStepData(step) {
    const stepData = {};
    const stepElement = document.getElementById(`step${step}`);
    
    if (stepElement) {
        const inputs = stepElement.querySelectorAll('input, select');
        inputs.forEach(input => {
            stepData[input.name || input.id] = input.value;
        });
        
        wizardData[`step_${step}`] = stepData;
        wizardData.currentStep = step;
        wizardData.lastSaved = new Date().toISOString();
        
        // Save to localStorage for offline persistence
        localStorage.setItem('vesselWizardData', JSON.stringify(wizardData));
        
        // Also save to server if online
        if (navigator.onLine) {
            saveToServer(step, stepData);
        }
    }
}

function saveToServer(step, stepData) {
    fetch('/wizard/api/save-step', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            step: step,
            data: stepData
        })
    }).catch(error => {
        console.log('Server save failed (offline):', error);
    });
}

function loadSavedWizardData() {
    // Load from localStorage first (offline support)
    const savedData = localStorage.getItem('vesselWizardData');
    if (savedData) {
        try {
            wizardData = JSON.parse(savedData);
            populateFormData(wizardData);
        } catch (e) {
            console.error('Error loading saved wizard data:', e);
        }
    }
    
    // Also try to load from server if online
    if (navigator.onLine) {
        fetch('/wizard/api/load-saved')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.data) {
                    wizardData = { ...wizardData, ...data.data };
                    populateFormData(wizardData);
                }
            })
            .catch(error => {
                console.log('Server load failed (offline):', error);
            });
    }
}

function populateFormData(data) {
    // Populate form fields from saved data
    Object.keys(data).forEach(stepKey => {
        if (stepKey.startsWith('step_')) {
            const stepData = data[stepKey];
            Object.keys(stepData).forEach(fieldName => {
                const field = document.getElementById(fieldName);
                if (field) {
                    field.value = stepData[fieldName];
                }
            });
        }
    });
}

// Document Upload Functions
function setupDragAndDrop() {
    const uploadZone = document.querySelector('.upload-zone');
    
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            processDocumentUpload(files[0]);
        }
    });
}

function handleDocumentUpload(event) {
    const file = event.target.files[0];
    if (file) {
        processDocumentUpload(file);
    }
}

function processDocumentUpload(file) {
    // Show loading state
    document.getElementById('uploadStatus').classList.remove('hidden');
    document.getElementById('uploadSuccess').classList.add('hidden');
    
    const formData = new FormData();
    formData.append('document', file);
    
    fetch('/wizard/api/document-upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('uploadStatus').classList.add('hidden');
        
        if (data.success) {
            // Populate form with extracted data
            extractedData = data.extracted_data;
            populateFormFromExtractedData(extractedData);
            document.getElementById('uploadSuccess').classList.remove('hidden');
            
            // Save extracted data info
            wizardData.documentSource = data.filename;
            saveStepData(currentStep);
            
        } else {
            showAlert('Document processing failed: ' + data.error, 'error');
        }
    })
    .catch(error => {
        document.getElementById('uploadStatus').classList.add('hidden');
        console.error('Document upload error:', error);
        
        if (navigator.onLine) {
            showAlert('Document upload failed. Please try again.', 'error');
        } else {
            showAlert('Document upload requires internet connection. Form data will be saved offline.', 'warning');
        }
    });
}

function populateFormFromExtractedData(data) {
    Object.keys(data).forEach(field => {
        const element = document.getElementById(field);
        if (element && data[field]) {
            element.value = data[field];
            // Trigger change event for auto-save
            element.dispatchEvent(new Event('change'));
        }
    });
    
    showAlert('Form fields populated from document!', 'success');
}

// Review Summary Generation
function generateReviewSummary() {
    const summary = document.getElementById('reviewSummary');
    
    const vesselName = getValue('vesselName');
    const vesselType = getValue('vesselType');
    const port = getValue('port');
    const operationDate = getValue('operationDate');
    const totalAutomobiles = getValue('totalAutomobiles') || '0';
    const heavyEquipment = getValue('heavyEquipment') || '0';
    const shiftStart = getValue('shiftStart');
    const shiftEnd = getValue('shiftEnd');
    const driversAssigned = getValue('driversAssigned') || '0';
    const ticoVehicles = getValue('ticoVehicles') || '0';
    
    summary.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-3">Vessel Information</h3>
                <div class="space-y-2 text-sm">
                    <div><strong>Name:</strong> ${vesselName}</div>
                    <div><strong>Type:</strong> ${vesselType}</div>
                    <div><strong>Port:</strong> ${port}</div>
                    <div><strong>Date:</strong> ${formatDate(operationDate)}</div>
                </div>
            </div>
            <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-3">Cargo Configuration</h3>
                <div class="space-y-2 text-sm">
                    <div><strong>Automobiles:</strong> ${totalAutomobiles}</div>
                    <div><strong>Heavy Equipment:</strong> ${heavyEquipment}</div>
                    <div><strong>Cargo Type:</strong> ${getValue('cargoType') || 'Automobile'}</div>
                </div>
            </div>
            <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-3">Operations</h3>
                <div class="space-y-2 text-sm">
                    <div><strong>Shift:</strong> ${shiftStart || 'Not set'} - ${shiftEnd || 'Not set'}</div>
                    <div><strong>Drivers:</strong> ${driversAssigned}</div>
                    <div><strong>TICO Vehicles:</strong> ${ticoVehicles}</div>
                </div>
            </div>
        </div>
    `;
}

// Form Submission
function handleFormSubmission(event) {
    event.preventDefault();
    
    // Show submission modal
    document.getElementById('submissionModal').classList.remove('hidden');
    
    // Gather all form data
    const formData = gatherAllFormData();
    
    // Submit to server
    fetch('/wizard/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSubmissionSuccess(data);
        } else {
            throw new Error(data.error || 'Submission failed');
        }
    })
    .catch(error => {
        console.error('Submission error:', error);
        
        if (navigator.onLine) {
            showAlert('Submission failed: ' + error.message, 'error');
        } else {
            // Save for later sync when online
            saveForOfflineSubmission(formData);
            showAlert('Saved offline. Will submit when connection returns.', 'info');
        }
        
        document.getElementById('submissionModal').classList.add('hidden');
    });
}

function gatherAllFormData() {
    const formData = {};
    const inputs = document.querySelectorAll('#vesselWizardForm input, #vesselWizardForm select');
    
    inputs.forEach(input => {
        if (input.name || input.id) {
            formData[input.name || input.id] = input.value;
        }
    });
    
    // Add metadata
    formData.documentSource = wizardData.documentSource;
    formData.timestamp = new Date().toISOString();
    
    return formData;
}

function saveForOfflineSubmission(formData) {
    const offlineSubmissions = JSON.parse(localStorage.getItem('offlineVesselSubmissions') || '[]');
    offlineSubmissions.push({
        data: formData,
        timestamp: new Date().toISOString()
    });
    localStorage.setItem('offlineVesselSubmissions', JSON.stringify(offlineSubmissions));
}

function showSubmissionSuccess(data) {
    document.getElementById('submissionLoading').classList.add('hidden');
    document.getElementById('submissionSuccess').classList.remove('hidden');
    
    // Clear saved wizard data
    localStorage.removeItem('vesselWizardData');
    
    // Redirect after a delay
    setTimeout(() => {
        if (data.redirect_url) {
            window.location.href = data.redirect_url;
        } else {
            window.location.href = '/dashboard';
        }
    }, 2000);
}

function closeModal() {
    document.getElementById('submissionModal').classList.add('hidden');
    window.location.href = '/dashboard';
}

// Utility Functions
function getValue(elementId) {
    const element = document.getElementById(elementId);
    return element ? element.value : '';
}

function formatDate(dateString) {
    if (!dateString) return 'Not set';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function showAlert(message, type = 'info') {
    // Simple alert system (could be enhanced with proper toast notifications)
    const alertClass = type === 'error' ? 'alert-error' : type === 'success' ? 'alert-success' : 'alert-info';
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Could implement proper toast notifications here
}

// Sync offline submissions when connection returns
window.addEventListener('online', () => {
    const offlineSubmissions = JSON.parse(localStorage.getItem('offlineVesselSubmissions') || '[]');
    
    if (offlineSubmissions.length > 0) {
        console.log('Syncing offline vessel submissions...');
        // Implementation for syncing offline submissions would go here
    }
});

console.log('Enhanced wizard with offline support loaded');