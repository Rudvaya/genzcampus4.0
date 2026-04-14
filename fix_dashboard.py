import os

html_path = r'd:\Sai Kiran\projects\genzcampus\pms\templates\club\dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove duplicated block from lines 433 to 627 (indices 432 to 626)
new_lines = lines[:432] + lines[627:]

script_addition = """
// AJAX Registration Deadline Update
document.querySelectorAll('.deadline-form').forEach(form => {
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Updating...';
        submitBtn.disabled = true;

        const eventId = this.dataset.eventId;
        const formData = new FormData(this);
        
        try {
            const response = await fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                const deadlineSpan = document.getElementById(`deadline-${eventId}`);
                if (deadlineSpan) {
                    deadlineSpan.innerHTML = `<i class="fas fa-stopwatch me-1"></i> ${data.deadline}`;
                    deadlineSpan.className = 'small fw-bold mb-1 text-success';
                } else {
                    location.reload();
                    return;
                }
                
                const modalEl = document.getElementById(`deadlineModal${eventId}`);
                if (modalEl) {
                    let modal = bootstrap.Modal.getInstance(modalEl);
                    if (!modal) modal = new bootstrap.Modal(modalEl);
                    modal.hide();
                    
                    // Safety logic to remove any lingering backdrops
                    setTimeout(() => {
                        const backdrop = document.querySelector('.modal-backdrop');
                        if (backdrop) backdrop.remove();
                        document.body.classList.remove('modal-open');
                        document.body.style.overflow = '';
                        document.body.style.paddingRight = '';
                    }, 300);
                }
            } else {
                alert(data.message || 'Failed to update deadline.');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while updating the deadline.');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    });
});
</script>
{% endblock %}
"""

content = "".join(new_lines)
if "</script>\n{% endblock %}" in content:
    content = content.replace("</script>\n{% endblock %}", script_addition)
elif "</script>\r\n{% endblock %}" in content:
    content = content.replace("</script>\r\n{% endblock %}", script_addition)
else:
    # Just in case formatting is slightly off
    content = content.replace("</script>", script_addition.replace("</script>\n{% endblock %}", "</script>"))

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("dashboard.html successfully updated!")
