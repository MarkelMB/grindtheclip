import numpy as np

# Just testing if AgglomerativeClustering works without errors
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
import librosa

audio = np.random.randn(16000 * 5)
sr = 16000

mfccs = []
for i in range(3):
    clip = audio[i*16000:(i+1)*16000]
    mfcc = librosa.feature.mfcc(y=clip, sr=sr, n_mfcc=20)
    delta = librosa.feature.delta(mfcc)
    feat = np.concatenate([np.mean(mfcc, axis=1), np.mean(delta, axis=1)])
    mfccs.append(feat)
    
mfccs = np.array(mfccs)
scaler = StandardScaler()
mfccs_scaled = scaler.fit_transform(mfccs)

clusterer = AgglomerativeClustering(n_clusters=None, distance_threshold=2.0)
labels = clusterer.fit_predict(mfccs_scaled)

print("Labels:", labels)
print("Success")
