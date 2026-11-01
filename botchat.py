import os
import torch, torch.nn as nn, torch.nn.functional as F

torch.set_num_threads(1)

D = os.path.dirname(os.path.abspath(__file__))
chars = list(open(os.path.join(D, "chat_vocab.txt"), encoding="utf-8").read())
stoi = {c: i for i, c in enumerate(chars)}
sd = torch.load(os.path.join(D, "chat_model.pt"), map_location="cpu")
V, C = sd["tok.weight"].shape
T = sd["pos.weight"].shape[0]
L = len({k.split(".")[1] for k in sd if k.startswith("blocks.")})
H = C // 32

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
model.load_state_dict(sd)
model.eval()

STOPS = ("\nUser:", "\n\n")
def visible(out):
    cut = 0
    for stop in STOPS:
        for k in range(len(stop), 0, -1):
            if out.endswith(stop[:k]):
                cut = max(cut, k)
                break
    return out[:len(out) - cut].strip()

def stream(msg, history=(), max_new=300, temp=0.5, top_k=10):
    msg = "".join(c for c in msg.replace("\n", " ") if c in stoi).strip()
    if not msg:
        yield "Use normal letters, please."
        return
    turns = list(history)
    last = f"User: {msg}\nBot:"
    while turns and len("".join(f"User: {u}\nBot: {b}\n" for u, b in turns)) + len(last) > T - 80:
        turns.pop(0)
    prompt = "".join(f"User: {u}\nBot: {b}\n" for u, b in turns) + last
    ids = [stoi[c] for c in prompt if c in stoi]
    out = ""
    with torch.inference_mode():
        logits, cache = model(torch.tensor([ids[-T:]]))
        n = min(len(ids), T)
        for _ in range(max_new):
            lg = logits[:, -1] / temp
            v, _ = torch.topk(lg, min(top_k, V))
            lg[lg < v[:, -1:]] = -float("inf")
            nxt = torch.multinomial(F.softmax(lg, dim=-1), 1)
            ids.append(nxt.item())
            out += chars[nxt.item()]
            yield visible(out)
            if out.endswith(STOPS):
                break
            if n >= T:
                keep = T // 2
                logits, cache = model(torch.tensor([ids[-keep:]]))
                n = keep
            else:
                logits, cache = model(nxt, past=cache, start=n)
                n += 1

def reply(msg, history=()):
    text = ""
    for text in stream(msg, history):
        pass
    return text or "..."
