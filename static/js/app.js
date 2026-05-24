document.addEventListener('DOMContentLoaded', () => {
    // Chart.js has been replaced with server-side Matplotlib image generation

    // Global Alert Function
    window.showAppAlert = function(message, title = "Notice") {
        const modal = document.getElementById('app-alert-modal');
        if (modal) {
            document.getElementById('app-alert-title').textContent = title;
            document.getElementById('app-alert-message').textContent = message;
            modal.style.display = 'flex';
            document.getElementById('app-alert-close').onclick = () => {
                modal.style.display = 'none';
            };
        } else {
            alert(message); // Fallback
        }
    };

    // Element Checks
    const hasDashboardStats = !!document.getElementById('total-students');
    const hasPerformanceChart = !!document.getElementById('performanceChartImg');
    const hasAttendanceChart = !!document.getElementById('attendanceChartImg');
    const hasStudentsTable = !!document.getElementById('students-table-body');
    const hasAddStudentForm = !!document.getElementById('add-student-form');
    const hasEventsList = !!document.getElementById('events-list');
    const hasAttendanceForm = !!document.getElementById('attendance-form');

    function loadDashboardData() {
        if(hasDashboardStats || hasEventsList) fetchStats();
        if(hasStudentsTable || hasAttendanceForm) fetchStudents();
        if(hasPerformanceChart || hasAttendanceChart) fetchCharts();
    }

    function fetchStats() {
        fetch('/api/dashboard-stats')
            .then(res => res.json())
            .then(data => {
                if(hasDashboardStats) {
                    document.getElementById('total-students').textContent = data.total_students !== undefined ? data.total_students : '--';
                    document.getElementById('overall-attendance').textContent = data.overall_attendance !== undefined ? data.overall_attendance + '%' : '--%';
                    document.getElementById('average-gpa').textContent = data.average_gpa !== undefined ? data.average_gpa : '--';
                }

                if(hasEventsList && data.upcoming_events) {
                    document.getElementById('events-list').innerHTML = data.upcoming_events.map(event => {
                        const dateObj = new Date(event.date);
                        const month = dateObj.toLocaleString('default', { month: 'short' });
                        const day = dateObj.getDate();
                        return `
                            <li class="event-item">
                                <div class="event-date">
                                    <div>${month}</div>
                                    <div>${day}</div>
                                </div>
                                <div class="event-details">
                                    <h4>${event.name}</h4>
                                    <p>Upcoming</p>
                                </div>
                            </li>
                        `;
                    }).join('');
                }
            });
    }

    function fetchCharts() {
        const perfImg = document.getElementById('performanceChartImg');
        const attImg = document.getElementById('attendanceChartImg');
        const t = new Date().getTime();
        if (perfImg) perfImg.src = '/api/performance-chart?t=' + t;
        if (attImg) attImg.src = '/api/attendance-trend?t=' + t;
    }

    if(hasAttendanceForm) {
        // Set date to today
        document.getElementById('attendance-date').valueAsDate = new Date();
        
        // Summary Counter Logic
        const updateSummary = () => {
            const checkboxes = document.querySelectorAll('.attendance-check');
            let present = 0, absent = 0;
            checkboxes.forEach(cb => {
                if (cb.closest('tr').style.display !== 'none') {
                    cb.checked ? present++ : absent++;
                    // Update label visually
                    const label = cb.closest('td').querySelector('.status-label');
                    if (cb.checked) {
                        label.textContent = 'Present';
                        label.className = 'status-label present';
                    } else {
                        label.textContent = 'Absent';
                        label.className = 'status-label absent';
                    }
                }
            });
            document.getElementById('summary-present').textContent = present;
            document.getElementById('summary-absent').textContent = absent;
        };

        // Live Search Filter
        document.getElementById('attendance-search').addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('#attendance-roster-body tr').forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
            updateSummary();
        });

        // Date Selection & Validation Logic
        const dateInput = document.getElementById('attendance-date');
        const submitBtn = document.querySelector('#attendance-form button[type="submit"]');
        const dayNameLabel = document.getElementById('attendance-day-name');

        const validateAndLoadDate = () => {
            const dateStr = dateInput.value;
            if (!dateStr) return;
            
            const dt = new Date(dateStr);
            const day = dt.getUTCDay(); 
            
            // Set Day Name
            const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
            dayNameLabel.textContent = `(${days[day]})`;
            
            // Check if date is "Today"
            // Get local date string matching input format
            const todayDate = new Date();
            const todayStr = todayDate.getFullYear() + '-' + String(todayDate.getMonth()+1).padStart(2, '0') + '-' + String(todayDate.getDate()).padStart(2, '0');
            const isToday = (dateStr === todayStr);
            
            if (day === 0) {
                showAppAlert("Cannot take attendance on Sundays.", "Invalid Date");
                submitBtn.disabled = true;
                dayNameLabel.style.color = "var(--danger)";
                return;
            }
            
            dayNameLabel.style.color = "var(--primary)";
            
            if (!isToday) {
                submitBtn.disabled = true;
                submitBtn.textContent = "Read-Only (Past Record)";
                submitBtn.style.background = "var(--text-muted)";
            } else {
                submitBtn.disabled = false;
                submitBtn.textContent = "Submit Attendance";
                submitBtn.style.background = "var(--primary)";
            }
            
            // Fetch records for this date
            fetch(`/api/attendance/${dateStr}`)
                .then(res => res.json())
                .then(records => {
                    document.querySelectorAll('.attendance-check').forEach(cb => {
                        const id = cb.value;
                        if (records[id] === 'absent') {
                            cb.checked = false;
                            cb.disabled = true; // Always lock absence
                        } else if (records[id] === 'present') {
                            cb.checked = true;
                            cb.disabled = !isToday; // Disable if not today
                        } else {
                            cb.checked = true; // Default
                            cb.disabled = !isToday; // Disable if not today
                        }
                    });
                    updateSummary();
                });
        };

        dateInput.addEventListener('change', validateAndLoadDate);

        // Bulk Actions
        document.getElementById('btn-mark-all').addEventListener('click', () => {
            document.querySelectorAll('.attendance-check').forEach(cb => {
                if (cb.closest('tr').style.display !== 'none' && !cb.disabled) cb.checked = true;
            });
            updateSummary();
        });

        document.getElementById('btn-mark-none').addEventListener('click', () => {
            document.querySelectorAll('.attendance-check').forEach(cb => {
                if (cb.closest('tr').style.display !== 'none' && !cb.disabled) cb.checked = false;
            });
            updateSummary();
        });

        // Toggle Listener via Delegation
        document.getElementById('attendance-roster-body').addEventListener('change', (e) => {
            if(e.target.classList.contains('attendance-check')) updateSummary();
        });
        
        // Handle Submission
        document.getElementById('attendance-form').addEventListener('submit', (e) => {
            e.preventDefault();
            
            const date = document.getElementById('attendance-date').value;
            const checkboxes = document.querySelectorAll('.attendance-check');
            const presentIds = [];
            
            checkboxes.forEach(cb => {
                // Submit only those that are checked (we ignore hidden/filtered rows logic here and submit everything checked globally)
                if(cb.checked) presentIds.push(cb.value);
            });
            
            fetch('/api/attendance/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date: date, present_ids: presentIds })
            })
            .then(async res => {
                const data = await res.json();
                if(res.ok) {
                    showAppAlert('Attendance saved successfully!', 'Success');
                    document.getElementById('attendance-search').value = '';
                    loadDashboardData(); // Refresh the roster to show new percentages
                } else {
                    showAppAlert('Failed to save attendance: ' + (data.error || 'Unknown error'), 'Error');
                }
            });
        });

        // History Modal Event Delegation
        const historyModal = document.getElementById('student-history-modal');
        const historyClose = document.getElementById('close-history-modal');
        
        if (historyModal && historyClose) {
            historyClose.onclick = () => historyModal.style.display = 'none';
            
            document.getElementById('attendance-roster-body').addEventListener('click', (e) => {
                const btn = e.target.closest('.view-history-btn');
                if (!btn) return;
                
                const id = btn.getAttribute('data-id');
                const name = btn.getAttribute('data-name');
                
                document.getElementById('history-student-name').textContent = name;
                document.getElementById('history-student-id').textContent = id;
                
                const loading = document.getElementById('history-loading');
                const calendarView = document.getElementById('history-calendar-view');
                
                loading.style.display = 'block';
                calendarView.style.display = 'none';
                historyModal.style.display = 'flex';
                
                fetch(`/api/students/${id}/attendance`)
                    .then(res => res.json())
                    .then(history => {
                        loading.style.display = 'none';
                        calendarView.style.display = 'flex';
                        
                        // Convert history to dictionary map
                        const recordMap = {};
                        history.forEach(r => { recordMap[r.date] = r.status; });
                        
                        const generateMonthHTML = (year, monthIndex, monthName) => {
                            const date = new Date(year, monthIndex, 1);
                            const startingDay = date.getDay();
                            const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
                            
                            let html = `
                                <div>
                                    <h4 style="text-align: center; margin-bottom: 1rem; color: var(--text-primary); font-size: 1.1rem;">${monthName} ${year}</h4>
                                    <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; text-align: center;">
                                        <div style="font-weight: 600; font-size: 0.8rem; color: var(--text-muted);">Su</div>
                                        <div style="font-weight: 600; font-size: 0.8rem; color: var(--text-muted);">Mo</div>
                                        <div style="font-weight: 600; font-size: 0.8rem; color: var(--text-muted);">Tu</div>
                                        <div style="font-weight: 600; font-size: 0.8rem; color: var(--text-muted);">We</div>
                                        <div style="font-weight: 600; font-size: 0.8rem; color: var(--text-muted);">Th</div>
                                        <div style="font-weight: 600; font-size: 0.8rem; color: var(--text-muted);">Fr</div>
                                        <div style="font-weight: 600; font-size: 0.8rem; color: var(--text-muted);">Sa</div>
                            `;
                            
                            // Blank days before start of month
                            for (let i = 0; i < startingDay; i++) {
                                html += `<div></div>`;
                            }
                            
                            // Days
                            for (let i = 1; i <= daysInMonth; i++) {
                                const currentDay = new Date(year, monthIndex, i).getDay();
                                const dateStr = `${year}-${String(monthIndex + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
                                
                                let bgColor = 'transparent';
                                let textColor = 'var(--text-primary)';
                                let border = '1px solid var(--border-color)';
                                
                                if (currentDay === 0) { // Sunday
                                    bgColor = 'var(--bg-body)';
                                    textColor = 'var(--text-muted)';
                                    border = '1px solid transparent';
                                } else if (recordMap[dateStr] === 'present') {
                                    bgColor = 'var(--success)';
                                    textColor = '#fff';
                                    border = '1px solid var(--success)';
                                } else if (recordMap[dateStr] === 'absent') {
                                    bgColor = 'var(--danger)';
                                    textColor = '#fff';
                                    border = '1px solid var(--danger)';
                                }
                                
                                html += `<div style="
                                    aspect-ratio: 1; 
                                    display: flex; 
                                    align-items: center; 
                                    justify-content: center; 
                                    border-radius: 8px; 
                                    background: ${bgColor}; 
                                    color: ${textColor}; 
                                    border: ${border};
                                    font-size: 0.9rem;
                                    font-weight: 500;
                                ">${i}</div>`;
                            }
                            
                            html += `</div></div>`;
                            return html;
                        };
                        
                        // Generate May 2026 calendar
                        calendarView.innerHTML = `
                            <div style="display:flex; justify-content:center; gap: 1rem; margin-bottom: 1rem;">
                                <div style="display:flex; align-items:center; gap: 5px; font-size: 0.8rem;"><div style="width:12px; height:12px; border-radius:3px; background:var(--success);"></div> Present</div>
                                <div style="display:flex; align-items:center; gap: 5px; font-size: 0.8rem;"><div style="width:12px; height:12px; border-radius:3px; background:var(--danger);"></div> Absent</div>
                                <div style="display:flex; align-items:center; gap: 5px; font-size: 0.8rem;"><div style="width:12px; height:12px; border-radius:3px; border:1px solid var(--border-color);"></div> Unmarked</div>
                            </div>
                            ${generateMonthHTML(2026, 4, 'May')}
                        `;
                    })
                    .catch(err => {
                        loading.textContent = "Failed to load history.";
                    });
            });
        }
    }

    function fetchStudents() {
        fetch('/api/students')
            .then(res => res.json())
            .then(students => {
                // Populate Manage Students Table
                if(hasStudentsTable) {
                    const tbody = document.getElementById('students-table-body');
                    
                    const getStatusClass = (status) => {
                        if (!status) return 'status-needs-improvement';
                        switch(status.toLowerCase()) {
                            case 'excellent': return 'status-excellent';
                            case 'good': return 'status-good';
                            case 'average': return 'status-average';
                            default: return 'status-needs-improvement';
                        }
                    };

                    tbody.innerHTML = students.map(student => `
                        <tr>
                            <td>
                                <div style="font-weight: 500; color: var(--text-primary);">${student.name}</div>
                                <div style="font-size: 0.75rem; color: var(--text-secondary);">${student.id}</div>
                            </td>
                            <td>${student.major}</td>
                            <td><strong>${parseFloat(student.gpa).toFixed(2)}</strong></td>
                            <td>${student.attendance}%</td>
                            <td>
                                <span class="status-badge ${getStatusClass(student.status)}">
                                    ${student.status || 'Unknown'}
                                </span>
                            </td>
                            <td>
                                <button class="btn-icon delete-btn" data-id="${student.id}" data-name="${student.name}" title="Delete Student">
                                    🗑️
                                </button>
                            </td>
                        </tr>
                    `).join('');
                    
                    // Modal Elements
                    const deleteModal = document.getElementById('delete-modal');
                    const confirmBtn = document.getElementById('confirm-delete-btn');
                    const cancelBtn = document.getElementById('cancel-delete-btn');
                    const studentNameDisplay = document.getElementById('delete-student-name');
                    
                    // Cleanup old listeners to prevent multiple fires
                    const newConfirmBtn = confirmBtn.cloneNode(true);
                    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
                    
                    document.querySelectorAll('.delete-btn').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const id = e.currentTarget.getAttribute('data-id');
                            const name = e.currentTarget.getAttribute('data-name');
                            
                            // Show custom modal
                            studentNameDisplay.textContent = name;
                            deleteModal.style.display = 'flex';
                            
                            // Setup confirm action
                            newConfirmBtn.onclick = () => {
                                deleteModal.style.display = 'none';
                                deleteStudent(id);
                            };
                        });
                    });
                    
                    cancelBtn.onclick = () => {
                        deleteModal.style.display = 'none';
                    };
                }
                
                // Populate Attendance Roster
                if(hasAttendanceForm) {
                    const rosterBody = document.getElementById('attendance-roster-body');
                    const totalSemesterDays = 26;
                    let currentClassDays = 0;
                    
                    if (students.length > 0) {
                        currentClassDays = students[0].total_class_days || 0;
                    }
                    
                    // Update Semester Stats Bar
                    document.getElementById('stats-remaining-days').textContent = (totalSemesterDays - currentClassDays);
                    
                    rosterBody.innerHTML = students.map(student => `
                        <tr>
                            <td><div style="font-size: 0.85rem; color: var(--text-secondary);">${student.id}</div></td>
                            <td><div style="font-weight: 500; color: var(--text-primary);">${student.name}</div></td>
                            <td>${student.attendance}%</td>
                            <td>
                                <label class="switch">
                                    <input type="checkbox" class="attendance-check" value="${student.id}" checked>
                                    <span class="slider"></span>
                                </label>
                                <span class="status-label present">Present</span>
                            </td>
                            <td style="text-align: right;">
                                <button type="button" class="btn-secondary btn-sm view-history-btn" data-id="${student.id}" data-name="${student.name}" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;">View Details</button>
                            </td>
                        </tr>
                    `).join('');
                    
                    // Trigger initial summary count and date validation
                    const evt = new Event('input');
                    document.getElementById('attendance-search').dispatchEvent(evt);
                    validateAndLoadDate();
                }
            });
    }

    if (hasAddStudentForm) {
        document.getElementById('add-student-form').addEventListener('submit', (e) => {
            e.preventDefault();
            
            const newStudent = {
                id: document.getElementById('student-id').value,
                name: document.getElementById('student-name').value,
                major: document.getElementById('student-major').value, // Now reads from <select>
                gpa: parseFloat(document.getElementById('student-gpa').value),
                attendance: parseInt(document.getElementById('student-attendance').value)
                // Status is removed, backend calculates it
            };

            fetch('/api/students', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newStudent)
            })
            .then(res => {
                if(res.ok) {
                    e.target.reset();
                    showAppAlert('Student added successfully!', 'Success');
                    loadDashboardData();
                } else {
                    showAppAlert('Failed to add student.', 'Error');
                }
            });
        });
    }

    function deleteStudent(id) {
        fetch(`/api/students/${id}`, {
            method: 'DELETE'
        })
        .then(res => {
            if(res.ok) {
                loadDashboardData();
            } else {
                showAppAlert('Failed to delete student.', 'Error');
            }
        });
    }

    // Initial Load
    loadDashboardData();
});
