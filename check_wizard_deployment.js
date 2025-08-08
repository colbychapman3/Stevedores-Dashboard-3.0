/**
 * Quick Wizard Deployment Status Check
 * Run this in browser console to verify advanced wizard deployed
 */

console.log('🔍 Checking Advanced Maritime Wizard Deployment Status...\n');

// Check 1: Look for advanced wizard version comment
fetch('/wizard')
    .then(response => response.text())
    .then(html => {
        if (html.includes('Advanced Maritime Wizard v3.0')) {
            console.log('✅ Advanced wizard version detected in HTML');
        } else {
            console.log('❌ Advanced wizard version not found - may still be deploying');
        }
    })
    .catch(e => console.log('❌ Could not fetch wizard page'));

// Check 2: Look for K-line shipping option
const shippingSelect = document.getElementById('shippingLine');
if (shippingSelect) {
    const klineOption = Array.from(shippingSelect.options).find(opt => opt.value === 'K-line');
    if (klineOption) {
        console.log('✅ K-line shipping option found - Advanced wizard deployed!');
        
        // Check for conditional elements
        const highHeavySection = document.getElementById('highHeavySection');
        const dischargeSection = document.getElementById('dischargeSection');
        
        if (highHeavySection && dischargeSection) {
            console.log('✅ Conditional sections found - Full maritime wizard active');
            console.log('🎯 Advanced wizard successfully deployed!');
        } else {
            console.log('⚠️  Some conditional sections missing');
        }
    } else {
        console.log('❌ K-line option not found - Old wizard still active');
    }
} else {
    console.log('❌ Shipping line select not found - Old wizard structure');
}

// Check 3: Look for advanced functions
if (typeof updateShippingLineOptions === 'function') {
    console.log('✅ Advanced wizard JavaScript functions loaded');
} else {
    console.log('❌ Advanced wizard JavaScript not loaded');
}

console.log('\n📊 Deployment Status Check Complete');
console.log('If advanced features not found, wait 2-3 minutes and refresh page.');