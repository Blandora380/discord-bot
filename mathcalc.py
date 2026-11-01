import ast, operator, random, re

OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}

WORDS = [
    (r"\bmultiplied by\b|\btimes\b", "*"),
    (r"\bdivided by\b", "/"),
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
]

FILLER = {
    "ok", "okay", "so", "hey", "hi", "please", "pls", "what", "whats", "what's",
    "is", "are", "calculate", "calc", "solve", "compute", "can", "you", "how",
    "much", "quick", "math", "the", "answer", "to", "of", "tell", "me", "equals",
    "equal", "then", "and", "um", "uh",
}

def _eval(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in OPS:
        a, b = _eval(n.left), _eval(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 100:
            raise ValueError
        return OPS[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
        return OPS[type(n.op)](_eval(n.operand))
    raise ValueError

def calc(msg):
    t = msg.lower().strip()
    for pat, sym in WORDS:
        t = re.sub(pat, sym, t)
    t = re.sub(r"(?<=[\d)])\s*[x×]\s*(?=[\d(])", "*", t)
    t = t.replace("÷", "/").replace("^", "**")
    cands = [c.strip() for c in re.findall(r"[\d(][\d\s+\-*/().%]*", t) if re.search(r"\d", c)]
    if len(cands) != 1 or not re.search(r"[-+*/%]", cands[0]):
        return None
    expr = cands[0]
    left = t.replace(expr, " ")
    if any(w not in FILLER for w in re.findall(r"[a-z']+", left)):
        return None
    try:
        r = _eval(ast.parse(expr, mode="eval").body)
    except ZeroDivisionError:
        return random.choice(["You can't divide by zero.", "Dividing by zero doesn't work."])
    except Exception:
        return None
    r = str(round(r, 6)).rstrip("0").rstrip(".") if isinstance(r, float) else str(r)
    shown = re.sub(r"\s+", " ", expr.replace("**", "^").replace("*", "×"))
    return random.choice([
        f"{shown} = {r}",
        f"That's {r}.",
        f"{shown} is {r}.",
        f"Easy, it's {r}.",
        f"The answer is {r}.",
        f"I make that {r}.",
        f"Got it: {shown} comes out to {r}.",
        f"Sure! {shown} is {r}.",
    ])