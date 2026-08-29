import os
import sys
import time
import warnings
import glob

try:
    import numpy as np
    import librosa
    import sounddevice as sd
except ImportError:
    print("Faltan dependencias. Por favor, ejecuta:")
    print("pip install numpy librosa sounddevice")
    sys.exit(1)

warnings.filterwarnings('ignore', category=UserWarning)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def extract_features(y, sr):
    """Extrae Tono (F0), Energía (RMS) y Timbre (MFCC)."""
    # 1. Tono (Pitch/F0)
    f0, voiced_flag, _ = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr)
    
    # 2. Energía (Volumen)
    rms = librosa.feature.rms(y=y)[0]
    
    # 3. Timbre/Forma de la voz (MFCC - coeficientes cepstrales)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    
    return f0, voiced_flag, rms, mfcc

def normalize(arr):
    arr_min = np.nanmin(arr)
    arr_max = np.nanmax(arr)
    if arr_max == arr_min: return arr
    return (arr - arr_min) / (arr_max - arr_min)

def calculate_correlation(arr1, arr2):
    if np.std(arr1) == 0 or np.std(arr2) == 0:
        return 0.0
    return np.corrcoef(arr1, arr2)[0, 1]

def compare_audio(ref_y, user_y, sr):
    print("Analizando tu voz y calculando resultados (Estilo The Choicer Voicer)...")
    ref_f0, ref_voiced, ref_rms, ref_mfcc = extract_features(ref_y, sr)
    user_f0, user_voiced, user_rms, user_mfcc = extract_features(user_y, sr)
    
    min_len = min(len(ref_f0), len(user_f0))
    
    # --- Métrica A: Tono (Pitch) ---
    voiced_mask = ref_voiced[:min_len] & user_voiced[:min_len]
    if np.sum(voiced_mask) > 5:
        metric_a = calculate_correlation(ref_f0[:min_len][voiced_mask], user_f0[:min_len][voiced_mask])
    else:
        metric_a = 0.0
        
    # --- Métrica B: Energía (Volumen) ---
    metric_b = calculate_correlation(normalize(ref_rms[:min_len]), normalize(user_rms[:min_len]))
    
    # --- Métrica C: Timbre (MFCC) ---
    mfcc_corrs = []
    for i in range(13):
        corr = calculate_correlation(ref_mfcc[i, :min_len], user_mfcc[i, :min_len])
        mfcc_corrs.append(corr)
    metric_c = np.mean(mfcc_corrs)
    
    # --- Fórmula de Puntuación (Regresión basada en logs) ---
    score = (8.5 * metric_a) + (5.0 * metric_b) + (3.5 * metric_c) - 8.5
    unclamped_score = int(round(score))
    
    return unclamped_score, metric_a, metric_b, metric_c

def play_round(ref_file):
    clear_screen()
    print("="*50)
    print(f" JUGANDO CLIP: {os.path.basename(ref_file)}")
    print("="*50)
    
    try:
        ref_y, sr = librosa.load(ref_file, sr=None, mono=True)
    except Exception as e:
        print(f"Error al cargar el archivo de audio: {e}")
        input("Presiona ENTER para volver al menú...")
        return
        
    duration = len(ref_y) / sr
    
    print("\n[ PASO 1: ESCUCHAR ]")
    input("Presiona ENTER para reproducir el clip original y estudiarlo...")
    print(f"Reproduciendo... (Duración: {duration:.2f}s)")
    sd.play(ref_y, sr)
    sd.wait()
    
    print("\n[ PASO 2: DOBLAR ]")
    input("Presiona ENTER cuando estés listo para grabar tu versión...")
    
    print("Prepárate...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
        
    print("\n>>> ¡GRABANDO! ¡Habla ahora! >>>")
    try:
        user_rec = sd.rec(int(duration * sr), samplerate=sr, channels=1, blocking=True)
        print(">>> ¡Tiempo agotado! Grabación finalizada. >>>\n")
    except Exception as e:
         print(f"Error durante la grabación: {e}")
         input("Presiona ENTER para volver al menú...")
         return
         
    user_y = user_rec.flatten()
    
    # Evaluar
    score, m_a, m_b, m_c = compare_audio(ref_y, user_y, sr)
    
    print("\n" + "="*50)
    print("                 RESULTADOS                 ")
    print("="*50)
    print(f" Precisión de Tono (Pitch)   : {m_a:.3f}")
    print(f" Precisión de Volumen (RMS)  : {m_b:.3f}")
    print(f" Precisión de Timbre (MFCC)  : {m_c:.3f}")
    print("-" * 50)
    print(f" PUNTUACIÓN FINAL (Unclamped): {score}")
    print("="*50)
    
    if score >= 8:
        print(" VEREDICTO: ¡DIOS DEL DOBLAJE! (Posible FW Bonus)")
    elif score >= 5:
        print(" VEREDICTO: Muy buena actuación.")
    elif score >= 2:
        print(" VEREDICTO: Decente, pero le falta alma.")
    elif score >= 0:
        print(" VEREDICTO: Apenas pasable.")
    else:
        print(" VEREDICTO: Desastroso. Has arruinado el clip.")
        
    print("\n")
    input("Presiona ENTER para continuar...")

def main():
    while True:
        clear_screen()
        print("="*50)
        print("           THE CHOICER VOICER - CLONE           ")
        print("="*50)
        
        # Buscar archivos .wav en el directorio actual o en una carpeta "clips"
        wav_files = glob.glob("*.wav") + glob.glob("clips/*.wav")
        
        if not wav_files:
            print("No se encontraron archivos .wav en esta carpeta.")
            print("Por favor, coloca algunos archivos de audio para jugar.")
            print("1. Salir")
            choice = input("\nSelecciona una opción: ")
            if choice == '1':
                break
            continue
            
        print("Clips disponibles para doblar:\n")
        for i, file in enumerate(wav_files):
            print(f" [{i+1}] - {os.path.basename(file)}")
            
        print(f" [{len(wav_files) + 1}] - Salir del juego")
        
        choice = input("\nElige el número del clip que quieres jugar: ")
        
        try:
            choice_idx = int(choice) - 1
            if choice_idx == len(wav_files):
                break
            elif 0 <= choice_idx < len(wav_files):
                play_round(wav_files[choice_idx])
            else:
                print("Opción inválida.")
                time.sleep(1)
        except ValueError:
            print("Por favor, introduce un número válido.")
            time.sleep(1)
            
    print("¡Gracias por jugar!")

if __name__ == "__main__":
    main()
