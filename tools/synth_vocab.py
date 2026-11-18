import numpy as np, sys, synth
EXTS = ["", "7", "7M", "9", "6", "4", "2", "sus4", "sus", "0", "07", "7(9)", "(9)", "5+", "+", "7(4)", "7(b9)", "7(#5)",
        "6(9)", "11", "13", "7sus4", "7(11)", "7(13)", "(b13)", "7(b13)", "(#5)", "5", "7M(9)", "(4)", "(sus4)", "7(sus4)", "7(b5)", "7(#9)", "9(11)", "(11)", "7(9)(13)"]
V = []
for r in "ABCDEFG":
    for a in ("", "#", "b"):
        for q in ("", "m"):
            for e in EXTS:
                for bs in [""] + list("ABCDEFG"):
                    for ba in (("",) if not bs else ("", "#", "b")):
                        V.append(r + a + q + e + ("/" + bs + ba if bs else ""))
k, n = int(sys.argv[1]), int(sys.argv[2])
part = V[k::n]
F = np.zeros((len(part), synth.FH * synth.FW), np.float16); A = np.zeros(len(part), np.float32)
for i, s in enumerate(part):
    r = synth.render(s); v, asp = synth.feat_img(r, synth.width_of(r)); F[i] = v; A[i] = asp
np.savez(f"tk/voc{k}.npz", V=np.array(part), F=F, A=A)
print(k, len(part))
