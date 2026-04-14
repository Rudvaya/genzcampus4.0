content = open('templates/admin/clubs.html', 'r').read()

reset_form = """
                        <!-- Quick Password Reset -->
                        <form method="POST" action="{{ url_for('reset_club_password', club_id=club.id) }}"
                            class="mt-2 pt-2 border-top d-flex gap-2 align-items-center">
                            <input type="password" name="new_password" class="form-control form-control-sm"
                                placeholder="Set New Portal Password" required minlength="4" style="max-width:200px;">
                            <button type="submit" class="btn btn-sm btn-warning fw-bold">
                                <i class="fas fa-key me-1"></i>Reset Password
                            </button>
                        </form>"""

old = '                    </div>\n                    {% endfor %}'
new = reset_form + '\n                    </div>\n                    {% endfor %}'

if old in content:
    content = content.replace(old, new, 1)
    open('templates/admin/clubs.html', 'w').write(content)
    print('Done! Password reset form added.')
else:
    print('Target string not found. Current content around endfor:')
    idx = content.find('{% endfor %}')
    print(repr(content[max(0, idx-200):idx+20]))
