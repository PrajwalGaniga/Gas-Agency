import re

filepath = r"c:\Users\ASUS\Desktop\Projects\gas-delivery\GasAgencySystem\templates\inventory_management.html"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update setDateRange pushState
setDateRange_target = """        currentFilterDateStart = start;
        currentFilterDateEnd = end;
        fetchLedgerData();"""
setDateRange_replacement = """        currentFilterDateStart = start;
        currentFilterDateEnd = end;
        
        // Push State correctly to URL for persistence
        const localDateStr = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
        const searchParams = new URLSearchParams(window.location.search);
        searchParams.set("date", localDateStr);
        window.history.pushState(null, '', window.location.pathname + '?' + searchParams.toString());

        fetchLedgerData();"""

content = content.replace(setDateRange_target, setDateRange_replacement)

# 2. Update fetchLedgerData spinner
fetch_target = """        let uri = `/admin/api/inventory/ledger?start_date=${encodeURIComponent(startIso)}&end_date=${encodeURIComponent(endIso)}`;
        if (searchQ) uri += `&driver_name=${encodeURIComponent(searchQ)}`;

        try {"""
fetch_replacement = """        let uri = `/admin/api/inventory/ledger?start_date=${encodeURIComponent(startIso)}&end_date=${encodeURIComponent(endIso)}`;
        if (searchQ) uri += `&driver_name=${encodeURIComponent(searchQ)}`;
        
        const loader = document.getElementById('ledgerLoading');
        const initialRow = document.getElementById('initial-empty-row');
        if(initialRow) initialRow.remove();
        if(loader) loader.classList.remove('hidden');

        try {"""

content = content.replace(fetch_target, fetch_replacement)

# 3. Update fetchLedgerData finally block and On Load logic
finally_target = """        } catch (err) {
            console.error("Ledger fetch error:", err);
        }
    }
    
    // Setup initial default logic on load without triggering fetch"""

finally_replacement = """        } catch (err) {
            console.error("Ledger fetch error:", err);
        } finally {
            if(loader) loader.classList.add('hidden');
        }
    }
    
    // --- ON LOAD PERSISTENCE ---
    document.addEventListener('DOMContentLoaded', () => {
        const urlParams = new URLSearchParams(window.location.search);
        const dateParam = urlParams.get('date');
        
        if (dateParam) {
            // Determine if it matches today or yesterday
            const today = new Date();
            const yesterday = new Date();
            yesterday.setDate(today.getDate() - 1);
            
            const tStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
            const yStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`;
            
            if (dateParam === tStr) {
                setDateRange('today');
            } else if (dateParam === yStr) {
                setDateRange('yesterday');
            } else {
                document.getElementById('custom-start-date').value = dateParam;
                setDateRange('custom');
            }
        } else {
            // Fallback to today behavior visually on load if no param
            document.getElementById('btn-today').className = "px-4 h-full font-bold bg-primary/10 text-primary transition-colors flex items-center justify-center";
        }
    });
    
    // Setup initial default logic on load without triggering fetch"""

content = content.replace(finally_target, finally_replacement)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("HTML Patched!")
