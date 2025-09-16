/**
 * Enhanced Vessel Wizard with Offline Support
 * Ported from stevedores-dashboard-2.0 with offline-first architecture
 */

let currentStep = 1;
let extractedData = {};
let wizardData = {};
let documentProcessor = null;

// Initialize wizard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeWizard();
});

function initializeWizard() {
    // Load document processor for offline auto-fill
    loadDocumentProcessor();
    
    // Load any saved wizard data from localStorage (offline support)
    loadSavedWizardData();
    
    // Check for server-side auto-fill data
    checkAutoFillData();
    
    // Setup auto-save functionality
    setupAutoSave();
    
    // Set default operation dates to today
    const today = new Date().toISOString().split('T')[0];
    const startDateField = document.getElementById('operationStartDate');
    const endDateField = document.getElementById('operationEndDate');
    if (startDateField) startDateField.value = today;
    if (endDateField) endDateField.value = today;
    
    // Setup drag and drop for document upload
    setupDragAndDrop();
    
    // Setup document upload handlers
    setupDocumentUpload();
    
    // Setup form submission handler
    document.getElementById('vesselWizardForm').addEventListener('submit', handleFormSubmission);
    
    console.log('Vessel wizard initialized with offline document processing support');
}

// Wizard Navigation Functions
function nextStep(step) {
    if (validateStep(step)) {
        saveStepData(step);
        hideStep(step);
        showStep(step + 1);
        updateStepIndicators(step, step + 1);
        currentStep = step + 1;
        
        if (step === 4) {
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
    } else if (step === 4) {
        return validateStep4();
    } else if (step === 5) {
        return validateStep5();
    }
    
    return true;
}

function validateStep1() {
    const vesselName = getValue('vesselName');
    const shippingLine = getValue('shippingLine');
    const vesselType = getValue('vesselType');
    const operationStartDate = getValue('operationStartDate');
    const operationEndDate = getValue('operationEndDate');
    const operationType = getValue('operationType');
    const berthAssignment = getValue('berthAssignment');
    const operationsManager = getValue('operationsManager');
    
    if (!vesselName.trim()) {
        showValidationError('vesselName', 'Vessel name is required');
        return false;
    }
    
    if (!shippingLine) {
        showValidationError('shippingLine', 'Shipping line is required');
        return false;
    }
    
    if (!vesselType) {
        showValidationError('vesselType', 'Vessel type is required');
        return false;
    }
    
    if (!operationStartDate) {
        showValidationError('operationStartDate', 'Operation start date is required');
        return false;
    }
    
    if (!operationEndDate) {
        showValidationError('operationEndDate', 'Operation end date is required');
        return false;
    }
    
    if (!operationType) {
        showValidationError('operationType', 'Operation type is required');
        return false;
    }
    
    if (!berthAssignment) {
        showValidationError('berthAssignment', 'Berth assignment is required');
        return false;
    }
    
    if (!operationsManager) {
        showValidationError('operationsManager', 'Operations manager is required');
        return false;
    }
    
    // Validate dates
    const startDate = new Date(operationStartDate);
    const endDate = new Date(operationEndDate);
    
    if (endDate < startDate) {
        showValidationError('operationEndDate', 'End date cannot be before start date');
        return false;
    }
    
    return true;
}

function validateStep2() {
    // Step 2 validation - team assignments
    const autoMembers = parseInt(getValue('autoOperationsMembers')) || 0;
    const highHeavyMembers = parseInt(getValue('highHeavyMembers')) || 0;
    
    // Validate that at least one team member is assigned for auto operations
    if (autoMembers === 0) {
        showValidationError('autoOperationsMembers', 'At least one auto operations team member is required');
        return false;
    }
    
    // Validate team member selections
    for (let i = 1; i <= autoMembers; i++) {
        const memberValue = getValue(`autoOperationsMember${i}`);
        const customValue = getValue(`autoOperationsMemberCustom${i}`);
        
        if (!memberValue || (memberValue === 'Custom' && !customValue.trim())) {
            showValidationError(`autoOperationsMember${i}`, `Auto operations member ${i} is required`);
            return false;
        }
    }
    
    // Validate high heavy team if K-line
    const shippingLine = getValue('shippingLine');
    if (shippingLine === 'K-line' && highHeavyMembers > 0) {
        for (let i = 1; i <= highHeavyMembers; i++) {
            const memberValue = getValue(`highHeavyMember${i}`);
            const customValue = getValue(`highHeavyMemberCustom${i}`);
            
            if (!memberValue || (memberValue === 'Custom' && !customValue.trim())) {
                showValidationError(`highHeavyMember${i}`, `High heavy team member ${i} is required`);
                return false;
            }
        }
    }
    
    return true;
}

function validateStep3() {
    // Step 3 validation - cargo configuration
    const operationType = getValue('operationType');
    
    if (operationType === 'Discharge Only' || operationType === 'Discharge + Loadback') {
        const dischargeTotalAutos = getValue('dischargeTotalAutos');
        if (!dischargeTotalAutos || parseInt(dischargeTotalAutos) <= 0) {
            showValidationError('dischargeTotalAutos', 'Total autos for discharge is required');
            return false;
        }
    }
    
    if (operationType === 'Loading Only') {
        const loadingTotalAutos = getValue('loadingTotalAutos');
        if (!loadingTotalAutos || parseInt(loadingTotalAutos) <= 0) {
            showValidationError('loadingTotalAutos', 'Total autos for loading is required');
            return false;
        }
    }
    
    if (operationType === 'Discharge + Loadback') {
        const loadbackTotalAutos = getValue('loadbackTotalAutos');
        if (!loadbackTotalAutos || parseInt(loadbackTotalAutos) <= 0) {
            showValidationError('loadbackTotalAutos', 'Total autos for loadback is required');
            return false;
        }
    }
    
    return true;
}

function validateStep4() {
    // Step 4 validation - operational parameters
    const totalDrivers = getValue('totalDrivers');
    const shiftStartTime = getValue('shiftStartTime');
    const shiftEndTime = getValue('shiftEndTime');
    const numberOfVans = parseInt(getValue('numberOfVans')) || 0;
    const numberOfWagons = parseInt(getValue('numberOfWagons')) || 0;
    
    if (!totalDrivers || parseInt(totalDrivers) <= 0) {
        showValidationError('totalDrivers', 'Total drivers is required');
        return false;
    }
    
    if (shiftStartTime && shiftEndTime) {
        if (shiftStartTime >= shiftEndTime) {
            showValidationError('shiftEndTime', 'Shift end time must be after start time');
            return false;
        }
    }
    
    // Validate van details if vans are specified
    for (let i = 1; i <= numberOfVans; i++) {
        const vanId = getValue(`van${i}Id`);
        const vanDriver = getValue(`van${i}Driver`);
        
        if (!vanId.trim()) {
            showValidationError(`van${i}Id`, `Van ${i} ID is required`);
            return false;
        }
        
        if (!vanDriver.trim()) {
            showValidationError(`van${i}Driver`, `Van ${i} driver name is required`);
            return false;
        }
    }
    
    // Validate wagon details if wagons are specified
    for (let i = 1; i <= numberOfWagons; i++) {
        const wagonId = getValue(`wagon${i}Id`);
        const wagonDriver = getValue(`wagon${i}Driver`);
        
        if (!wagonId.trim()) {
            showValidationError(`wagon${i}Id`, `Wagon ${i} ID is required`);
            return false;
        }
        
        if (!wagonDriver.trim()) {
            showValidationError(`wagon${i}Driver`, `Wagon ${i} driver name is required`);
            return false;
        }
    }
    
    return true;
}

function validateStep5() {
    // Step 5 validation - review/summary 
    // No additional validation needed as all previous steps are already validated
    // This step is just for review and confirmation
    return true;
}

function validateAllSteps() {
    // Validate all steps before final submission
    clearValidationErrors();
    
    let allValid = true;
    const stepNames = ['Step 1 (Vessel Info)', 'Step 2 (Team Assignment)', 'Step 3 (Cargo Config)', 'Step 4 (Operations)'];
    
    for (let step = 1; step <= 4; step++) {
        const stepValid = validateStep(step);
        if (!stepValid) {
            console.log(`Validation failed on ${stepNames[step-1]}`);
            allValid = false;
        }
    }
    
    return allValid;
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
        fetch('/wizard/api/load-saved', { redirect: 'follow' })
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
    
    // Get vessel information
    const vesselName = getValue('vesselName');
    const shippingLine = getValue('shippingLine'); 
    const vesselType = getValue('vesselType');
    const port = getValue('port');
    const operationStartDate = getValue('operationStartDate');
    const operationEndDate = getValue('operationEndDate');
    const operationType = getValue('operationType');
    const berthAssignment = getValue('berthAssignment');
    const operationsManager = getValue('operationsManager');
    
    // Get cargo information based on operation type
    let totalAutos = 0;
    let heavyEquipment = 0;
    
    if (operationType === 'Discharge Only' || operationType === 'Discharge + Loadback') {
        totalAutos += parseInt(getValue('dischargeTotalAutos')) || 0;
        heavyEquipment += parseInt(getValue('dischargeHeavy')) || 0;
    }
    if (operationType === 'Loading Only') {
        totalAutos += parseInt(getValue('loadingTotalAutos')) || 0;
        heavyEquipment += parseInt(getValue('loadingHeavy')) || 0;
    }
    if (operationType === 'Discharge + Loadback') {
        totalAutos += parseInt(getValue('loadbackTotalAutos')) || 0;
        heavyEquipment += parseInt(getValue('loadbackHeavy')) || 0;
    }
    
    // Get team information
    const autoOperationsMembers = getValue('autoOperationsMembers') || '0';
    const highHeavyMembers = getValue('highHeavyMembers') || '0';
    
    // Get operational parameters
    const totalDrivers = getValue('totalDrivers');
    const shiftStartTime = getValue('shiftStartTime');
    const shiftEndTime = getValue('shiftEndTime');
    const shipStartTime = getValue('shipStartTime');
    const shipCompleteTime = getValue('shipCompleteTime');
    const numberOfBreaks = getValue('numberOfBreaks') || '0';
    
    // Calculate TICO vehicles
    const numberOfVans = parseInt(getValue('numberOfVans')) || 0;
    const numberOfWagons = parseInt(getValue('numberOfWagons')) || 0;
    const numberOfLowDecks = parseInt(getValue('numberOfLowDecks')) || 0;
    const totalTicoVehicles = numberOfVans + numberOfWagons;
    
    summary.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-3">
                    <i class="fas fa-ship text-blue-600 mr-2"></i>Vessel Information
                </h3>
                <div class="space-y-2 text-sm">
                    <div><strong>Name:</strong> ${vesselName || 'Not specified'}</div>
                    <div><strong>Shipping Line:</strong> ${shippingLine || 'Not specified'}</div>
                    <div><strong>Type:</strong> ${vesselType || 'Not specified'}</div>
                    <div><strong>Port:</strong> ${port || 'Not specified'}</div>
                    <div><strong>Operation:</strong> ${operationType || 'Not specified'}</div>
                    <div><strong>Berth:</strong> ${berthAssignment || 'Not specified'}</div>
                    <div><strong>Manager:</strong> ${operationsManager || 'Not specified'}</div>
                    <div><strong>Start Date:</strong> ${formatDate(operationStartDate)}</div>
                    <div><strong>End Date:</strong> ${formatDate(operationEndDate)}</div>
                </div>
            </div>
            <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-3">
                    <i class="fas fa-boxes text-green-600 mr-2"></i>Cargo Configuration
                </h3>
                <div class="space-y-2 text-sm">
                    <div><strong>Total Automobiles:</strong> ${totalAutos}</div>
                    <div><strong>Heavy Equipment:</strong> ${heavyEquipment}</div>
                    <div><strong>Operation Type:</strong> ${operationType || 'Not specified'}</div>
                </div>
                
                <h4 class="text-md font-semibold text-gray-800 mt-4 mb-2">
                    <i class="fas fa-users text-orange-600 mr-2"></i>Team Assignment
                </h4>
                <div class="space-y-2 text-sm">
                    <div><strong>Auto Operations:</strong> ${autoOperationsMembers} members</div>
                    ${shippingLine === 'K-line' ? `<div><strong>High Heavy Team:</strong> ${highHeavyMembers} members</div>` : ''}
                </div>
            </div>
            <div>
                <h3 class="text-lg font-semibold text-gray-900 mb-3">
                    <i class="fas fa-cog text-purple-600 mr-2"></i>Operations
                </h3>
                <div class="space-y-2 text-sm">
                    <div><strong>Total Drivers:</strong> ${totalDrivers || 'Not specified'}</div>
                    <div><strong>Shift:</strong> ${shiftStartTime || 'Not set'} - ${shiftEndTime || 'Not set'}</div>
                    <div><strong>Ship Operation:</strong> ${shipStartTime || 'Not set'} - ${shipCompleteTime || 'Not set'}</div>
                    <div><strong>Breaks:</strong> ${numberOfBreaks} (${parseInt(numberOfBreaks) * 60} minutes)</div>
                </div>
                
                <h4 class="text-md font-semibold text-gray-800 mt-4 mb-2">
                    <i class="fas fa-van-shuttle text-green-600 mr-2"></i>TICO Transportation
                </h4>
                <div class="space-y-2 text-sm">
                    <div><strong>Vans:</strong> ${numberOfVans} (${numberOfVans * 7} driver capacity)</div>
                    <div><strong>Wagons:</strong> ${numberOfWagons} (${numberOfWagons * 5} driver capacity)</div>
                    <div><strong>Low Decks:</strong> ${numberOfLowDecks}</div>
                    <div><strong>Total TICO Vehicles:</strong> ${totalTicoVehicles}</div>
                    <div><strong>Total Transport Capacity:</strong> ${(numberOfVans * 7) + (numberOfWagons * 5)} drivers</div>
                </div>
            </div>
        </div>
    `;
}

// Form Submission with Sync Manager Integration
function handleFormSubmission(event) {
    event.preventDefault();
    
    // Validate all steps before submission
    const allStepsValid = validateAllSteps();
    if (!allStepsValid) {
        showAlert('Please complete all required fields before submitting.', 'error');
        return;
    }
    
    // Show submission modal
    document.getElementById('submissionModal').classList.remove('hidden');
    
    // Gather all form data
    const formData = gatherAllFormData();
    
    // Debug: Log form data being submitted
    console.log('📊 Form Data Being Submitted:', formData);
    console.log('📋 Total fields:', Object.keys(formData).length);
    console.log('🚢 Vessel Name:', formData.vesselName);
    console.log('📦 Discharge Autos:', formData.dischargeTotalAutos);
    console.log('👷 Total Drivers:', formData.totalDrivers);
    console.log('🚐 Number of Vans:', formData.numberOfVans);
    
    // Try online submission first, fallback to sync manager
    if (navigator.onLine) {
        fetch('/wizard/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        })
        .then(response => {
            console.log('📡 Response Status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('✅ Server Response:', data);
            if (data.success) {
                console.log('🎉 Vessel created successfully! ID:', data.vessel_id);
                showSubmissionSuccess(data);
            } else {
                console.error('❌ Server returned error:', data.error);
                throw new Error(data.error || 'Submission failed');
            }
        })
        .catch(error => {
            console.error('Online submission failed, using sync manager:', error);
            handleOfflineSubmission(formData);
        });
    } else {
        // Direct offline submission
        handleOfflineSubmission(formData);
    }
}

function handleOfflineSubmission(formData) {
    // Use sync manager if available
    if (window.VesselSyncHelper) {
        const syncId = window.VesselSyncHelper.syncVesselCreation(formData);
        
        if (syncId) {
            // Show offline success
            document.getElementById('submissionModal').classList.add('hidden');
            showAlert('Vessel saved offline. Will sync when online.', 'success');
            
            // Clear saved wizard data
            localStorage.removeItem('vesselWizardData');
            
            // Redirect to dashboard
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);
            
            return;
        }
    }
    
    // Fallback to old offline method
    saveForOfflineSubmission(formData);
    showAlert('Saved offline. Will submit when connection returns.', 'info');
    document.getElementById('submissionModal').classList.add('hidden');
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
    // Enhanced alert system with visible notifications
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Create alert element
    const alertId = 'wizard-alert-' + Date.now();
    const alertDiv = document.createElement('div');
    alertDiv.id = alertId;
    alertDiv.className = `fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg max-w-md ${getAlertClasses(type)}`;
    alertDiv.innerHTML = `
        <div class="flex items-center">
            <div class="flex-shrink-0">
                ${getAlertIcon(type)}
            </div>
            <div class="ml-3">
                <p class="text-sm font-medium">${message}</p>
            </div>
            <div class="ml-auto pl-3">
                <button onclick="document.getElementById('${alertId}').remove()" class="text-sm hover:opacity-70">×</button>
            </div>
        </div>
    `;
    
    // Add to page
    document.body.appendChild(alertDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        const element = document.getElementById(alertId);
        if (element) element.remove();
    }, 5000);
}

function getAlertClasses(type) {
    switch(type) {
        case 'error': return 'bg-red-100 border border-red-300 text-red-800';
        case 'success': return 'bg-green-100 border border-green-300 text-green-800';
        case 'warning': return 'bg-yellow-100 border border-yellow-300 text-yellow-800';
        default: return 'bg-blue-100 border border-blue-300 text-blue-800';
    }
}

function getAlertIcon(type) {
    switch(type) {
        case 'error': return '<i class="fas fa-exclamation-circle text-red-500"></i>';
        case 'success': return '<i class="fas fa-check-circle text-green-500"></i>';
        case 'warning': return '<i class="fas fa-exclamation-triangle text-yellow-500"></i>';
        default: return '<i class="fas fa-info-circle text-blue-500"></i>';
    }
}

// Sync offline submissions when connection returns
window.addEventListener('online', () => {
    const offlineSubmissions = JSON.parse(localStorage.getItem('offlineVesselSubmissions') || '[]');
    
    if (offlineSubmissions.length > 0) {
        console.log('Syncing offline vessel submissions...');
        // Implementation for syncing offline submissions would go here
    }
});

// Document Processing Functions
async function loadDocumentProcessor() {
    try {
        // Load offline document processor
        if (!window.documentProcessor) {
            const script = document.createElement('script');
            script.src = '/document/client-processor.js';
            document.head.appendChild(script);
            
            // Wait for script to load
            await new Promise((resolve) => {
                script.onload = resolve;
            });
        }
        documentProcessor = window.documentProcessor;
        console.log('Document processor loaded for offline auto-fill');
    } catch (error) {
        console.error('Failed to load document processor:', error);
    }
}

async function checkAutoFillData() {
    try {
        const response = await fetch('/document/get-auto-fill', { redirect: 'follow' });
        const data = await response.json();
        
        if (data.has_data) {
            displayAutoFillOption(data);
        }
    } catch (error) {
        console.log('No server-side auto-fill data available');
    }
}

function displayAutoFillOption(autoFillData) {
    const autoFillBanner = document.createElement('div');
    autoFillBanner.className = 'auto-fill-banner';
    autoFillBanner.innerHTML = `
        <div class="auto-fill-content">
            <div class="auto-fill-icon">📄</div>
            <div class="auto-fill-text">
                <strong>Auto-fill Available</strong>
                <p>Found data from ${autoFillData.document_source} (${Math.round(autoFillData.confidence_score * 100)}% confidence)</p>
            </div>
            <div class="auto-fill-actions">
                <button onclick="applyAutoFill()" class="btn-auto-fill">Apply Auto-fill</button>
                <button onclick="dismissAutoFill()" class="btn-dismiss">Dismiss</button>
            </div>
        </div>
    `;
    
    const wizardContainer = document.querySelector('.wizard-container');
    wizardContainer.insertBefore(autoFillBanner, wizardContainer.firstChild);
    
    // Store auto-fill data
    window.availableAutoFill = autoFillData;
}

async function applyAutoFill() {
    if (!window.availableAutoFill) return;
    
    const autoFillData = window.availableAutoFill.wizard_data;
    
    // Populate Step 1
    if (autoFillData.step_1) {
        const step1Data = autoFillData.step_1;
        if (step1Data.vessel_name) document.getElementById('vesselName').value = step1Data.vessel_name;
        if (step1Data.vessel_type) document.getElementById('vesselType').value = step1Data.vessel_type;
        if (step1Data.port_of_call) document.getElementById('portOfCall').value = step1Data.port_of_call;
        if (step1Data.eta) document.getElementById('eta').value = step1Data.eta;
    }
    
    // Populate Step 2
    if (autoFillData.step_2) {
        const step2Data = autoFillData.step_2;
        if (step2Data.total_cargo_capacity) document.getElementById('totalCapacity').value = step2Data.total_cargo_capacity;
        if (step2Data.cargo_type) document.getElementById('cargoType').value = step2Data.cargo_type;
        if (step2Data.heavy_equipment_count) document.getElementById('heavyEquipment').value = step2Data.heavy_equipment_count;
    }
    
    // Populate Step 3
    if (autoFillData.step_3) {
        const step3Data = autoFillData.step_3;
        if (step3Data.current_berth) document.getElementById('berth').value = step3Data.current_berth;
        if (step3Data.shift_start) document.getElementById('shiftStart').value = step3Data.shift_start;
        if (step3Data.shift_end) document.getElementById('shiftEnd').value = step3Data.shift_end;
        if (step3Data.drivers_assigned) document.getElementById('driversAssigned').value = step3Data.drivers_assigned;
        if (step3Data.tico_vehicles_needed) document.getElementById('ticoVehicles').value = step3Data.tico_vehicles_needed;
    }
    
    // Save auto-fill source
    wizardData.documentSource = window.availableAutoFill.document_source;
    wizardData.autoFilled = true;
    
    // Remove banner
    const banner = document.querySelector('.auto-fill-banner');
    if (banner) banner.remove();
    
    // Clear server-side auto-fill data
    await fetch('/document/clear-auto-fill', { method: 'POST', redirect: 'follow' });
    
    showAlert('Form auto-filled successfully!', 'success');
}

function dismissAutoFill() {
    const banner = document.querySelector('.auto-fill-banner');
    if (banner) banner.remove();
    
    // Clear server-side auto-fill data
    fetch('/document/clear-auto-fill', { method: 'POST', redirect: 'follow' });
}

function setupDocumentUpload() {
    const fileInput = document.getElementById('documentUpload');
    const textArea = document.getElementById('documentText');
    const processTextBtn = document.getElementById('processTextBtn');
    
    if (fileInput) {
        fileInput.addEventListener('change', handleDocumentUpload);
    }
    
    if (processTextBtn) {
        processTextBtn.addEventListener('click', processTextContent);
    }
}

async function handleDocumentUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // Show loading
    setUploadStatus('processing', 'Processing document...');
    
    try {
        // Try server-side processing first
        const formData = new FormData();
        formData.append('document', file);
        
        const response = await fetch('/document/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            setUploadStatus('success', `Document processed successfully! Confidence: ${Math.round(result.extracted_data.confidence_score * 100)}%`);
            applyExtractedData(result.wizard_data);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.log('Server processing failed, trying offline processing:', error);
        
        // Fall back to client-side processing
        if (documentProcessor && file.type === 'text/plain') {
            const text = await file.text();
            const result = documentProcessor.processText(text, file.name);
            
            if (result.success) {
                setUploadStatus('success', `Document processed offline! Confidence: ${Math.round(result.confidence_score * 100)}%`);
                applyExtractedData(result.wizard_data);
            } else {
                setUploadStatus('error', 'Document processing failed: ' + result.error);
            }
        } else {
            setUploadStatus('error', 'Document processing failed. Please try pasting text content instead.');
        }
    }
}

async function processTextContent() {
    const textArea = document.getElementById('documentText');
    const text = textArea.value.trim();
    
    if (!text) {
        showAlert('Please enter document text to process', 'error');
        return;
    }
    
    setUploadStatus('processing', 'Processing text content...');
    
    try {
        // Try server-side processing first
        const response = await fetch('/document/process-text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, filename: 'pasted_content.txt' })
        });
        
        const result = await response.json();
        
        if (result.success) {
            setUploadStatus('success', `Text processed successfully! Confidence: ${Math.round(result.extracted_data.confidence_score * 100)}%`);
            applyExtractedData(result.wizard_data);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.log('Server processing failed, trying offline processing:', error);
        
        // Fall back to client-side processing
        if (documentProcessor) {
            const result = documentProcessor.processText(text, 'pasted_content.txt');
            
            if (result.success) {
                setUploadStatus('success', `Text processed offline! Confidence: ${Math.round(result.confidence_score * 100)}%`);
                applyExtractedData(result.wizard_data);
            } else {
                setUploadStatus('error', 'Text processing failed: ' + result.error);
            }
        } else {
            setUploadStatus('error', 'Text processing unavailable');
        }
    }
}

function applyExtractedData(wizardData) {
    // Apply extracted data to form fields
    Object.keys(wizardData).forEach(stepKey => {
        const stepData = wizardData[stepKey];
        Object.keys(stepData).forEach(fieldKey => {
            const element = document.getElementById(fieldKey) || 
                          document.querySelector(`[name="${fieldKey}"]`);
            if (element && stepData[fieldKey]) {
                element.value = stepData[fieldKey];
                element.classList.add('auto-filled');
            }
        });
    });
    
    // Mark as auto-filled
    wizardData.autoFilled = true;
    wizardData.documentSource = wizardData.step_4?.document_source || 'processed_document';
    
    // Save to wizard data
    saveStepData(currentStep);
    
    showAlert('Form fields populated from document!', 'success');
}

function setUploadStatus(type, message) {
    const statusElement = document.getElementById('uploadStatus');
    if (!statusElement) return;
    
    statusElement.className = `upload-status ${type}`;
    statusElement.textContent = message;
    statusElement.classList.remove('hidden');
    
    if (type === 'success' || type === 'error') {
        setTimeout(() => {
            statusElement.classList.add('hidden');
        }, 5000);
    }
}

// New Enhanced Wizard Functions for Dashboard 3.0

// Step 1: Conditional Logic Functions
function updateVesselTypeOptions() {
    const shippingLine = document.getElementById('shippingLine').value;
    const vesselType = document.getElementById('vesselType');
    const kLineOptions = document.querySelectorAll('.k-line-only');
    
    // Reset vessel type selection
    vesselType.value = '';
    
    if (shippingLine === 'K-line') {
        // Show all options for K-line
        kLineOptions.forEach(option => {
            option.style.display = 'block';
        });
    } else if (['Grimaldi', 'Glovis', 'MOL'].includes(shippingLine)) {
        // Hide Heavy Only and Auto + Heavy for other lines
        kLineOptions.forEach(option => {
            option.style.display = 'none';
        });
    }
    
    // Update Step 2 visibility based on shipping line
    updateStep2Visibility();
    
    // Update Step 3 heavy equipment visibility
    updateStep3HeavyEquipment();
}

// Update Step 2 team assignment visibility
function updateStep2Visibility() {
    const shippingLine = document.getElementById('shippingLine').value;
    const highHeavySection = document.getElementById('highHeavySection');
    
    if (shippingLine === 'K-line') {
        highHeavySection.style.display = 'block';
    } else {
        highHeavySection.style.display = 'none';
        // Reset high heavy team members when hidden
        document.getElementById('highHeavyMembers').value = '0';
        updateTeamMembers('highHeavy');
    }
}

// Update Step 3 cargo configuration based on operation type and vessel type
function updateStep3Configuration() {
    const operationType = document.getElementById('operationType').value;
    const dischargeSection = document.getElementById('dischargeSection');
    const loadbackSection = document.getElementById('loadbackSection');
    const loadingSection = document.getElementById('loadingSection');
    
    // Hide all sections first
    dischargeSection.style.display = 'none';
    loadbackSection.style.display = 'none';
    loadingSection.style.display = 'none';
    
    if (operationType === 'Discharge Only') {
        dischargeSection.style.display = 'block';
    } else if (operationType === 'Loading Only') {
        loadingSection.style.display = 'block';
    } else if (operationType === 'Discharge + Loadback') {
        dischargeSection.style.display = 'block';
        loadbackSection.style.display = 'block';
    }
    
    updateStep3HeavyEquipment();
}

function updateStep3HeavyEquipment() {
    const shippingLine = document.getElementById('shippingLine').value;
    const vesselType = document.getElementById('vesselType').value;
    
    const heavyContainers = [
        document.getElementById('dischargeHeavyContainer'),
        document.getElementById('loadbackHeavyContainer'),
        document.getElementById('loadingHeavyContainer')
    ];
    
    heavyContainers.forEach(container => {
        if (container) {
            if (shippingLine === 'K-line' && vesselType === 'Auto + Heavy') {
                container.style.display = 'block';
            } else {
                container.style.display = 'none';
            }
        }
    });
}

// Step 2: Team Assignment Functions
function updateTeamMembers(teamType) {
    const memberCount = parseInt(document.getElementById(`${teamType}Members`).value) || 0;
    const container = document.getElementById(`${teamType}TeamMembers`);
    
    // Clear existing members
    container.innerHTML = '';
    
    // Add member fields based on count
    for (let i = 1; i <= memberCount; i++) {
        const memberDiv = document.createElement('div');
        memberDiv.className = 'flex flex-col';
        memberDiv.innerHTML = `
            <label for="${teamType}Member${i}" class="block text-sm font-medium text-gray-700 mb-2">Member ${i}</label>
            <select id="${teamType}Member${i}" name="${teamType}Member${i}" onchange="handleMemberSelection('${teamType}', ${i})"
                    class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
                <option value="">Select Member</option>
                <option value="Colby">Colby</option>
                <option value="Spencer">Spencer</option>
                <option value="Cole">Cole</option>
                <option value="Bruce">Bruce</option>
                <option value="Custom">Custom</option>
            </select>
            <input type="text" id="${teamType}MemberCustom${i}" name="${teamType}MemberCustom${i}" 
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 mt-2 hidden"
                   placeholder="Enter custom name">
        `;
        container.appendChild(memberDiv);
    }
}

function handleMemberSelection(teamType, memberIndex) {
    const select = document.getElementById(`${teamType}Member${memberIndex}`);
    const customInput = document.getElementById(`${teamType}MemberCustom${memberIndex}`);
    
    if (select.value === 'Custom') {
        customInput.classList.remove('hidden');
        customInput.required = true;
    } else {
        customInput.classList.add('hidden');
        customInput.required = false;
        customInput.value = '';
    }
}

// Step 3: Cargo Configuration Functions
let vehicleTypeCounters = {
    discharge: 0,
    loadback: 0,
    loading: 0
};

function addVehicleType(section) {
    vehicleTypeCounters[section]++;
    const container = document.getElementById(`${section}VehicleTypes`);
    
    const vehicleDiv = document.createElement('div');
    vehicleDiv.className = 'grid grid-cols-1 md:grid-cols-3 gap-4 p-4 border border-gray-200 rounded-lg';
    vehicleDiv.id = `${section}VehicleType${vehicleTypeCounters[section]}`;
    
    vehicleDiv.innerHTML = `
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Vehicle Type</label>
            <input type="text" name="${section}VehicleType${vehicleTypeCounters[section]}" 
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                   placeholder="e.g., Sedan, SUV, Truck">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Quantity</label>
            <input type="number" name="${section}Quantity${vehicleTypeCounters[section]}" min="0"
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                   placeholder="Enter quantity">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Location</label>
            <input type="text" name="${section}Location${vehicleTypeCounters[section]}" 
                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                   placeholder="e.g., Deck 1, Zone A">
        </div>
        <div class="md:col-span-3">
            <button type="button" onclick="removeVehicleType('${section}', ${vehicleTypeCounters[section]})" 
                    class="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm">
                <i class="fas fa-trash mr-1"></i>Remove
            </button>
        </div>
    `;
    
    container.appendChild(vehicleDiv);
}

function removeVehicleType(section, index) {
    const element = document.getElementById(`${section}VehicleType${index}`);
    if (element) {
        element.remove();
    }
}

// Step 4: TICO Transportation Functions
function updateVanList() {
    const vanCount = parseInt(document.getElementById('numberOfVans').value) || 0;
    const vanDetailsSection = document.getElementById('vanDetailsSection');
    const vanDetailsList = document.getElementById('vanDetailsList');
    
    // Clear existing van details
    vanDetailsList.innerHTML = '';
    
    if (vanCount > 0) {
        vanDetailsSection.style.display = 'block';
        
        for (let i = 1; i <= vanCount; i++) {
            const vanDiv = document.createElement('div');
            vanDiv.className = 'grid grid-cols-1 md:grid-cols-2 gap-4 p-4 border border-gray-200 rounded-lg';
            vanDiv.innerHTML = `
                <div>
                    <label for="van${i}Id" class="block text-sm font-medium text-gray-700 mb-2">Van ${i} ID Number</label>
                    <input type="text" id="van${i}Id" name="van${i}Id" 
                           class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                           placeholder="Enter van ID">
                </div>
                <div>
                    <label for="van${i}Driver" class="block text-sm font-medium text-gray-700 mb-2">Van ${i} Driver Name</label>
                    <input type="text" id="van${i}Driver" name="van${i}Driver" 
                           class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                           placeholder="Enter driver name">
                </div>
            `;
            vanDetailsList.appendChild(vanDiv);
        }
    } else {
        vanDetailsSection.style.display = 'none';
    }
}

function updateWagonList() {
    const wagonCount = parseInt(document.getElementById('numberOfWagons').value) || 0;
    const wagonDetailsSection = document.getElementById('wagonDetailsSection');
    const wagonDetailsList = document.getElementById('wagonDetailsList');
    
    // Clear existing wagon details
    wagonDetailsList.innerHTML = '';
    
    if (wagonCount > 0) {
        wagonDetailsSection.style.display = 'block';
        
        for (let i = 1; i <= wagonCount; i++) {
            const wagonDiv = document.createElement('div');
            wagonDiv.className = 'grid grid-cols-1 md:grid-cols-2 gap-4 p-4 border border-gray-200 rounded-lg';
            wagonDiv.innerHTML = `
                <div>
                    <label for="wagon${i}Id" class="block text-sm font-medium text-gray-700 mb-2">Wagon ${i} ID Number</label>
                    <input type="text" id="wagon${i}Id" name="wagon${i}Id" 
                           class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                           placeholder="Enter wagon ID">
                </div>
                <div>
                    <label for="wagon${i}Driver" class="block text-sm font-medium text-gray-700 mb-2">Wagon ${i} Driver Name</label>
                    <input type="text" id="wagon${i}Driver" name="wagon${i}Driver" 
                           class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                           placeholder="Enter driver name">
                </div>
            `;
            wagonDetailsList.appendChild(wagonDiv);
        }
    } else {
        wagonDetailsSection.style.display = 'none';
    }
}

function checkLowDeckWarning() {
    const lowDecks = parseInt(document.getElementById('numberOfLowDecks').value) || 0;
    const wagons = parseInt(document.getElementById('numberOfWagons').value) || 0;
    const warning = document.getElementById('lowDeckWarning');
    
    if (lowDecks > 0 && wagons === 0) {
        warning.classList.remove('hidden');
    } else {
        warning.classList.add('hidden');
    }
}

// Enhanced Navigation with Conditional Logic
function nextStep(step) {
    if (validateStep(step)) {
        saveStepData(step);
        hideStep(step);
        showStep(step + 1);
        updateStepIndicators(step, step + 1);
        currentStep = step + 1;
        
        // Apply conditional logic when entering steps
        if (step + 1 === 2) {
            updateStep2Visibility();
        } else if (step + 1 === 3) {
            updateStep3Configuration();
        }
        
        if (step === 4) {
            generateReviewSummary();
        }
    }
}

// Event Listeners for Conditional Logic
document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners for conditional updates
    const shippingLineField = document.getElementById('shippingLine');
    if (shippingLineField) {
        shippingLineField.addEventListener('change', updateVesselTypeOptions);
    }
    
    const operationTypeField = document.getElementById('operationType');
    if (operationTypeField) {
        operationTypeField.addEventListener('change', updateStep3Configuration);
    }
    
    const vesselTypeField = document.getElementById('vesselType');
    if (vesselTypeField) {
        vesselTypeField.addEventListener('change', updateStep3HeavyEquipment);
    }
    
    const numberOfWagonsField = document.getElementById('numberOfWagons');
    if (numberOfWagonsField) {
        numberOfWagonsField.addEventListener('change', checkLowDeckWarning);
    }
    
    const numberOfLowDecksField = document.getElementById('numberOfLowDecks');
    if (numberOfLowDecksField) {
        numberOfLowDecksField.addEventListener('change', checkLowDeckWarning);
    }
});

console.log('Enhanced wizard with offline document processing loaded');