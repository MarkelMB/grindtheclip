import os
import librosa
p = r"C:\Users\marke\AppData\Roaming\YeahMaybe\ChoicerVoicer\game\packs_voice\Erwin's Speech"
d1 = librosa.get_duration(path=os.path.join(p, '01_Erwin.mp3'))
d2 = librosa.get_duration(path=os.path.join(p, '02_Erwin.mp3'))
print("01_Erwin.mp3 length:", d1)
print("02_Erwin.mp3 length:", d2)
