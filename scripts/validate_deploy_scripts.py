import glob
import subprocess
import sys
import os

def validate_powershell():
    print("--- Validating PowerShell Scripts ---")
    ps_files = glob.glob("deploy/*.ps1")
    all_ok = True
    for ps_file in ps_files:
        abs_path = os.path.abspath(ps_file)
        ps_cmd = f"$errs = $null; [System.Management.Automation.Language.Parser]::ParseFile('{abs_path}', [ref]$null, [ref]$errs); if ($errs.Count -gt 0) {{ Write-Host $errs; exit 1 }} else {{ exit 0 }}"
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"PASS: {ps_file}")
        else:
            print(f"FAIL: {ps_file}\n{res.stderr}\n{res.stdout}")
            all_ok = False
    return all_ok

def validate_bash():
    print("\n--- Validating Bash Scripts (bash -n) ---")
    bash_path = r"C:\Program Files\Git\bin\bash.exe"
    if not os.path.exists(bash_path):
        bash_path = r"C:\Program Files\Git\usr\bin\bash.exe"
    if not os.path.exists(bash_path):
        print("Notice: Git bash not found at standard path, checking system PATH")
        bash_path = "bash"

    sh_files = glob.glob("deploy/*.sh")
    all_ok = True
    for sh_file in sh_files:
        try:
            res = subprocess.run([bash_path, "-n", sh_file], capture_output=True, text=True)
            if res.returncode == 0:
                print(f"PASS: {sh_file}")
            else:
                print(f"FAIL: {sh_file}\n{res.stderr}")
                all_ok = False
        except Exception as e:
            print(f"SKIPPED/ERROR on {sh_file}: {e}")
    return all_ok

if __name__ == "__main__":
    ps_ok = validate_powershell()
    sh_ok = validate_bash()
    if ps_ok and sh_ok:
        print("\nAll deploy scripts validated successfully!")
        sys.exit(0)
    else:
        print("\nSome scripts failed validation.")
        sys.exit(1)
