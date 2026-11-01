import os
import torch, torch.nn as nn, torch.nn.functional as F

torch.set_num_threads(1)

D = os.path.dirname(os.path.abspath(__file__))
chars = list(open(os.path.join(D, "vocab.txt"), encoding="utf-8").read())
V = len(chars)
stoi = {c: i for i, c in enumerate(chars)}
T, C, H, L = 128, 128, 4, 4

class Block(nn.Module):
    def __init__(s):
        super().__init__()
        s.ln1, s.ln2 = nn.LayerNorm(C), nn.LayerNorm(C)
        s.qkv = nn.Linear(C, 3 * C)
        s.proj = nn.Linear(C, C)
        s.mlp = nn.Sequential(nn.Linear(C, 4 * C), nn.GELU(), nn.Linear(4 * C, C))

    def forward(s, x, past=None):
        b, n, _ = x.shape
        q, k, v = s.qkv(s.ln1(x)).view(b, n, 3, H, C // H).permute(2, 0, 3, 1, 4)
        if past is not None:
            k = torch.cat([past[0], k], 2)
            v = torch.cat([past[1], v], 2)
        a = F.scaled_dot_product_attention(q, k, v, is_causal=past is None)
        x = x + s.proj(a.transpose(1, 2).reshape(b, n, C))
        return x + s.mlp(s.ln2(x)), (k, v)

class GPT(nn.Module):
    def __init__(s):
        super().__init__()
        s.tok = nn.Embedding(V, C)
        s.pos = nn.Embedding(T, C)
        s.blocks = nn.ModuleList([Block() for _ in range(L)])
        s.ln = nn.LayerNorm(C)
        s.head = nn.Linear(C, V)

    def forward(s, x, past=None, start=0):
        h = s.tok(x) + s.pos(torch.arange(start, start + x.size(1)))
        cache = []
        for i, blk in enumerate(s.blocks):
            h, kv = blk(h, past[i] if past else None)
            cache.append(kv)
        return s.head(s.ln(h)), cache

model = GPT()
model.load_state_dict(torch.load(os.path.join(D, "model.pt"), map_location="cpu"))
model.eval()

def stream_story(prompt="", max_new=1200, temp=0.6, top_k=10):
    prompt = "".join(c for c in prompt if c in stoi) or ""
    stop = "<|endoftext|>"
    ids = [stoi[c] for c in prompt]
    out = prompt
    sent = 0
    with torch.inference_mode():
        logits, cache = model(torch.tensor([ids[-T:]]))
        n_cached = min(len(ids), T)
        for _ in range(max_new):
            lg = logits[:, -1] / temp
            v, _ = torch.topk(lg, min(top_k, V))
            lg[lg < v[:, -1:]] = -float("inf")
            nxt = torch.multinomial(F.softmax(lg, dim=-1), 1)
            ids.append(nxt.item())
            out += chars[nxt.item()]
            if out.endswith(stop):
                out = out[:-len(stop)]
                break
            hold = 0
            for k in range(min(len(stop) - 1, len(out)), 0, -1):
                if stop.startswith(out[-k:]):
                    hold = k
                    break
            if len(out) - hold > sent:
                yield out[sent:len(out) - hold]
                sent = len(out) - hold
            if n_cached >= T:
                keep = T // 2
                logits, cache = model(torch.tensor([ids[-keep:]]))
                n_cached = keep
            else:
                logits, cache = model(nxt, past=cache, start=n_cached)
                n_cached += 1
    if len(out) > sent:
        yield out[sent:]
