# 🚢 Advanced Maritime Wizard - Production Testing Checklist

## **Test Environment**
- **Production URL**: [Your Render deployment URL]
- **Test Date**: $(date)
- **Version**: Advanced 4-Step Maritime Wizard (commits: db3985d + bfbcfab)

---

## **🧪 Test 1: Shipping Line Conditional Logic**

### **K-line Testing (Advanced Features)**
- [ ] **Step 1**: Select "K-line" as shipping line
- [ ] **Vessel Type Options**: Verify "Heavy Only" and "Auto + Heavy" options appear
- [ ] **Step 2**: High Heavy Team section becomes visible
- [ ] **Step 3**: Heavy equipment fields appear for "Auto + Heavy" vessel type
- [ ] **Cross-step**: Changes in Step 1 properly cascade to Steps 2 & 3

### **Other Lines Testing (Simplified Workflow)**
- [ ] **Step 1**: Select "Grimaldi", "Glovis", or "MOL"
- [ ] **Vessel Type Options**: Verify "Heavy Only" and "Auto + Heavy" are hidden
- [ ] **Step 2**: High Heavy Team section remains hidden
- [ ] **Step 3**: Heavy equipment fields remain hidden
- [ ] **Auto-reset**: High heavy team resets when switching from K-line

---

## **🧪 Test 2: Operation Type Workflows**

### **Discharge Only**
- [ ] **Step 1**: Select "Discharge Only" operation type
- [ ] **Step 3**: Only discharge section visible
- [ ] **Validation**: Discharge total autos required
- [ ] **Heavy Equipment**: Shows only for K-line + Auto+Heavy

### **Loading Only**  
- [ ] **Step 1**: Select "Loading Only" operation type
- [ ] **Step 3**: Only loading section visible
- [ ] **Validation**: Loading total autos required
- [ ] **Heavy Equipment**: Shows only for K-line + Auto+Heavy

### **Discharge + Loadback**
- [ ] **Step 1**: Select "Discharge + Loadback" operation type
- [ ] **Step 3**: Both discharge AND loadback sections visible
- [ ] **Validation**: Both discharge and loadback autos required
- [ ] **Heavy Equipment**: Shows in both sections for K-line + Auto+Heavy

---

## **🧪 Test 3: Team Assignment Management**

### **Auto Operations Team (Always Visible)**
- [ ] **Members Selection**: Dropdown with stevedore names + Custom option
- [ ] **Custom Names**: Custom input appears when "Custom" selected
- [ ] **Validation**: At least 1 auto operations team member required
- [ ] **Dynamic Fields**: Correct number of member fields generated

### **High Heavy Team (K-line Only)**
- [ ] **Visibility**: Only shows for K-line shipping line
- [ ] **Hide/Reset**: Properly hides and resets for other shipping lines
- [ ] **Member Management**: Same dropdown + custom functionality as auto team
- [ ] **Validation**: High heavy members validated only for K-line

---

## **🧪 Test 4: TICO Vehicle Management**

### **Van Management**
- [ ] **Count Selection**: Number of vans dropdown (0-10+)
- [ ] **Details Section**: Van details appear when count > 0
- [ ] **Driver Assignment**: ID number and driver name fields for each van
- [ ] **Dynamic Generation**: Correct number of van detail forms

### **Wagon Management**
- [ ] **Count Selection**: Number of wagons dropdown (0-10+)
- [ ] **Details Section**: Wagon details appear when count > 0
- [ ] **Driver Assignment**: ID number and driver name fields for each wagon
- [ ] **Low Deck Warning**: Warning appears when low decks > 0 but wagons = 0

### **Operational Parameters**
- [ ] **Total Drivers**: Required field validation
- [ ] **Shift Times**: Start/end time inputs working
- [ ] **Target Completion**: Date/time picker functional
- [ ] **Integration**: TICO counts integrate with operational planning

---

## **🧪 Test 5: Data Persistence & JSON Storage**

### **Team Assignments JSON**
- [ ] **Storage**: Team data properly stored as JSON in database
- [ ] **Retrieval**: Team assignments load correctly when editing vessel
- [ ] **Structure**: Auto operations and high heavy teams stored separately
- [ ] **Custom Names**: Custom member names persist correctly

### **Cargo Configuration JSON**
- [ ] **Storage**: Cargo config properly stored as JSON in database
- [ ] **Retrieval**: Cargo configuration loads correctly when editing vessel
- [ ] **Conditional Data**: Different operation types store appropriate sections
- [ ] **Vehicle Types**: Dynamic vehicle type data persists

---

## **🧪 Test 6: Progressive Disclosure & UX**

### **Step Navigation**
- [ ] **Forward Navigation**: Can't proceed without required fields
- [ ] **Conditional Validation**: Validation rules adapt to selections
- [ ] **Step Indicators**: Progress indicators update correctly
- [ ] **Back Navigation**: Previous data preserved when going back

### **Document Auto-fill**
- [ ] **Step 1**: Document upload and auto-fill working
- [ ] **Step 2**: Team assignment document processing
- [ ] **Step 3**: Cargo document auto-fill functional
- [ ] **Step 4**: Operational parameters document integration

---

## **🧪 Test 7: End-to-End Maritime Scenarios**

### **Scenario 1: K-line Auto+Heavy with Discharge+Loadback**
- [ ] **Complete Workflow**: Full 4-step process with all advanced features
- [ ] **Data Integrity**: All conditional data properly saved
- [ ] **Team Management**: Both auto operations and high heavy teams
- [ ] **TICO Integration**: Full van/wagon assignment with drivers

### **Scenario 2: Grimaldi Auto-Only with Discharge Only**
- [ ] **Simplified Workflow**: Streamlined process for non-K-line operations
- [ ] **Conditional Hiding**: Advanced features properly hidden
- [ ] **Data Accuracy**: Only relevant data captured and stored
- [ ] **User Experience**: Clean, focused interface for simple operations

### **Scenario 3: Mixed Operations Testing**
- [ ] **Shipping Line Switch**: Test switching between K-line and others
- [ ] **Operation Type Switch**: Test changing operation types
- [ ] **Reset Behavior**: Conditional fields reset appropriately
- [ ] **Data Consistency**: No orphaned data from hidden fields

---

## **🎯 Success Criteria**

### **Technical Success**
- [ ] All conditional logic functions correctly
- [ ] No JavaScript errors in browser console
- [ ] Database stores JSON data properly
- [ ] Backward compatibility with existing vessels maintained

### **Functional Success**
- [ ] Maritime workflows feel natural and professional
- [ ] Progressive disclosure prevents user confusion
- [ ] Validation guides users effectively
- [ ] TICO vehicle management works end-to-end

### **Data Success**
- [ ] Complex maritime data captured accurately
- [ ] JSON storage enables rich data structures
- [ ] Conditional data only saved when relevant
- [ ] Existing simple vessels remain functional

---

## **🚨 Issues Found**
- [ ] Issue 1: [Description]
- [ ] Issue 2: [Description]
- [ ] Issue 3: [Description]

## **✅ Test Results Summary**
- **Total Tests**: [Count]
- **Passed**: [Count]
- **Failed**: [Count]
- **Success Rate**: [Percentage]

---
*Advanced Maritime Wizard Testing Checklist*
*Generated: $(date)*