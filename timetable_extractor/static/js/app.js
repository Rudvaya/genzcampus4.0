let extractedData = null;

document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    document.getElementById('loader').style.display = 'block';
    document.getElementById('verificationScreen').style.display = 'none';
    document.getElementById('btnExtract').disabled = true;
    
    try {
        const response = await fetch('/api/timetable/extract', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            extractedData = result.data;
            renderVerificationScreen(result.data);
        } else {
            alert("Extraction Error: " + result.error + (result.needs_manual_review ? "\nManual review required." : ""));
        }
    } catch (err) {
        alert("Failed to connect to the server.");
    } finally {
        document.getElementById('loader').style.display = 'none';
        document.getElementById('btnExtract').disabled = false;
    }
});

function renderVerificationScreen(data) {
    document.getElementById('verificationScreen').style.display = 'block';
    
    document.getElementById('metaInfo').innerHTML = 
        `<strong>Department:</strong> ${data.department} | <strong>Year:</strong> ${data.year} | <strong>Section:</strong> ${data.section}`;
        
    document.getElementById('rawJson').innerText = JSON.stringify(data, null, 2);
    
    const table = document.getElementById('timetableGrid');
    table.innerHTML = '';
    
    // Header Row 1: Periods
    let thead = document.createElement('thead');
    let trPeriod = document.createElement('tr');
    trPeriod.innerHTML = '<th>DAY / PERIOD</th>';
    data.periods.forEach(p => {
        trPeriod.innerHTML += `<th>${p.id}</th>`;
    });
    thead.appendChild(trPeriod);
    
    // Header Row 2: Timings
    let trTime = document.createElement('tr');
    trTime.innerHTML = '<th>TIMINGS</th>';
    data.periods.forEach(p => {
        trTime.innerHTML += `<th>${p.start} - ${p.end}</th>`;
    });
    thead.appendChild(trTime);
    table.appendChild(thead);
    
    // Body: Days
    let tbody = document.createElement('tbody');
    data.days.forEach(day => {
        let trDay = document.createElement('tr');
        trDay.innerHTML = `<td><strong>${day}</strong></td>`;
        
        const dayData = data.timetable[day] || {};
        
        let skipNext = 0;
        
        data.periods.forEach((p, index) => {
            if (skipNext > 0) {
                skipNext--;
                return;
            }
            
            const cell = dayData[p.id];
            if (cell) {
                let colSpan = 1;
                if (cell.periods && cell.periods.length > 1 && cell.periods[0] === p.id) {
                    colSpan = cell.periods.length;
                    skipNext = colSpan - 1;
                }
                
                let cssClass = 'cell-lecture';
                if (cell.type === 'lab') cssClass = 'cell-lab';
                if (cell.type === 'break') cssClass = 'cell-break';
                
                trDay.innerHTML += `<td class="${cssClass}" colspan="${colSpan}">
                    ${cell.subject}
                </td>`;
            } else {
                trDay.innerHTML += `<td></td>`;
            }
        });
        
        tbody.appendChild(trDay);
    });
    
    table.appendChild(tbody);
}

function editMode() {
    alert("Edit Mode: In a full production app, this would turn the table cells into input fields or open a modal to edit the raw JSON directly.");
}

async function saveTimetable() {
    if (!extractedData) return;
    
    try {
        const response = await fetch('/api/timetable/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(extractedData)
        });
        
        const result = await response.json();
        if (result.success) {
            alert(`Timetable saved successfully! ID: ${result.timetable_id}`);
            // Optional: reset form or redirect
        } else {
            alert(`Failed to save: ${result.error}`);
        }
    } catch (err) {
        alert("Failed to connect to the server.");
    }
}
