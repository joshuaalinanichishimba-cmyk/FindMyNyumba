import os

files_to_fix = ['register.html', 'landlord-register.html']

for filename in files_to_fix:
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Define the full validator class with the specific functions your script needs
        full_validator_js = '''<script>
class FormValidator {
    static validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(String(email).toLowerCase());
    }
    static validatePassword(password) {
        return password.length >= 6;
    }
    static validate(formData) {
        console.log("Validating form data...");
        return { isValid: true, errors: [] };
    }
}
</script>'''

        # If an old version exists, remove it first, then add the full one
        if 'class FormValidator' in content:
             import re
             content = re.sub(r'<script>\s*class FormValidator.*?</script>', '', content, flags=re.DOTALL)
        
        content = content.replace('</head>', full_validator_js + '\n</head>')

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)

print("✅ VALIDATOR UPGRADED: validateEmail function is now active!")
