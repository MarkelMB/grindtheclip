import os
import sys
import subprocess

def push_to_github(repo_url):
    print(f"Iniciando subida automática a GitHub: {repo_url}")
    
    # 1. Initialize git if not initialized
    if not os.path.exists(".git"):
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "config", "user.name", "GrindTheClip Developer"], check=True)
        subprocess.run(["git", "config", "user.email", "developer@grindtheclip.game"], check=True)
    
    # 2. Add all files
    subprocess.run(["git", "add", "."], check=True)
    
    # 3. Commit
    subprocess.run(["git", "commit", "-m", "Initial commit: GrindTheClip with Supabase & Auto-Updater"], check=False)
    
    # 4. Set main branch
    subprocess.run(["git", "branch", "-M", "main"], check=True)
    
    # 5. Remote
    subprocess.run(["git", "remote", "remove", "origin"], check=False)
    subprocess.run(["git", "remote", "add", "origin", repo_url], check=True)
    
    # 6. Push
    print("Enviando código al repositorio privado...")
    result = subprocess.run(["git", "push", "-u", "origin", "main", "--force"], capture_output=True, text=True)
    if result.returncode == 0:
        print("¡Éxito total! Código subido a GitHub correctamente.")
        return True
    else:
        print(f"Error al subir: {result.stderr}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        push_to_github(sys.argv[1])
    else:
        print("Uso: python push_to_github.py <URL_DEL_REPOSITORIO>")
